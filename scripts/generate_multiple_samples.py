"""
generate_multiple_samples.py – Generates 5 sample text-based invoice PDFs for testing.
"""

from pathlib import Path
import sys
import random

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


def _random_gstin():
    """Generate a random but validly-formatted GSTIN (15 chars)."""
    state_code = str(random.randint(1, 35)).zfill(2)
    pan        = _random_pan()
    entity     = random.choice("123456789")
    check      = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    return f"{state_code}{pan}{entity}Z{check}"


def _random_pan():
    """Generate a random but validly-formatted PAN (10 chars)."""
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    pan = (
        ''.join(random.choices(letters, k=5))
        + str(random.randint(1000, 9999))
        + random.choice(letters)
    )
    return pan


def build_invoice(filename, inv_num, date_str, due_date_str, po_num,
                  vendor, vendor_addr, vendor_gstin, vendor_pan,
                  buyer, buyer_addr, items, currency):
    doc = SimpleDocTemplate(str(OUTPUT_DIR / filename), pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    bold   = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10)
    normal = styles["Normal"]
    h1     = ParagraphStyle("h1", parent=styles["Title"], fontSize=20, textColor=colors.HexColor("#1F4E79"))
    
    story = []
    story.append(Paragraph("TAX INVOICE", h1))
    story.append(Spacer(1, 0.3*cm))

    # Meta
    meta = [
        ["Invoice No.:", inv_num, "PO Number:", po_num],
        ["Invoice Date:", date_str, "Due Date:", due_date_str],
    ]
    meta_table = Table(meta, colWidths=[2.5*cm, 4*cm, 2.5*cm, 4*cm], hAlign='LEFT')
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.5*cm))

    # Parties
    party = [
        ["Bill From:", "Bill To:"],
        [vendor, buyer],
        [vendor_addr, buyer_addr],
        [f"GSTIN: {vendor_gstin}\nPAN: {vendor_pan}", ""]
    ]
    party_table = Table(party, colWidths=[8*cm, 8*cm], hAlign='LEFT')
    party_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
    ]))
    story.append(party_table)
    story.append(Spacer(1, 0.5*cm))

    # Items
    header = ["Sr. No.", "Description", "HSN/SAC", "Qty", f"Unit Price ({currency})", "Tax Rate", f"Tax Amt ({currency})", f"Total ({currency})"]
    data = [header]
    subtotal = 0
    total_tax = 0
    
    for idx, item in enumerate(items, 1):
        desc, qty, price, tax_rate = item
        tax_amt = qty * price * (tax_rate / 100)
        line_total = (qty * price) + tax_amt
        
        subtotal += (qty * price)
        total_tax += tax_amt
        
        data.append([
            str(idx), desc, "9987", str(qty), f"{price:.2f}", f"{tax_rate}%", f"{tax_amt:.2f}", f"{line_total:.2f}"
        ])
        
    grand_total = subtotal + total_tax
    
    item_table = Table(data, colWidths=[1.5*cm, 5*cm, 2*cm, 1.2*cm, 2.5*cm, 1.8*cm, 2.5*cm, 2.5*cm])
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0,0), (-1,0), 8),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    story.append(item_table)
    story.append(Spacer(1, 0.5*cm))

    # Totals
    totals = [
        ["Subtotal:", f"{currency} {subtotal:,.2f}"],
        ["GST (18%/12%):", f"{currency} {total_tax:,.2f}"],
        ["Grand Total:", f"{currency} {grand_total:,.2f}"],
    ]
    totals_table = Table(totals, colWidths=[14*cm, 3.5*cm])
    totals_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "RIGHT"),
        ("LINEABOVE", (0,-1), (-1,-1), 1, colors.black),
    ]))
    story.append(totals_table)
    
    doc.build(story)
    print(f"Created: {filename}")

if __name__ == "__main__":
    import uuid
    from datetime import datetime, timedelta

    vendors = ["Acme Corp", "Globex Inc", "Soylent Corp", "Initech", "Massive Dynamic", "Cyberdyne", "Umbrella Corp"]
    buyers = ["Wayne Enterprises", "Stark Industries", "Oscorp", "LexCorp", "Daily Planet", "Goliath National Bank"]
    items_list = ["Widgets", "Gadgets", "Server Hosting", "Consulting", "Travel", "Software License", "Maintenance", "Cloud Storage"]
    currencies = ["$", "₹", "€", "£"]

    streets   = ["Main St", "Park Ave", "Oak Rd", "Market Blvd", "Lake Dr", "Hill Rd"]
    cities    = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Pune", "Kolkata"]
    states    = ["MH", "DL", "KA", "TN", "TS", "GJ", "WB"]

    num_samples = 5
    for i in range(1, num_samples + 1):
        filename = f"random_invoice_{i:02d}_{uuid.uuid4().hex[:6]}.pdf"
        inv_num = f"INV-{random.randint(10000, 99999)}"

        # Random invoice date in 2024
        start_date = datetime(2024, 1, 1)
        random_days = random.randint(0, 365)
        inv_date = start_date + timedelta(days=random_days)
        date_str = inv_date.strftime("%d/%m/%Y")

        # Randomly pick between a Net payment term OR a real due date
        if random.random() < 0.5:
            due_date_str = random.choice(["Net 15", "Net 30", "Net 60", "Net 90"])
        else:
            due_offset = random.randint(15, 90)
            due_date_str = (inv_date + timedelta(days=due_offset)).strftime("%d/%m/%Y")

        po_num = f"PO-{random.randint(1000, 9999)}"
        vendor = random.choice(vendors)
        buyer  = random.choice(buyers)
        currency = random.choice(currencies)

        # Unique addresses, GSTIN, PAN per invoice
        vendor_addr = f"{random.randint(1, 999)} {random.choice(streets)}, {random.choice(cities)}, {random.choice(states)} {random.randint(100000, 999999)}"
        buyer_addr  = f"{random.randint(1, 999)} {random.choice(streets)}, {random.choice(cities)}, {random.choice(states)} {random.randint(100000, 999999)}"
        vendor_gstin = _random_gstin()
        vendor_pan   = _random_pan()

        # Random items (30 to 40 items)
        items = []
        for _ in range(random.randint(30, 40)):
            desc = random.choice(items_list)
            qty  = random.randint(1, 50)
            price = round(random.uniform(10.0, 5000.0), 2)
            tax_rate = random.choice([5, 12, 18, 28])
            items.append((desc, qty, price, tax_rate))

        build_invoice(filename, inv_num, date_str, due_date_str, po_num,
                      vendor, vendor_addr, vendor_gstin, vendor_pan,
                      buyer, buyer_addr, items, currency)
