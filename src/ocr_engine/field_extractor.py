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
    extra_fields: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExtractedInvoice:
    """All structured fields extracted from a single invoice PDF."""

    source_file: Path

    # Header
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    purchase_order: Optional[str] = None
    order_id: Optional[str] = None
    ship_mode: Optional[str] = None

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
    extra_fields: Dict[str, str] = field(default_factory=dict)
    overall_ocr_confidence: Optional[float] = None

    def to_flat_dict(self) -> dict:
        """Return all scalar fields as a flat dictionary (for Excel row)."""
        return {
            "source_file"   : str(self.source_file.name),
            "ocr_confidence": f"{self.overall_ocr_confidence:.1f}%" if self.overall_ocr_confidence is not None else "100.0% (Native)",
            "invoice_number": self.invoice_number,
            "invoice_date"  : self.invoice_date,
            "due_date"      : self.due_date,
            "purchase_order": self.purchase_order,
            "order_id"      : self.order_id,
            "ship_mode"     : self.ship_mode,
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
            **self.extra_fields,
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
                       "cgst", "sgst", "vat", "gst", "discount", "mrp", "product", "model",
                       "date", "charge", "charges", "credit", "credits", "reference", "activity", "folio"}

    for table in tables:
        if not table or len(table) < 2:
            continue

        # Check if first row looks like a header
        header_row = [str(cell or "").lower().strip() for cell in table[0]]
        matched = sum(1 for h in header_row if any(kw in h for kw in HEADER_KEYWORDS))
        has_description_col = any("description" in h or "particular" in h or "item" in h or "charge" in h for h in header_row)
        if matched < 2 and not has_description_col:
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
                or ("price" in header and "net" in header)
                or ("price" in header and "list" in header)
                or ("price" in header and "item" in header)
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
            else:
                # Capture any unknown column headers exactly as they appear
                # Title-case it for aesthetics (e.g. "salesperson" -> "Salesperson")
                clean_header = str(table[0][idx]).strip().title()
                if clean_header and clean_header not in col_map:
                    if __import__("re").match(r"^[A-Za-z0-9\s\.\-/#]{2,30}$", clean_header) and not __import__("re").search(r"(?i)^(invoice|date|fd7|mhl|page)", clean_header):
                        col_map[clean_header] = idx

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
            
            # Gather all fields in raw order
            extras = {}
            for idx, header in enumerate(table[0]):
                if header and idx < len(row):
                    val = row[idx]
                    if val is not None:
                        clean_header = str(header).strip().title()
                        extras[clean_header] = str(val).strip()

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
                extra_fields = extras,
            ))
        break  # use the first matching table

    return items


def clean_numeric(val: Optional[str]) -> Optional[str]:
    if not val:
        return val
    cleaned = re.sub(r"[\$\u20AC\u00A3\u20B9]|Rs\.?|INR", "", val, flags=re.IGNORECASE)
    return cleaned.strip()


# Improved number pattern that prevents matching across separate columns
NUMBER_PATTERN = r"(?:\d+(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d{3})+(?:,\d+)?|\d+(?:\s\d{3})+(?:[\.,]\d+)?|\d+(?:[\.,]\d+)?)"

def get_max_tail_tokens(header_line: str) -> int:
    lower = header_line.lower()
    desc_keywords = ["description", "item", "particulars", "product", "service"]
    pos = -1
    for kw in desc_keywords:
        pos = lower.find(kw)
        if pos != -1:
            pos += len(kw)
            break
    if pos == -1:
        return 4
    
    text_to_right = header_line[pos:].strip()
    if not text_to_right:
        return 4
        
    cols = [c.strip() for c in re.split(r"\s{2,}", text_to_right) if c.strip()]
    if len(cols) <= 1:
        # Concept counting logic for single-spaced headers (common in Tesseract OCR output)
        concepts = [
            ("hsn_sac", [r'hsn\s*/\s*sac', r'hsn', r'sac']),
            ("net_price", [r'unit\s+price', r'net\s+price', r'list\s+price', r'item\s+price']),
            ("net_worth", [r'net\s+worth', r'net\s+amount', r'net\s+amt']),
            ("gross_worth", [r'gross\s+worth', r'gross\s+amount', r'gross\s+total']),
            ("tax_rate", [r'tax\s+rate', r'tax\s+amount', r'cgst\s+rate', r'sgst\s+rate', r'cgst\s+amount', r'sgst\s+amount', r'vat\s+amount', r'vat\s+\[%\]', r'vat']),
            ("quantity", [r'qty', r'quantity', r'units', r'unit']),
            ("um", [r'\bum\b', r'\buom\b', r'\bpcs\b', r'\beach\b']),
            ("price", [r'price']),
            ("rate", [r'rate']),
            ("net", [r'net']),
            ("gross", [r'gross']),
            ("total", [r'total']),
            ("amount", [r'amount', r'amt']),
            ("worth", [r'worth'])
        ]
        
        matched_indices = set()
        concept_count = 0
        
        tr_lower = text_to_right.lower()
        for concept_name, patterns in concepts:
            matched_concept = False
            for pattern in patterns:
                for match in re.finditer(pattern, tr_lower):
                    start, end = match.span()
                    if not any(idx in matched_indices for idx in range(start, end)):
                        matched_indices.update(range(start, end))
                        matched_concept = True
            if matched_concept:
                concept_count += 1
                
        return concept_count if concept_count > 0 else 4
        
    return len(cols)


def parse_header_columns(header_line: str) -> List[str]:
    lower = header_line.lower()
    desc_keywords = ["description", "item", "particulars", "product", "service"]
    pos = -1
    for kw in desc_keywords:
        pos = lower.find(kw)
        if pos != -1:
            pos += len(kw)
            break
    if pos == -1:
        return []
    
    text_to_right = header_line[pos:].strip()
    if not text_to_right:
        return []
        
    cols = [c.strip() for c in re.split(r"\s{2,}", text_to_right) if c.strip()]
    if len(cols) <= 1:
        # Concept counting logic for single-spaced headers
        concepts = [
            ("hsn_sac", [r'hsn\s*/\s*sac', r'hsn', r'sac']),
            ("net_price", [r'unit\s+price', r'net\s+price', r'list\s+price', r'item\s+price']),
            ("net_worth", [r'net\s+worth', r'net\s+amount', r'net\s+amt']),
            ("gross_worth", [r'gross\s+worth', r'gross\s+amount', r'gross\s+total']),
            ("tax_rate", [r'tax\s+rate', r'tax\s+amount', r'cgst\s+rate', r'sgst\s+rate', r'cgst\s+amount', r'sgst\s+amount', r'vat\s+amount', r'vat\s+\[%\]', r'vat']),
            ("quantity", [r'qty', r'quantity', r'units', r'unit']),
            ("um", [r'\bum\b', r'\buom\b', r'\bpcs\b', r'\beach\b']),
            ("price", [r'price']),
            ("rate", [r'rate']),
            ("net", [r'net']),
            ("gross", [r'gross']),
            ("total", [r'total']),
            ("amount", [r'amount', r'amt']),
            ("worth", [r'worth'])
        ]
        
        matched_spans = []
        tr_lower = text_to_right.lower()
        for concept_name, patterns in concepts:
            for pattern in patterns:
                for match in re.finditer(pattern, tr_lower):
                    start, end = match.span()
                    if not any(max(start, s) < min(end, e) for s, e, _ in matched_spans):
                        matched_spans.append((start, end, text_to_right[start:end].strip()))
                        
        matched_spans.sort(key=lambda x: x[0])
        return [name for _, _, name in matched_spans]
        
    return cols

def map_col_name_to_field(col_name: str) -> Optional[str]:
    name = col_name.lower()
    if "qty" in name or "quantity" in name:
        return "quantity"
    if "unit price" in name or "net price" in name or "price" in name or "rate" in name:
        if "worth" in name or "amount" in name or "total" in name:
            return None
        return "unit_price"
    if "vat" in name or "tax" in name or "gst" in name or "%" in name:
        if "amount" in name or "amt" in name:
            return "tax_amount"
        return "tax_rate"
    if "gross" in name or "total" in name or "amount" in name or "amt" in name:
        return "line_total"
    if "hsn" in name or "sac" in name:
        return "hsn_sac_code"
    return None

def _extract_line_items_from_ocr_text(text: str) -> List[LineItem]:
    """
    Extract line items from raw OCR text using a rule-based parser.
    """
    items: List[LineItem] = []
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    table_lines = []
    in_table = False
    max_tail_tokens = 4
    header_cols = []
    
    # Standard keywords to find start of table
    start_keywords = ["items", "item", "description", "qty", "quantity", "net price", "net worth", "gross worth", "particulars", "rate", "amount", "charge", "charges", "credit", "credits", "date", "reference"]
    # Standard keywords to find end of table / start of summary
    end_keywords = ["summary", "subtotal", "total", "grand total", "amount payable", "amount due", "vat [", "vat%", "tax amount", "balance due"]

    for line in lines:
        lower_line = line.lower()
        
        if not in_table:
            matched_start = sum(1 for kw in start_keywords if kw in lower_line)
            has_desc = any(kw in lower_line for kw in ["description", "particulars", "item", "charges"])
            if matched_start >= 2 or (matched_start >= 1 and has_desc) or (len(lower_line) < 15 and "items" in lower_line):
                in_table = True
                header_cols = parse_header_columns(line)
                max_tail_tokens = len(header_cols) if header_cols else 4
                continue
        else:
            # If we find a line inside the table section that contains key header terms,
            # re-evaluate the columns count and skip processing it as a line item
            if any(kw in lower_line for kw in ["description", "particulars", "net price"]):
                header_cols = parse_header_columns(line)
                max_tail_tokens = len(header_cols) if header_cols else 4
                continue

            # Extract tokens to see if we hit a summary line
            temp_line = line
            tokens = []
            currency_pattern = r"(?:[\$\u20AC\u00A3\u20B9]|Rs\.?|INR)?"
            
            while len(tokens) < max_tail_tokens:
                m = re.search(r"\s+(" + currency_pattern + r"\s*" + NUMBER_PATTERN + r"(?:\s*%)?|\b(?:each|pcs|units?|UM)\b)\s*$", temp_line, re.IGNORECASE)
                if not m:
                    break
                tokens.append(m.group(1).strip())
                temp_line = temp_line[:m.start()].strip()
            tokens.reverse()

            matched_end = any(kw in lower_line for kw in end_keywords)
            is_end = False
            if matched_end:
                if len(tokens) < 3:
                    if "summary" in lower_line or "subtotal" in lower_line or "total" in lower_line or "balance due" in lower_line:
                        is_end = True
            
            if is_end:
                break
            table_lines.append((line, tokens, max_tail_tokens))

    # If we didn't find clear boundaries (meaning we never detected a table header), search the entire text for lines that look like table rows
    if not in_table and not table_lines:
        table_lines = [(line, [], max_tail_tokens) for line in lines]

    current_item: Optional[LineItem] = None
    currency_pattern = r"(?:[\$\u20AC\u00A3\u20B9]|Rs\.?|INR)?"

    for line, tokens, mt in table_lines:
        sr_match = re.match(r"^(\d+|tke|1e|l|i|t)\s*[\.,\s]\s*(.*)$", line, flags=re.IGNORECASE)
        
        # Extract tokens from the appropriate portion of the line
        if sr_match:
            sr_no = sr_match.group(1).lower()
            if not sr_no.isdigit():
                sr_no = "1"
            rest = sr_match.group(2).strip()
            temp_rest = rest
            tokens = []
            while len(tokens) < mt:
                m = re.search(r"\s+(" + currency_pattern + r"\s*" + NUMBER_PATTERN + r"(?:\s*%)?|\b(?:each|pcs|units?|UM)\b)\s*$", temp_rest, re.IGNORECASE)
                if not m:
                    break
                tokens.append(m.group(1).strip())
                temp_rest = temp_rest[:m.start()].strip()
            tokens.reverse()
            desc = temp_rest
        else:
            sr_no = None
            temp_line = line
            tokens = []
            while len(tokens) < mt:
                m = re.search(r"\s+(" + currency_pattern + r"\s*" + NUMBER_PATTERN + r"(?:\s*%)?|\b(?:each|pcs|units?|UM)\b)\s*$", temp_line, re.IGNORECASE)
                if not m:
                    break
                tokens.append(m.group(1).strip())
                temp_line = temp_line[:m.start()].strip()
            tokens.reverse()
            desc = temp_line

        # Map tokens
        if tokens:
            item = LineItem(sr_no=sr_no, description=desc, extra_fields={})
            
            # Populate extra_fields with all columns in their raw order
            if sr_no is not None:
                sr_header = "No."
                # Check if raw headers have a custom serial number name
                for h in header_cols:
                    if h.lower() in ("no", "no.", "sr", "sr.", "sr.no.", "s.no.", "#"):
                        sr_header = h.strip().title()
                        break
                item.extra_fields[sr_header] = sr_no
                
            item.extra_fields["Description"] = desc
            
            # Map using header columns alignment
            for col_idx, token in enumerate(tokens):
                if col_idx < len(header_cols):
                    col_name = header_cols[col_idx]
                    field_name = map_col_name_to_field(col_name)
                    clean_val = clean_numeric(token)
                    
                    if field_name:
                        setattr(item, field_name, clean_val)
                    
                    # Store ALL fields in extra_fields in raw order
                    clean_header = col_name.strip().title()
                    if __import__("re").match(r"^[A-Za-z0-9\s\.\-/#]{2,30}$", clean_header) and not __import__("re").search(r"(?i)^(invoice|date|fd7|mhl|page)", clean_header):
                        item.extra_fields[clean_header] = clean_val
            
            if item.quantity or item.line_total or item.unit_price:
                # Row validation to identify description continuations vs standalone items
                is_valid_item = False
                if sr_no is not None:
                    is_valid_item = True
                else:
                    if item.line_total and (item.unit_price or item.quantity):
                        is_valid_item = True
                    elif item.line_total and not re.match(r"^\d+$", item.line_total):
                        is_valid_item = True
                        
                if is_valid_item:
                    current_item = item
                    items.append(current_item)
                elif current_item:
                    current_item.description = (current_item.description or "") + " " + line
                    if "Description" in current_item.extra_fields:
                        current_item.extra_fields["Description"] = current_item.description
            elif current_item:
                current_item.description = (current_item.description or "") + " " + line
                if "Description" in current_item.extra_fields:
                    current_item.extra_fields["Description"] = current_item.description
        else:
            if current_item:
                current_item.description = (current_item.description or "") + " " + line
                if "Description" in current_item.extra_fields:
                    current_item.extra_fields["Description"] = current_item.description

    # Filter out empty or non-item rows
    valid_items = []
    for item in items:
        if not item.description:
            continue
        desc_lower = item.description.lower()
        if "description" in desc_lower and "qty" in desc_lower:
            continue
        if "items" == desc_lower.strip() or "summary" == desc_lower.strip():
            continue
        if item.quantity or item.line_total or item.unit_price:
            item.description = re.sub(r"\s+", " ", item.description).strip()
            valid_items.append(item)

    return valid_items


def _extract_header_table_fields(tables: list) -> dict:
    """
    Look for 2-row tables that contain summary information like 'P.O. NUMBER',
    'TERMS', 'SALESPERSON', 'DATE', etc., and extract them as key-value pairs.
    """
    extracted = {}
    for table in tables:
        # A typical header table has exactly 2 rows (Headers, Values)
        # or it's a vertical table (Key, Value)
        if len(table) == 2:
            headers = [str(c).strip().lower() for c in table[0] if c]
            # Verify it's not a line-item table
            if not any(kw in " ".join(headers) for kw in ("description", "qty", "quantity")):
                for idx, header in enumerate(table[0]):
                    if header and idx < len(table[1]):
                        val = table[1][idx]
                        if val:
                            extracted[header.strip().lower()] = str(val).strip()
    return extracted

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

    # ── Strategy 0: Custom layout-specific parser for Seller: Client: block (scanned images) ──
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    header_idx = -1
    for idx, line in enumerate(lines):
        if "seller:" in line.lower() and "client:" in line.lower():
            header_idx = idx
            break
            
    if header_idx != -1 and header_idx + 3 < len(lines):
        line1 = lines[header_idx + 1]
        line2 = lines[header_idx + 2]
        line3 = lines[header_idx + 3]
        
        def split_names_line(line):
            words = line.split()
            if len(words) < 2: return line, ""
            if len(words) >= 2 and words[1].lower() in ("ltd", "group"):
                split_idx = 2
            elif len(words) >= 3 and words[2].lower() in ("sons",):
                split_idx = 3
            else:
                split_idx = len(words) // 2
                for idx, w in enumerate(words):
                    if w.lower() == "and":
                        split_idx = idx + 2
                        break
            return " ".join(words[:split_idx]), " ".join(words[split_idx:])

        def split_city_line(line):
            matches = list(re.finditer(r"\b\d{5}\b", line))
            if matches:
                split_idx = matches[0].end()
                return split_idx, line[:split_idx].strip(), line[split_idx:].strip()
            return len(line) // 2, line, ""

        def split_street_line_refined(line):
            words = line.split()
            if len(words) < 2: return line, ""
            if len(words) >= 3 and re.match(r"^\d{5}$", words[2]):
                return " ".join(words[:3]), " ".join(words[3:])
            for idx in range(1, len(words)):
                if words[idx].lower() in ("unit", "apt", "apt.", "box"):
                    return " ".join(words[:idx]), " ".join(words[idx:])
            for idx in (5, 4, 3):
                if idx < len(words):
                    clean_w = re.sub(r"\D", "", words[idx])
                    if len(clean_w) >= 3:
                        return " ".join(words[:idx]), " ".join(words[idx:])
            split_idx = len(words) // 2
            return " ".join(words[:split_idx]), " ".join(words[split_idx:])

        v_name, b_name = split_names_line(line1)
        _, c_sel, c_buy = split_city_line(line3)
        s_sel, s_buy = split_street_line_refined(line2)
        
        result["vendor_name"] = v_name
        result["buyer_name"] = b_name
        result["vendor_address"] = f"{s_sel}, {c_sel}" if s_sel and c_sel else (s_sel or c_sel)
        result["buyer_address"] = f"{s_buy}, {c_buy}" if s_buy and c_buy else (s_buy or c_buy)
        return result

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
        r"(?i)([ \t]*)(bill\s+from:|from:|vendor:)([ \t]*)(bill\s+to:|to:|ship\s+to:)([ \t]*)\n",
        text
    )
    if not header_match:
        # Check for column split where Vendor is missing but TO: and SHIP TO: exist (like external_1)
        alt_match = re.search(r"(?i)([ \t]*)(to:)([ \t]*)(ship\s+to:)([ \t]*)\n", text)
        if alt_match:
            split_pos = alt_match.group(0).lower().index("ship to:")
            rest = text[alt_match.end():]
            lines = rest.split("\n")[:4]
            left_lines = [line[:split_pos].strip() for line in lines if line[:split_pos].strip()]
            if left_lines:
                result["buyer_name"] = left_lines[0]
                result["buyer_address"] = left_lines[1] if len(left_lines) > 1 else None
        else:
            # Simple regex fallback (like external_2)
            m = re.search(r"(?i)(?:from|vendor|seller)[: \t]*\n?([^\n]+)", text)
            if m: result["vendor_name"] = m.group(1).strip()
            
            m = re.search(r"(?i)(?:bill\s+to|sold\s+to|customer|buyer|to)[: \t]*\n([^\n]+)", text)
            if m: result["buyer_name"] = m.group(1).strip()

        # If vendor is still missing, the first non-empty line of the PDF is almost always the Vendor
        if not result["vendor_name"]:
            first_line = text.strip().split("\n")[0]
            if first_line and "invoice" not in first_line.lower():
                result["vendor_name"] = first_line
            elif len(text.strip().split("\n")) > 1:
                result["vendor_name"] = text.strip().split("\n")[0].replace("INVOICE", "").strip() or text.strip().split("\n")[1]

        return result

    header_line = header_match.group(0)
    # find the start of the 'to' part
    split_match = re.search(r"(?i)(bill\s+to:|to:|ship\s+to:)", header_line)
    split_pos   = split_match.start() if split_match else len(header_line) // 2
    
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
    extracted_data = {}

    # ── Party fields (table-aware extraction) ──────────────────────────────
    party = _extract_party_info(text, tables=tables)
    invoice.vendor_name    = party["vendor_name"]
    invoice.vendor_address = party["vendor_address"]
    invoice.buyer_name     = party["buyer_name"]
    invoice.buyer_address  = party["buyer_address"]
    for k in ("vendor_name", "vendor_address", "buyer_name", "buyer_address"):
        confidence[k] = 1.0 if party[k] else 0.0
        log.debug("  {:20} → {}", k, party[k] or "(not found)")

    # Extract header table fields (for unstructured PO numbers, Salesperson, etc)
    header_data = _extract_header_table_fields(tables or [])

    # ── Scalar fields via regex ──────────────────────────────────────────────
    field_map = {f.name: f for f in ALL_FIELDS}

    scalar_attrs = [
        "invoice_number", "invoice_date", "due_date", "purchase_order",
        "order_id", "ship_mode",
        "vendor_gstin", "vendor_pan",
        "subtotal", "tax_amount", "total_amount", "currency",
    ]

    consumed_headers = set()

    for attr in scalar_attrs:
        inv_field = field_map.get(attr)
        
        # Check if the field was captured in header_data
        header_match = False
        for h_key, h_val in header_data.items():
            # e.g., 'p.o. number' -> 'purchase_order'
            if inv_field.name.replace("_", " ") in h_key or h_key.replace(".", "").replace(" ", "_") == inv_field.name:
                setattr(invoice, attr, h_val)
                confidence[attr] = 1.0
                log.debug("  {:20} → {} (from header table)", attr, h_val)
                header_match = True
                consumed_headers.add(h_key)
                break
            if attr == "purchase_order" and "p.o." in h_key:
                setattr(invoice, attr, h_val)
                confidence[attr] = 1.0
                log.debug("  {:20} → {} (from header table)", attr, h_val)
                header_match = True
                consumed_headers.add(h_key)
                break
        
        if header_match:
            continue

        if inv_field and inv_field.regex_hints:
            value = _try_patterns(text, inv_field)
            setattr(invoice, attr, value)
            confidence[attr] = 1.0 if value else 0.0
            log.debug("  {:20} → {}", attr, value or "(not found)")
        else:
            confidence[attr] = 0.0

    # Special parser for horizontal summary rows (especially for scanned image VAT tables)
    # Look for a line starting with Total/Summary and containing multiple currency/numeric amounts
    for line in text.split("\n"):
        line = line.strip()
        if re.match(r"(?i)^\W*(?:total|summary|grand\s+total)\b", line):
            # Extract all numeric/decimal-like tokens from this line
            amounts = re.findall(r"(?:[\$\u20AC\u00A3\u20B9]|Rs\.?|INR)?\s*(\d+[\s\d,]*[\.,]\d+|\d+)", line)
            amounts = [a.strip() for a in amounts if a.strip()]
            if len(amounts) >= 3:
                invoice.subtotal = clean_numeric(amounts[0])
                confidence["subtotal"] = 1.0
                invoice.tax_amount = clean_numeric(amounts[1])
                confidence["tax_amount"] = 1.0
                invoice.total_amount = clean_numeric(amounts[2])
                confidence["total_amount"] = 1.0
                log.info("Extracted summary from horizontal row: subtotal={}, tax_amount={}, total_amount={}", 
                         invoice.subtotal, invoice.tax_amount, invoice.total_amount)
                break
            elif len(amounts) == 2:
                invoice.subtotal = clean_numeric(amounts[0])
                confidence["subtotal"] = 1.0
                invoice.total_amount = clean_numeric(amounts[1])
                confidence["total_amount"] = 1.0
                log.info("Extracted summary from horizontal row (2 cols): subtotal={}, total_amount={}", 
                         invoice.subtotal, invoice.total_amount)
                break
            elif len(amounts) == 1:
                invoice.total_amount = clean_numeric(amounts[0])
                confidence["total_amount"] = 1.0
                break
    
    # Store any remaining header data into invoice extra_fields if we add it
    invoice.extra_fields = {}
    for h_key, h_val in header_data.items():
        if h_key not in ["date", "due date"] and h_key not in consumed_headers:
            clean_k = h_key.title()
            if __import__("re").match(r"^[A-Za-z0-9\s\.\-/#]{2,30}$", clean_k) and not __import__("re").search(r"(?i)^(invoice|date|fd7|mhl|page)", clean_k) and "!" not in clean_k:
                invoice.extra_fields[clean_k] = h_val

    # ── Line items from tables ───────────────────────────────────────────────
    if tables:
        invoice.line_items = _extract_line_items_from_tables(tables)
        log.debug("  line_items          → {} row(s)", len(invoice.line_items))
    
    if not invoice.line_items:
        log.info("No line items extracted from tables. Attempting to parse line items from raw text...")
        invoice.line_items = _extract_line_items_from_ocr_text(text)
        log.debug("  line_items (raw text) → {} row(s)", len(invoice.line_items))

    invoice.extraction_confidence = confidence

    found = sum(1 for v in confidence.values() if v > 0)
    log.info(
        "Field extraction complete: {}/{} fields found",
        found,
        len(confidence),
    )

    return invoice
