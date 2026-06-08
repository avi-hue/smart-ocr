"""
invoice_structures.py – Week 1 Research Output
================================================
Documents the key fields found in typical invoice layouts
and the regex patterns used to identify them.

This module serves as the "research" artifact for Week 1
and is consumed by the extraction engine in Week 1-2.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Invoice field taxonomy
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class InvoiceField:
    """Describes a single extractable invoice field."""
    name: str
    description: str
    required: bool
    example_values: List[str] = field(default_factory=list)
    regex_hints: List[str]    = field(default_factory=list)


# ── Header / Metadata fields ──────────────────────────────────────────────────
HEADER_FIELDS: List[InvoiceField] = [
    InvoiceField(
        name="invoice_number",
        description="Unique identifier assigned by the vendor",
        required=True,
        example_values=["INV-2024-001", "2024/INV/00123", "INV#5678"],
        regex_hints=[
            r"(?i)invoice\s*(?:#|no\.?|number)[:\s]*([A-Z0-9\-/]+)",
            r"(?i)INV[-\s]?(\d+)",
        ],
    ),
    InvoiceField(
        name="invoice_date",
        description="Date the invoice was issued",
        required=True,
        example_values=["01/06/2024", "June 1, 2024", "2024-06-01"],
        regex_hints=[
            r"(?i)(?:invoice\s+)?date[:\s]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            r"(?i)date[:\s]*([A-Za-z]+ \d{1,2},? \d{4})",
        ],
    ),
    InvoiceField(
        name="due_date",
        description="Payment due date",
        required=False,
        example_values=["30/06/2024", "Net 30"],
        regex_hints=[
            r"(?i)(?:payment\s+)?due\s+(?:date|by)[:\s]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            r"(?i)(net\s*\d+)",
        ],
    ),
    InvoiceField(
        name="purchase_order",
        description="Buyer's PO number linked to this invoice",
        required=False,
        example_values=["PO-2024-789", "4500012345"],
        regex_hints=[
            r"(?i)\b(?:purchase\s+order|p\.?o\.?\s*(?:number|no\.?))\s*[:#\s]\s*([A-Z0-9][A-Z0-9\-/]{1,20})",
        ],
    ),
]

# ── Vendor / Seller fields ────────────────────────────────────────────────────
VENDOR_FIELDS: List[InvoiceField] = [
    InvoiceField(
        name="vendor_name",
        description="Legal name of the selling company",
        required=True,
        example_values=["Acme Corp", "Global Supplies Ltd."],
        regex_hints=[
            r"(?i)bill\s+from:[^\n]*\n\s*([a-zA-Z0-9_\s\.,\-]+?)(?:\s{3,}|\n)",
            r"(?i)(?:from|seller|vendor)[:\s]+([^ \n]+(?: [^ \n]+)*?)(?:\s{2,}|\n)",
        ],
    ),
    InvoiceField(
        name="vendor_address",
        description="Full postal address of the vendor",
        required=False,
        example_values=["123 Main St, Mumbai, MH 400001"],
        regex_hints=[
            r"(?i)bill\s+from:[^\n]*\n[^\n]*\n\s*([a-zA-Z0-9_\s\.,\-]+?)(?:\s{3,}|\n)",
        ],
    ),
    InvoiceField(
        name="vendor_gstin",
        description="GST Identification Number (India-specific)",
        required=False,
        example_values=["27AABCU9603R1ZX"],
        regex_hints=[
            r"(?i)GSTIN?[:\s]*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
        ],
    ),
    InvoiceField(
        name="vendor_pan",
        description="Permanent Account Number (India-specific)",
        required=False,
        example_values=["AABCU9603R"],
        regex_hints=[
            r"(?i)PAN[:\s]*([A-Z]{5}[0-9]{4}[A-Z]{1})",
        ],
    ),
]

# ── Buyer / Bill-to fields ────────────────────────────────────────────────────
BUYER_FIELDS: List[InvoiceField] = [
    InvoiceField(
        name="buyer_name",
        description="Name of the purchasing entity",
        required=True,
        example_values=["XYZ Enterprises", "John Doe"],
        regex_hints=[
            r"(?i)bill\s+to:[^\n]*\n.*?\s{3,}([a-zA-Z0-9_\s\.,\-]+?)(?:\s{3,}|\n|$)",
            r"(?i)(?:sold\s+to|customer|buyer)[:\s]+([^ \n]+(?: [^ \n]+)*?)(?:\s{2,}|\n)",
        ],
    ),
    InvoiceField(
        name="buyer_address",
        description="Billing address of the buyer",
        required=False,
        example_values=["456 Park Ave, Delhi 110001"],
        regex_hints=[
            r"(?i)bill\s+to:[^\n]*\n[^\n]*\n.*?\s{3,}([a-zA-Z0-9_\s\.,\-]+?)(?:\s{3,}|\n|$)",
        ],
    ),
]

# ── Financial fields ──────────────────────────────────────────────────────────
FINANCIAL_FIELDS: List[InvoiceField] = [
    InvoiceField(
        name="subtotal",
        description="Sum before taxes and fees",
        required=True,
        example_values=["₹10,000.00", "$5,000.00"],
        regex_hints=[
            r"(?i)sub[\s\-]?total[^:\n]*?[: \t]*[^\d\n]*([\d,]+\.\d{2})",
        ],
    ),
    InvoiceField(
        name="tax_amount",
        description="Total tax charged (GST / VAT / etc.)",
        required=True,
        example_values=["₹1,800.00 (18% GST)"],
        regex_hints=[
            r"(?i)(?:gst|vat|tax|igst|cgst|sgst)[^:\n]*?[: \t]*[^\d\n]*([\d,]+\.\d{2})",
        ],
    ),
    InvoiceField(
        name="total_amount",
        description="Grand total payable",
        required=True,
        example_values=["₹11,800.00", "$5,500.00"],
        regex_hints=[
            r"(?i)(?:grand\s+)?\btotal(?:\s+amount)?(?:\s+due)?[^:\n]*?[: \t]*[^\d\n]*([\d,]+\.\d{2})",
            r"(?i)amount\s+payable[^:\n]*?[: \t]*[^\d\n]*([\d,]+\.\d{2})",
        ],
    ),
    InvoiceField(
        name="currency",
        description="Currency code or symbol",
        required=False,
        example_values=["INR", "USD", "EUR", "₹", "$"],
        regex_hints=[
            r"(?i)currency[:\s]*([A-Z]{3})",
            r"(Rs\.|€|\$)",    # matches Rs. (INR), € (EUR), $ (USD) as used in PDFs
        ],
    ),
]

# ── Line item table columns ───────────────────────────────────────────────────
LINE_ITEM_COLUMNS = [
    "sr_no",
    "description",
    "hsn_sac_code",
    "quantity",
    "unit",
    "unit_price",
    "discount",
    "tax_rate",
    "tax_amount",
    "line_total",
]

# ── Master field registry ─────────────────────────────────────────────────────
ALL_FIELDS: List[InvoiceField] = (
    HEADER_FIELDS + VENDOR_FIELDS + BUYER_FIELDS + FINANCIAL_FIELDS
)

# ── Invoice type classification ───────────────────────────────────────────────
INVOICE_TYPES = {
    "text_based": "PDF with selectable/embedded text — use PyMuPDF/pdfplumber",
    "scanned"   : "PDF containing rasterised image — use Tesseract OCR",
    "mixed"     : "PDF with both text pages and image pages",
}


def list_required_fields() -> List[str]:
    """Return names of all mandatory invoice fields."""
    return [f.name for f in ALL_FIELDS if f.required]


def list_all_fields() -> List[str]:
    """Return names of every tracked invoice field."""
    return [f.name for f in ALL_FIELDS]


if __name__ == "__main__":
    print("Required fields:", list_required_fields())
    print("All fields     :", list_all_fields())
    print("Line item cols :", LINE_ITEM_COLUMNS)
