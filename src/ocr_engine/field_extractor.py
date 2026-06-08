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
    discount: Optional[str] = None
    tax_rate: Optional[str] = None
    tax_amount: Optional[str] = None
    cgst_rate: Optional[str] = None
    cgst_amount: Optional[str] = None
    sgst_rate: Optional[str] = None
    sgst_amount: Optional[str] = None
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
                       "amount", "price", "total", "rate", "hsn", "sac",
                       "cgst", "sgst", "vat", "gst", "discount", "mrp"}

    for table in tables:
        if not table or len(table) < 2:
            continue

        # Check if first row looks like a header
        header_row = [str(cell or "").lower().strip() for cell in table[0]]
        matched = sum(1 for h in header_row if any(kw in h for kw in HEADER_KEYWORDS))
        if matched < 2:
            continue

        # Build column index map — covers all labels used across every invoice profile
        col_map: Dict[str, int] = {}
        for idx, header in enumerate(header_row):
            # ── Serial number ────────────────────────────────────────────────
            # Matches: "sr. no.", "sr", "no.", "s.no.", "item #", "line", "#"
            if (
                "sr" in header
                or header in ("no", "no.", "s.no", "s.no.", "#", "line")
                or (header.startswith("item") and "#" in header)
            ):
                col_map.setdefault("sr_no", idx)

            # ── Description ──────────────────────────────────────────────────
            # Matches: "description", "item description", "particulars",
            #          "product/service", "item"  (but NOT "item #")
            elif (
                "description" in header
                or "particular" in header
                or "product" in header
                or "service" in header
                or (header == "item")
            ):
                col_map.setdefault("description", idx)

            # ── HSN / SAC ────────────────────────────────────────────────────
            elif "hsn" in header or "sac" in header:
                col_map.setdefault("hsn_sac_code", idx)

            # ── Quantity ─────────────────────────────────────────────────────
            # Matches: "qty", "quantity", "units", "unit" (standalone)
            elif (
                "qty" in header
                or "quantity" in header
                or header in ("units", "unit")
            ):
                col_map.setdefault("quantity", idx)

            # ── Tax / VAT / GST rate (%, not amount) ─────────────────────────
            # CGST and SGST get their own dedicated keys; generic tax/gst/vat
            # only falls through if it's not already one of those.
            elif "cgst" in header and "%" in header and "amt" not in header and "amount" not in header:
                col_map.setdefault("cgst_rate", idx)

            elif "sgst" in header and "%" in header and "amt" not in header and "amount" not in header:
                col_map.setdefault("sgst_rate", idx)

            elif (
                "%" in header
                and any(kw in header for kw in ("tax", "gst", "vat"))
                and "amt" not in header
                and "amount" not in header
            ) or (
                "tax" in header and "rate" in header
            ):
                col_map.setdefault("tax_rate", idx)

            # ── Unit price / rate ─────────────────────────────────────────────
            # Matches: "unit price", "list price", "mrp", "rate" (not tax-rate),
            #          "price" standalone
            elif (
                ("price" in header and "unit" in header)
                or ("price" in header and "list" in header)
                or header in ("mrp", "rate", "price")
                or ("rate" in header and "tax" not in header and "%" not in header)
            ):
                col_map.setdefault("unit_price", idx)

            # ── Discount ──────────────────────────────────────────────────────
            elif "disc" in header:
                col_map.setdefault("discount", idx)

            # ── Tax / GST / VAT / CGST / SGST amount ─────────────────────────
            elif "cgst" in header and any(kw in header for kw in ("amt", "amount")):
                col_map.setdefault("cgst_amount", idx)

            elif "sgst" in header and any(kw in header for kw in ("amt", "amount")):
                col_map.setdefault("sgst_amount", idx)

            elif (
                any(kw in header for kw in ("tax", "gst", "vat"))
                and any(kw in header for kw in ("amt", "amount"))
            ):
                col_map.setdefault("tax_amount", idx)

            # ── Line total (catch-all — must be last) ─────────────────────────
            elif (
                "total" in header
                or "amount" in header
                or "amt" in header
            ):
                col_map.setdefault("line_total", idx)

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
                discount     = cell(row, "discount"),
                tax_rate     = cell(row, "tax_rate"),
                tax_amount   = cell(row, "tax_amount"),
                cgst_rate    = cell(row, "cgst_rate"),
                cgst_amount  = cell(row, "cgst_amount"),
                sgst_rate    = cell(row, "sgst_rate"),
                sgst_amount  = cell(row, "sgst_amount"),
                line_total   = cell(row, "line_total"),
            ))
        break  # use the first matching table

    return items

def _extract_party_info(text: str, tables: list | None = None) -> dict:
    """
    Parse vendor and buyer name/address from the invoice.

    Strategy (in priority order):
      1. Scan pdfplumber tables for a table whose first row contains both
         'Bill From' and 'Bill To' headers — these are extracted cleanly
         with no character-alignment issues.
      2. Fall back to character-column splitting on the raw text (original
         approach, kept as a safety net for non-table layouts).
    """
    result = {"vendor_name": None, "vendor_address": None,
              "buyer_name": None,  "buyer_address": None}

    # ── Strategy 1: read from pdfplumber table data ───────────────────────────
    # The party block is a proper PDF Table, so pdfplumber returns it cleanly.
    # Row 0: ["Bill From:", "Bill To:"]
    # Row 1: [vendor_name, buyer_name]
    # Row 2: [vendor_address, buyer_address]
    # Row 3 (optional): ["GSTIN: ... PAN: ...", ""]
    if tables:
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = [str(c or "").lower().strip() for c in table[0]]
            # Identify the party table by its header row
            if any("bill from" in h for h in header) and any("bill to" in h for h in header):
                from_idx = next((i for i, h in enumerate(header) if "bill from" in h), 0)
                to_idx   = next((i for i, h in enumerate(header) if "bill to"   in h), 1)

                def _cell(row, idx):
                    if idx < len(row):
                        val = str(row[idx] or "").strip()
                        return val if val else None
                    return None

                # Row 1 → names, Row 2 → addresses
                if len(table) > 1:
                    result["vendor_name"] = _cell(table[1], from_idx)
                    result["buyer_name"]  = _cell(table[1], to_idx)
                if len(table) > 2:
                    result["vendor_address"] = _cell(table[2], from_idx)
                    result["buyer_address"]  = _cell(table[2], to_idx)
                return result

    # ── Strategy 2: character-column split on raw text (fallback) ─────────────
    header_match = re.search(
        r"(?i)([ \t]*)(bill\s+from:)([ \t]*)(bill\s+to:)([ \t]*)\n",
        text
    )
    if not header_match:
        m = re.search(r"(?i)(?:from|vendor|seller)[:\s]+([^\n]+)", text)
        if m: result["vendor_name"] = m.group(1).strip()
        m = re.search(r"(?i)(?:bill\s+to|sold\s+to|customer|buyer)[:\s]+([^\n]+)", text)
        if m: result["buyer_name"] = m.group(1).strip()
        return result

    header_line = header_match.group(0)
    split_pos   = header_line.lower().index("bill to:")
    rest        = text[header_match.end():]
    lines       = rest.split("\n")[:6]

    left_lines, right_lines = [], []
    for line in lines:
        left_part  = line[:split_pos].strip()
        right_part = line[split_pos:].strip()
        if left_part  and not re.match(r"(?i)^(gstin|pan)[:\s]", left_part):
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

    # ── Party fields (table-aware extraction) ──────────────────────────────
    party = _extract_party_info(text, tables=tables)
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
