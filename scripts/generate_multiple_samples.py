"""
generate_multiple_samples.py – Generates diverse invoice PDFs, each with a
DIFFERENT schema (columns and header fields vary per profile).

Profiles
────────
  standard_gst   – Full Indian GST invoice: 8 columns, all header fields
  no_po_no_pan   – Missing PO Number and Vendor PAN
  split_gst      – CGST + SGST shown separately (10 columns)
  with_discount  – Adds a Discount % column before tax
  minimal        – Bare-bones: only Sr.No., Description, Qty, Unit Price, Total
  international  – No GSTIN/PAN; uses VAT instead of GST; foreign currencies

Run: python scripts/generate_multiple_samples.py [--count N]
"""

from __future__ import annotations

import argparse
import random
import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
except ImportError:
    print("reportlab not installed. Run: pip install reportlab")
    sys.exit(1)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# Invoice Schema Profiles
# Each profile fully controls what header fields and line-item columns appear.
# ──────────────────────────────────────────────────────────────────────────────

PROFILES = [
    {
        "name": "standard_gst",
        "label": "TAX INVOICE",
        "header_color": "#1F4E79",
        "has_po": True,
        "has_gstin": True,
        "has_pan": True,
        "has_due_date": True,
        "currencies": ["INR"],
        # (key, display_label, column_width)
        "line_cols": [
            ("sr_no",      "Sr. No.",      1.5 * cm),
            ("desc",       "Description",  4.5 * cm),
            ("hsn",        "HSN/SAC",      2.0 * cm),
            ("qty",        "Qty",          1.2 * cm),
            ("unit_price", "Unit Price",   2.5 * cm),
            ("tax_rate",   "Tax Rate",     1.8 * cm),
            ("tax_amt",    "Tax Amt",      2.5 * cm),
            ("total",      "Total",        2.5 * cm),
        ],
    },
    {
        "name": "no_po_no_pan",
        "label": "INVOICE",
        "header_color": "#2E4057",
        "has_po": False,
        "has_gstin": True,
        "has_pan": False,
        "has_due_date": True,
        "currencies": ["INR"],
        "line_cols": [
            ("sr_no",      "Item #",       1.5 * cm),
            ("desc",       "Item Description", 5.5 * cm),
            ("hsn",        "HSN/SAC",      2.0 * cm),
            ("qty",        "Qty",          1.2 * cm),
            ("unit_price", "Rate",         2.5 * cm),
            ("tax_rate",   "GST %",        1.8 * cm),
            ("tax_amt",    "GST Amt",      2.5 * cm),
            ("total",      "Amount",       2.5 * cm),
        ],
    },
    {
        "name": "split_gst",
        "label": "TAX INVOICE",
        "header_color": "#374151",
        "has_po": True,
        "has_gstin": True,
        "has_pan": True,
        "has_due_date": True,
        "currencies": ["INR"],
        "line_cols": [
            ("sr_no",      "No.",          1.0 * cm),
            ("desc",       "Particulars",  3.5 * cm),
            ("hsn",        "HSN",          1.8 * cm),
            ("qty",        "Qty",          1.0 * cm),
            ("unit_price", "MRP",          2.0 * cm),
            ("cgst_rate",  "CGST %",       1.5 * cm),
            ("cgst_amt",   "CGST Amt",     2.0 * cm),
            ("sgst_rate",  "SGST %",       1.5 * cm),
            ("sgst_amt",   "SGST Amt",     2.0 * cm),
            ("total",      "Net Amount",   2.2 * cm),
        ],
    },
    {
        "name": "with_discount",
        "label": "SALES INVOICE",
        "header_color": "#7B3F00",
        "has_po": True,
        "has_gstin": True,
        "has_pan": True,
        "has_due_date": False,
        "currencies": ["INR"],
        "line_cols": [
            ("sr_no",      "S.No.",        1.2 * cm),
            ("desc",       "Product/Service", 3.8 * cm),
            ("hsn",        "HSN/SAC",      1.8 * cm),
            ("qty",        "Units",        1.0 * cm),
            ("unit_price", "List Price",   2.0 * cm),
            ("discount",   "Disc. %",      1.5 * cm),
            ("tax_rate",   "Tax %",        1.5 * cm),
            ("tax_amt",    "Tax Amt",      2.0 * cm),
            ("total",      "Final Amt",    2.7 * cm),
        ],
    },
    {
        "name": "minimal",
        "label": "BILL / RECEIPT",
        "header_color": "#1B4332",
        "has_po": False,
        "has_gstin": False,
        "has_pan": False,
        "has_due_date": False,
        "currencies": ["INR", "USD", "EUR"],
        "line_cols": [
            ("sr_no",      "#",            0.8 * cm),
            ("desc",       "Description",  9.0 * cm),
            ("qty",        "Qty",          2.0 * cm),
            ("unit_price", "Price",        3.0 * cm),
            ("total",      "Amount",       3.0 * cm),
        ],
    },
    {
        "name": "international",
        "label": "COMMERCIAL INVOICE",
        "header_color": "#1A1A2E",
        "has_po": True,
        "has_gstin": False,
        "has_pan": False,
        "has_due_date": True,
        "currencies": ["USD", "EUR"],
        "line_cols": [
            ("sr_no",      "Line",         1.0 * cm),
            ("desc",       "Item Description", 5.5 * cm),
            ("qty",        "Qty",          1.5 * cm),
            ("unit_price", "Unit Price",   2.5 * cm),
            ("vat_rate",   "VAT %",        1.8 * cm),
            ("vat_amt",    "VAT Amount",   2.5 * cm),
            ("total",      "Line Total",   2.7 * cm),
        ],
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# Random data pools
# ──────────────────────────────────────────────────────────────────────────────

VENDORS = [
    "Acme Corp", "Globex Solutions", "Soylent Industries", "Initech Ltd",
    "Massive Dynamic", "Cyberdyne Systems", "Umbrella Corp", "Pied Piper Inc",
    "Hooli Technologies", "Weyland-Yutani Corp",
]
BUYERS = [
    "Wayne Enterprises", "Stark Industries", "Oscorp LLC", "LexCorp",
    "Daily Planet Media", "Goliath National Bank", "Vought International",
    "Dunder Mifflin Paper", "Nakatomi Trading", "Prestige Worldwide",
]
ITEM_DESCS = [
    "Cloud Server Hosting", "Software License (Annual)", "Consulting Services",
    "Network Hardware", "Technical Support", "Data Storage (1 TB)",
    "Security Audit", "UPS Maintenance", "API Integration", "Training Sessions",
    "Office Supplies", "Equipment Rental", "Custom Development", "Bulk Widgets",
    "Marketing Campaign", "Legal Advisory", "Logistics & Freight", "Web Hosting",
]
STREETS = ["Main St", "Park Ave", "Oak Rd", "Market Blvd", "Lake Dr", "Hill Rd", "5th Avenue"]
CITIES  = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Pune", "Kolkata",
           "New York", "London", "Singapore", "Dubai", "Frankfurt"]
STATES  = ["MH", "DL", "KA", "TN", "TS", "GJ", "WB", "NY", "CA", "TX"]
TAX_RATES = [5, 9, 12, 18, 28]

# ReportLab built-in fonts use WinAnsiEncoding:
#   ₹ (U+20B9) is NOT in WinAnsiEncoding  → use "Rs." (ASCII fallback)
#   € (U+20AC) IS  in WinAnsiEncoding at 0x80 → safe to use directly
#   $ (U+0024) is Latin-1 → always safe
CURRENCY_SYMBOL = {"INR": "Rs.", "USD": "$", "EUR": "€"}


def _rand_pan() -> str:
    L = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(random.choices(L, k=5)) + str(random.randint(1000, 9999)) + random.choice(L)


def _rand_gstin() -> str:
    state = str(random.randint(1, 35)).zfill(2)
    pan   = _rand_pan()
    return f"{state}{pan}{random.choice('123456789')}Z{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')}"


def _rand_address() -> str:
    return (
        f"{random.randint(1, 999)} {random.choice(STREETS)}, "
        f"{random.choice(CITIES)}, {random.choice(STATES)} "
        f"{random.randint(100000, 999999)}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Compute per-row values for any column key combination
# ──────────────────────────────────────────────────────────────────────────────

def _row_values(col_keys: list[str], sr: int, desc: str, qty: int,
                price: float, tax_rate: int, sym: str) -> list[str]:
    discount_pct     = random.choice([0, 5, 10, 15]) if "discount" in col_keys else 0
    discounted_price = price * (1 - discount_pct / 100)
    half_rate        = tax_rate / 2

    base             = qty * discounted_price
    cgst_amt         = base * (half_rate / 100)
    sgst_amt         = cgst_amt
    tax_amt          = base * (tax_rate / 100)
    vat_amt          = qty * price * (tax_rate / 100)

    if "cgst_rate" in col_keys:
        line_tax = cgst_amt + sgst_amt
        line_total = base + line_tax
    elif "vat_rate" in col_keys:
        base = qty * price
        line_tax = vat_amt
        line_total = base + line_tax
    elif "discount" in col_keys or "tax_rate" in col_keys:
        line_tax = tax_amt
        line_total = base + line_tax
    else:  # minimal — no tax
        base = qty * price
        line_tax = 0.0
        line_total = base

    hsn = str(random.randint(1000, 9999))

    vm: dict[str, str] = {
        "sr_no":      str(sr),
        "desc":       desc,
        "hsn":        hsn,
        "qty":        str(qty),
        "unit_price": f"{sym}{price:.2f}",
        "discount":   f"{discount_pct}%",
        "tax_rate":   f"{tax_rate}%",
        "tax_amt":    f"{sym}{tax_amt:.2f}",
        "cgst_rate":  f"{half_rate:.1f}%",
        "cgst_amt":   f"{sym}{cgst_amt:.2f}",
        "sgst_rate":  f"{half_rate:.1f}%",
        "sgst_amt":   f"{sym}{sgst_amt:.2f}",
        "vat_rate":   f"{tax_rate}%",
        "vat_amt":    f"{sym}{vat_amt:.2f}",
        "total":      f"{sym}{line_total:.2f}",
    }
    return [vm[k] for k in col_keys], base, line_tax, line_total


# ──────────────────────────────────────────────────────────────────────────────
# PDF builder
# ──────────────────────────────────────────────────────────────────────────────

def build_invoice(
    filename: str,
    profile: dict,
    inv_num: str,
    date_str: str,
    due_date_str: str | None,
    po_num: str | None,
    vendor: str,
    vendor_addr: str,
    vendor_gstin: str | None,
    vendor_pan: str | None,
    buyer: str,
    buyer_addr: str,
    items: list[tuple],
    currency: str,
) -> None:

    sym = CURRENCY_SYMBOL.get(currency, currency)
    hdr_color = colors.HexColor(profile["header_color"])

    doc = SimpleDocTemplate(
        str(OUTPUT_DIR / filename), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    h1     = ParagraphStyle("h1",   parent=styles["Title"],  fontSize=18,
                             textColor=hdr_color)
    normal = ParagraphStyle("n9",   parent=styles["Normal"], fontSize=9)
    bold9  = ParagraphStyle("b9",   parent=styles["Normal"], fontSize=9,
                             fontName="Helvetica-Bold")

    story = []
    story.append(Paragraph(profile["label"], h1))
    story.append(Spacer(1, 0.3 * cm))

    # ── Meta block (conditionally rendered) ───────────────────────────────────
    meta_rows = [[Paragraph("<b>Invoice No.:</b>", normal), inv_num,
                  Paragraph("<b>Invoice Date:</b>", normal), date_str]]

    if profile["has_po"] and po_num:
        due_label = "<b>Due Date:</b>" if profile["has_due_date"] else "<b>Payment:</b>"
        meta_rows.append([
            Paragraph("<b>PO Number:</b>", normal), po_num,
            Paragraph(due_label, normal), due_date_str or "On Receipt",
        ])
    elif profile["has_due_date"] and due_date_str:
        meta_rows.append([
            Paragraph("<b>Due Date:</b>", normal), due_date_str, "", "",
        ])

    meta_tbl = Table(meta_rows, colWidths=[2.8*cm, 4*cm, 2.8*cm, 4*cm], hAlign="LEFT")
    meta_tbl.setStyle(TableStyle([
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # ── Party block (conditionally shows GSTIN/PAN) ───────────────────────────
    vendor_extra = ""
    if profile["has_gstin"] and vendor_gstin:
        vendor_extra += f"GSTIN: {vendor_gstin}\n"
    if profile["has_pan"] and vendor_pan:
        vendor_extra += f"PAN:   {vendor_pan}"

    party_data = [
        [Paragraph("<b>Bill From:</b>", bold9), Paragraph("<b>Bill To:</b>", bold9)],
        [Paragraph(f"<b>{vendor}</b>", bold9),  Paragraph(f"<b>{buyer}</b>", bold9)],
        [vendor_addr, buyer_addr],
    ]
    if vendor_extra.strip():
        party_data.append([vendor_extra, ""])

    party_tbl = Table(party_data, colWidths=[8.5*cm, 8.5*cm], hAlign="LEFT")
    party_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#D9E1F2")),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.grey),
    ]))
    story.append(party_tbl)
    story.append(Spacer(1, 0.5 * cm))

    # ── Line-items table (schema-driven) ──────────────────────────────────────
    col_keys   = [c[0] for c in profile["line_cols"]]
    col_labels = [c[1] for c in profile["line_cols"]]
    col_widths = [c[2] for c in profile["line_cols"]]

    table_data  = [col_labels]
    subtotal = 0.0
    tax_total = 0.0
    grand_total = 0.0

    for sr, (desc, qty, price, tax_rate) in enumerate(items, 1):
        row, r_base, r_tax, r_total = _row_values(col_keys, sr, desc, qty, price, tax_rate, sym)
        table_data.append(row)
        subtotal += r_base
        tax_total += r_tax
        grand_total += r_total

    # Build alternating row backgrounds explicitly — ROWBACKGROUNDS can render
    # as a solid black box on some ReportLab versions.
    ALT_COLORS = [colors.white, colors.HexColor("#F0F4F8")]
    row_bg_cmds = [
        ("BACKGROUND", (0, r), (-1, r), ALT_COLORS[(r - 1) % 2])
        for r in range(1, len(table_data))   # row 0 is header, already coloured
    ]

    item_tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    item_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), hdr_color),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.grey),
        *row_bg_cmds,
    ]))
    story.append(item_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # ── Grand total footer ────────────────────────────────────────────────────
    total_width = sum(col_widths)
    
    footer_data = []
    if tax_total > 0:
        footer_data.extend([
            ["", f"Subtotal:  {sym}{subtotal:,.2f}"],
            ["", f"Tax Amount:  {sym}{tax_total:,.2f}"],
        ])
    footer_data.append(["", f"Grand Total:  {sym}{grand_total:,.2f}"])

    total_tbl = Table(
        footer_data,
        colWidths=[total_width - 5*cm, 5*cm],
    )
    total_tbl.setStyle(TableStyle([
        ("FONTNAME",  (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",  (0, 0), (-1, -1), 10),
        ("ALIGN",     (1, 0), (1, -1),  "RIGHT"),
        ("LINEABOVE", (0, 0), (-1, 0),  1, hdr_color),
    ]))
    story.append(total_tbl)

    doc.build(story)
    print(f"  [OK] {filename}  [{profile['name']}]")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate diverse invoice PDF samples.")
    parser.add_argument("--count", type=int, default=6,
                        help="Number of PDFs to generate (default: 6, one per profile)")
    args = parser.parse_args()

    n = args.count
    # Ensure every profile appears at least once; extras cycle randomly
    profile_pool = PROFILES[:]
    extra = [random.choice(PROFILES) for _ in range(max(0, n - len(PROFILES)))]
    profile_cycle = (profile_pool + extra)[:n]
    random.shuffle(profile_cycle)

    print(f"\nGenerating {n} diverse invoice PDF(s) -> {OUTPUT_DIR}\n")

    start_date = datetime(2024, 1, 1)

    for i, profile in enumerate(profile_cycle, 1):
        hex_id   = uuid.uuid4().hex[:6]
        filename = f"invoice_{i:02d}_{hex_id}_{profile['name']}.pdf"

        inv_num  = f"INV-{random.randint(10000, 99999)}"
        inv_date = start_date + timedelta(days=random.randint(0, 365))
        date_str = inv_date.strftime("%d/%m/%Y")

        due_date_str = None
        if profile["has_due_date"]:
            if random.random() < 0.5:
                due_date_str = random.choice(["Net 15", "Net 30", "Net 60", "Net 90"])
            else:
                offset = random.randint(15, 90)
                due_date_str = (inv_date + timedelta(days=offset)).strftime("%d/%m/%Y")

        po_num       = f"PO-{random.randint(1000, 9999)}" if profile["has_po"] else None
        vendor       = random.choice(VENDORS)
        buyer        = random.choice(BUYERS)
        vendor_addr  = _rand_address()
        buyer_addr   = _rand_address()
        vendor_gstin = _rand_gstin() if profile["has_gstin"] else None
        vendor_pan   = _rand_pan()   if profile["has_pan"]   else None
        currency     = random.choice(profile["currencies"])

        items = [
            (
                random.choice(ITEM_DESCS),
                random.randint(1, 50),
                round(random.uniform(10.0, 5000.0), 2),
                random.choice(TAX_RATES),
            )
            for _ in range(random.randint(4, 10))
        ]

        build_invoice(
            filename, profile, inv_num, date_str, due_date_str, po_num,
            vendor, vendor_addr, vendor_gstin, vendor_pan,
            buyer, buyer_addr, items, currency,
        )

    print(f"\nDone. {n} PDFs written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
