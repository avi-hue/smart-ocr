"""
field_extractor.py – Apply regex patterns to extract structured invoice fields
from raw text (works for both text-based and OCR output).

Consumes:
  - invoice_structures.py  (regex patterns, field definitions)
  - DocumentContent        (from text_extractor.py)

Returns an ExtractedInvoice dataclass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from src.utils.invoice_structures import (
    ALL_FIELDS,
    LINE_ITEM_COLUMNS,
    InvoiceField,
)
from src.utils.logger import get_logger

log = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Output dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class LineItem:
    """A single row extracted from an invoice line-item table."""
    sr_no: Optional[str] = None
    description: Optional[str] = None
    hsn_sac_code: Optional[str] = None
    quantity: Optional[str] = None
    unit_price: Optional[str] = None
    tax_rate: Optional[str] = None
    tax_amount: Optional[str] = None
    line_total: Optional[str] = None


@dataclass
class ExtractedInvoice:
    """All structured fields extracted from a single invoice PDF."""

    source_file: Path

    # Header
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    purchase_order: Optional[str] = None

    # Vendor
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    vendor_gstin: Optional[str] = None
    vendor_pan: Optional[str] = None

    # Buyer
    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None

    # Financials
    subtotal: Optional[str] = None
    tax_amount: Optional[str] = None
    total_amount: Optional[str] = None
    currency: Optional[str] = None

    # Line items
    line_items: List[LineItem] = field(default_factory=list)

    # Meta
    extraction_confidence: Dict[str, float] = field(default_factory=dict)

    def to_flat_dict(self) -> dict:
        """Return all scalar fields as a flat dictionary (for Excel row)."""
        return {
            "source_file"   : str(self.source_file.name),
            "invoice_number": self.invoice_number,
            "invoice_date"  : self.invoice_date,
            "due_date"      : self.due_date,
            "purchase_order": self.purchase_order,
            "vendor_name"   : self.vendor_name,
            "vendor_address": self.vendor_address,
            "vendor_gstin"  : self.vendor_gstin,
            "vendor_pan"    : self.vendor_pan,
            "buyer_name"    : self.buyer_name,
            "buyer_address" : self.buyer_address,
            "subtotal"      : self.subtotal,
            "tax_amount"    : self.tax_amount,
            "total_amount"  : self.total_amount,
            "currency"      : self.currency,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Extraction logic
# ──────────────────────────────────────────────────────────────────────────────

def _try_patterns(text: str, invoice_field: InvoiceField) -> Optional[str]:
    """
    Try each regex hint for a field and return the first match,
    or None if none match.
    """
    for pattern in invoice_field.regex_hints:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _extract_line_items_from_tables(
    tables: list,
) -> List[LineItem]:
    """
    Attempt to extract line items from pdfplumber table data.

    Heuristic: find a table whose header row contains keywords like
    'description', 'qty', 'amount', 'price', etc.
    """
    items: List[LineItem] = []
    HEADER_KEYWORDS = {"description", "item", "particulars", "qty", "quantity",
                       "amount", "price", "total", "rate", "hsn", "sac"}

    for table in tables:
        if not table or len(table) < 2:
            continue

        # Check if first row looks like a header
        header_row = [str(cell or "").lower().strip() for cell in table[0]]
        matched = sum(1 for h in header_row if any(kw in h for kw in HEADER_KEYWORDS))
        if matched < 2:
            continue

        # Build column index map
        col_map: Dict[str, int] = {}
        for idx, header in enumerate(header_row):
            if "sr" in header or header in ("no", "s.no", "#"):
                col_map["sr_no"] = idx
            elif "description" in header or "item" in header or "particular" in header:
                col_map["description"] = idx
            elif "hsn" in header or "sac" in header:
                col_map["hsn_sac_code"] = idx
            elif "qty" in header or "quantity" in header:
                col_map["quantity"] = idx
            elif "tax" in header and ("rate" in header or "%" in header):
                col_map["tax_rate"] = idx
            elif "unit" in header and "price" in header:
                col_map["unit_price"] = idx
            elif "rate" in header and "tax" not in header:
                col_map["unit_price"] = idx
            elif "tax" in header and ("amt" in header or "amount" in header):
                col_map["tax_amount"] = idx
            elif "total" in header or "amount" in header or "amt" in header:
                col_map["line_total"] = idx

        def cell(row, key):
            idx = col_map.get(key)
            if idx is not None and idx < len(row):
                val = row[idx]
                return str(val).strip() if val else None
            return None

        for row in table[1:]:
            # Skip empty rows
            if not any(row):
                continue
            items.append(LineItem(
                sr_no        = cell(row, "sr_no"),
                description  = cell(row, "description"),
                hsn_sac_code = cell(row, "hsn_sac_code"),
                quantity     = cell(row, "quantity"),
                unit_price   = cell(row, "unit_price"),
                tax_rate     = cell(row, "tax_rate"),
                tax_amount   = cell(row, "tax_amount"),
                line_total   = cell(row, "line_total"),
            ))
        break  # use the first matching table

    return items

def _extract_party_info(text: str) -> dict:
    """
    Parse vendor and buyer name/address from a columnar 'Bill From / Bill To' block.

    The layout looks like (with many spaces between columns):
        Bill From:                      Bill To:
        Globex Inc                      Daily Planet
        123 Vendor St, City, ST 12345   456 Buyer Ave, Town, ST 67890
        GSTIN: 27AABCU9603R1ZX PAN: ABCDE1234F

    Strategy: Find the 'Bill From:'/'Bill To:' header line, then read the
    subsequent lines. Split each line at the midpoint of the two header labels
    to reliably separate left (vendor) and right (buyer) columns.
    """
    result = {"vendor_name": None, "vendor_address": None,
              "buyer_name": None,  "buyer_address": None}

    # Find the header line containing both labels
    header_match = re.search(
        r"(?i)([ \t]*)(bill\s+from:)([ \t]*)(bill\s+to:)([ \t]*)\n",
        text
    )
    if not header_match:
        # Fallback: try simple single-column patterns
        m = re.search(r"(?i)(?:from|vendor|seller)[:\s]+([^\n]+)", text)
        if m: result["vendor_name"] = m.group(1).strip()
        m = re.search(r"(?i)(?:bill\s+to|sold\s+to|customer|buyer)[:\s]+([^\n]+)", text)
        if m: result["buyer_name"] = m.group(1).strip()
        return result

    # Calculate the column split point: position of 'Bill To:' in the header
    header_line = header_match.group(0)
    split_pos = header_line.lower().index("bill to:")

    # Grab up to 5 lines after the header
    rest_of_text = text[header_match.end():]
    lines = rest_of_text.split("\n")[:6]

    left_lines = []
    right_lines = []

    for line in lines:
        left_part  = line[:split_pos].strip()
        right_part = line[split_pos:].strip()
        # Skip lines that only contain GSTIN/PAN (keep for gstin/pan regex)
        if left_part and not re.match(r"(?i)^(gstin|pan)[:\s]", left_part):
            left_lines.append(left_part)
        if right_part and not re.match(r"(?i)^(gstin|pan)[:\s]", right_part):
            right_lines.append(right_part)

    if left_lines:
        result["vendor_name"]    = left_lines[0]
        result["vendor_address"] = left_lines[1] if len(left_lines) > 1 else None
    if right_lines:
        result["buyer_name"]    = right_lines[0]
        result["buyer_address"] = right_lines[1] if len(right_lines) > 1 else None

    return result



def extract_invoice_fields(
    text: str,
    source_file: str | Path,
    tables: list | None = None,
) -> ExtractedInvoice:
    """
    Extract all structured invoice fields from raw text.

    Args:
        text:        Raw text (from pdfplumber or Tesseract).
        source_file: Path to the original PDF (for reference).
        tables:      Optional list of pdfplumber tables for line-item extraction.

    Returns:
        ExtractedInvoice with all matched fields populated.
    """
    source_file = Path(source_file)
    invoice = ExtractedInvoice(source_file=source_file)
    confidence: Dict[str, float] = {}

    # ── Party fields (columnar extraction) ───────────────────────────────────
    party = _extract_party_info(text)
    invoice.vendor_name    = party["vendor_name"]
    invoice.vendor_address = party["vendor_address"]
    invoice.buyer_name     = party["buyer_name"]
    invoice.buyer_address  = party["buyer_address"]
    for k in ("vendor_name", "vendor_address", "buyer_name", "buyer_address"):
        confidence[k] = 1.0 if party[k] else 0.0
        log.debug("  {:20} → {}", k, party[k] or "(not found)")

    # ── Scalar fields via regex ──────────────────────────────────────────────
    field_map = {f.name: f for f in ALL_FIELDS}

    scalar_attrs = [
        "invoice_number", "invoice_date", "due_date", "purchase_order",
        "vendor_gstin", "vendor_pan",
        "subtotal", "tax_amount", "total_amount", "currency",
    ]

    for attr in scalar_attrs:
        inv_field = field_map.get(attr)
        if inv_field and inv_field.regex_hints:
            value = _try_patterns(text, inv_field)
            setattr(invoice, attr, value)
            confidence[attr] = 1.0 if value else 0.0
            log.debug("  {:20} → {}", attr, value or "(not found)")
        else:
            confidence[attr] = 0.0

    # ── Line items from tables ───────────────────────────────────────────────
    if tables:
        invoice.line_items = _extract_line_items_from_tables(tables)
        log.debug("  line_items          → {} row(s)", len(invoice.line_items))

    invoice.extraction_confidence = confidence

    found = sum(1 for v in confidence.values() if v > 0)
    log.info(
        "Field extraction complete: {}/{} fields found",
        found,
        len(confidence),
    )

    return invoice
