"""
normalizer.py – Clean and normalize raw extracted invoice field values.

Handles:
  - Date normalization   → YYYY-MM-DD
  - Amount normalization → float (strips ₹ $ € £ and commas)
  - String cleanup       → strip whitespace, collapse multiple spaces
  - Common OCR errors    → 0↔O, 1↔l substitutions in numeric fields
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Optional

from src.ocr_engine.field_extractor import ExtractedInvoice
from src.utils.logger import get_logger

log = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Date parsing
# ──────────────────────────────────────────────────────────────────────────────

_DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    (r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})", "%d%m%Y"),
    # YYYY-MM-DD
    (r"(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})", "%Y%m%d"),
    # Month DD, YYYY  e.g. "June 1, 2024" or "Jun 1 2024"
    (
        r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})",
        "named_month",
    ),
    # DD Month YYYY  e.g. "01 June 2024"
    (
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
        "day_named_month_year",
    ),
]

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def normalize_date(raw: Optional[str]) -> Optional[str]:
    """
    Parse a raw date string and return YYYY-MM-DD, or None if unparseable.
    """
    if not raw:
        return None
    raw = raw.strip()

    # Try DD/MM/YYYY style
    m = re.match(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})$", raw)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    # Try YYYY-MM-DD style
    m = re.match(r"(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})$", raw)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    # Try "Month DD, YYYY"
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", raw)
    if m:
        month_str = m.group(1).lower()[:3]
        mo = _MONTH_MAP.get(month_str)
        if mo:
            d, y = int(m.group(2)), int(m.group(3))
            return f"{y}-{mo:02d}-{d:02d}"

    # Try "DD Month YYYY"
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if m:
        month_str = m.group(2).lower()[:3]
        mo = _MONTH_MAP.get(month_str)
        if mo:
            d, y = int(m.group(1)), int(m.group(3))
            return f"{y}-{mo:02d}-{d:02d}"

    log.warning("Could not parse date: '{}'", raw)
    return raw   # return as-is rather than losing the value


# ──────────────────────────────────────────────────────────────────────────────
# Amount / currency parsing
# ──────────────────────────────────────────────────────────────────────────────

def normalize_amount(raw: Optional[str]) -> Optional[float]:
    """
    Parse a currency string and return a float.
    e.g. "₹ 1,18,000.00"  →  118000.0
    """
    if not raw:
        return None
    # Strip currency symbols and spaces
    cleaned = re.sub(r"[₹$€£\s,]", "", raw)
    # Fix common OCR substitution: O → 0 in numeric context
    cleaned = re.sub(r"(?<=[0-9])O(?=[0-9])", "0", cleaned)
    try:
        return float(cleaned)
    except ValueError:
        log.warning("Could not parse amount: '{}'", raw)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# String cleanup
# ──────────────────────────────────────────────────────────────────────────────

def clean_string(raw: Optional[str]) -> Optional[str]:
    """Collapse multiple spaces and strip leading/trailing whitespace."""
    if not raw:
        return None
    return re.sub(r"\s+", " ", raw).strip()


# ──────────────────────────────────────────────────────────────────────────────
# Normalize an entire ExtractedInvoice
# ──────────────────────────────────────────────────────────────────────────────

def normalize_invoice(invoice: ExtractedInvoice) -> ExtractedInvoice:
    """
    Return a new ExtractedInvoice with all fields normalized.
    Does NOT mutate the input.
    """
    log.info("Normalizing invoice: {}", invoice.source_file.name)

    normalized = replace(
        invoice,
        invoice_number = clean_string(invoice.invoice_number),
        invoice_date   = normalize_date(invoice.invoice_date),
        due_date       = normalize_date(invoice.due_date),
        purchase_order = clean_string(invoice.purchase_order),
        vendor_name    = clean_string(invoice.vendor_name),
        vendor_address = clean_string(invoice.vendor_address),
        vendor_gstin   = clean_string(invoice.vendor_gstin),
        vendor_pan     = clean_string(invoice.vendor_pan),
        buyer_name     = clean_string(invoice.buyer_name),
        buyer_address  = clean_string(invoice.buyer_address),
        # Amounts stored as strings (formatted) for Excel display
        subtotal       = _format_amount(invoice.subtotal),
        tax_amount     = _format_amount(invoice.tax_amount),
        total_amount   = _format_amount(invoice.total_amount),
        currency       = clean_string(invoice.currency),
    )

    log.info("Normalization complete")
    return normalized


def _format_amount(raw: Optional[str]) -> Optional[str]:
    """Normalize amount and return as a formatted string (2 dp)."""
    val = normalize_amount(raw)
    if val is None:
        return raw  # keep original if unparseable
    return f"{val:.2f}"
