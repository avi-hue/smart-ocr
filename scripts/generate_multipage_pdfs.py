"""
generate_multipage_pdfs.py
--------------------------
Creates structurally diverse multi-page PDF samples for testing the Smart-OCR pipeline.

Each PDF has a genuinely different:
  - Document type (Tax Invoice, Purchase Order, Vendor Statement, Credit Note, Pro Forma, ...)
  - Visual layout (two-column, centred, header-band, minimal, formal)
  - Field labels (e.g. "GSTIN" vs "GST Reg. No." vs "Tax ID", "Bill To" vs "Client" vs "Consignee")
  - Currency & locale (USD, EUR, GBP, INR)
  - Number of pages / line items

Run from the project root:
    python scripts/generate_multipage_pdfs.py
"""

import random
from pathlib import Path
from io import BytesIO

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import mm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, KeepTogether,
)
from reportlab.pdfgen.canvas import Canvas

# ── output ─────────────────────────────────────────────────────────────────────
OUT = Path("data/samples")
OUT.mkdir(parents=True, exist_ok=True)

styles = getSampleStyleSheet()

def h(size, bold=True, color=colors.black, align=TA_LEFT):
    return ParagraphStyle("custom", parent=styles["Normal"],
                          fontSize=size, fontName="Helvetica-Bold" if bold else "Helvetica",
                          textColor=color, alignment=align)

def para(txt, size=9, bold=False, color=colors.black, align=TA_LEFT):
    st = ParagraphStyle("p", parent=styles["Normal"],
                        fontSize=size, fontName="Helvetica-Bold" if bold else "Helvetica",
                        textColor=color, alignment=align, leading=size * 1.4)
    return Paragraph(txt, st)

def wrap(txt, size=8, align=TA_LEFT):
    st = ParagraphStyle('p', parent=styles['Normal'], fontSize=size, fontName='Helvetica', alignment=align)
    # ReportLab Paragraphs use <br/> for newlines
    txt = str(txt).replace('\n', '<br/>')
    return Paragraph(txt, st)

def money(amount, sym="$"):
    return f"{sym}{amount:,.2f}"

def rand_items(n, sym="$"):
    rows, total = [], 0
    for i in range(1, n + 1):
        qty  = random.randint(1, 100)
        rate = round(random.uniform(5, 800), 2)
        disc = random.choice([0, 0, 5, 10, 15])
        disc_amt = round(qty * rate * disc / 100, 2)
        line = round(qty * rate - disc_amt, 2)
        total += line
        rows.append((i, qty, rate, disc, disc_amt, line))
    return rows, round(total, 2)


# ══════════════════════════════════════════════════════════════════════════════
# PDF 1 ── Multi-page Indian Tax Invoice with GSTIN split across pages
# Layout: centred header band, two-column party block, itemised table
# ══════════════════════════════════════════════════════════════════════════════
def make_external_5(path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            topMargin=15*mm, bottomMargin=15*mm,
                            leftMargin=15*mm, rightMargin=15*mm)
    elems = []

    # Header band
    elems.append(para("KRISH TECHNOLOGIES PRIVATE LIMITED", 16, bold=True, align=TA_CENTER))
    elems.append(para("Plot 42, MIDC Industrial Area, Pune - 411018 | CIN: U72900MH2018PTC308142", 8, align=TA_CENTER, color=colors.grey))
    elems.append(para("GSTIN: 27AABCK5231M1ZV  |  PAN: AABCK5231M  |  Email: billing@krishtech.in", 8, align=TA_CENTER, color=colors.grey))
    elems.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1565C0")))
    elems.append(para("TAX INVOICE", 13, bold=True, color=colors.HexColor("#1565C0"), align=TA_CENTER))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elems.append(Spacer(1, 6))

    # Two-column meta
    meta = Table([
        [para("Invoice No:", 8, bold=True), para("KT/2026/INV/00842", 8),
         para("Invoice Date:", 8, bold=True), para("25-Jun-2026", 8)],
        [para("P.O. Reference:", 8, bold=True), para("PO-CUST-20260601", 8),
         para("Due Date:", 8, bold=True), para("25-Jul-2026", 8)],
        [para("Place of Supply:", 8, bold=True), para("Maharashtra (27)", 8),
         para("Payment Terms:", 8, bold=True), para("Net 30", 8)],
    ], colWidths=["18%","32%","18%","32%"])
    meta.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),2)]))
    elems += [meta, Spacer(1,8)]

    # Party block
    party = Table([
        [para("Bill To", 9, bold=True, color=colors.HexColor("#1565C0")),
         para("Ship To", 9, bold=True, color=colors.HexColor("#1565C0"))],
        [para("Reliance Retail Limited\n211, BKC Annex, Bandra East,\nMumbai - 400051\nGSTIN: 27AAKCS5588N1ZY\nContact: accounts@ril-retail.in", 8),
         para("Reliance DC Hub, Shed No. 7,\nNhava Sheva Logistics Park,\nNaviMumbai - 400707\nState Code: 27", 8)],
    ], colWidths=["50%","50%"])
    party.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.5,colors.lightgrey),
        ("INNERGRID",(0,0),(-1,-1),0.5,colors.lightgrey),
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E3F2FD")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    elems += [party, Spacer(1,10)]

    # Line items (enough to force 3+ pages)
    rows, subtotal = rand_items(180, sym="INR ")
    sym = "INR "
    hdr = ["Sr.", "Description / Particulars", "HSN/SAC", "Qty", "Unit Rate", "Disc. %", "Disc. Amt", "Line Total"]
    tdata = [hdr]
    for i, qty, rate, disc, disc_amt, line in rows:
        tdata.append([
            str(i),
            wrap(wrap(f"IT Service Component {i}\nRef: SOW-{2026+i}-{random.randint(100,999)}", 8), 8),
            f"{random.choice(['998314','998315','998316','998521'])}",
            str(qty),
            money(rate, sym),
            f"{disc}%",
            money(disc_amt, sym),
            money(line, sym),
        ])

    t = Table(tdata, repeatRows=1, colWidths=["4%","30%","9%","6%","11%","7%","10%","13%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1565C0")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7.5),
        ("ALIGN",(3,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#F5F5F5")]),
        ("GRID",(0,0),(-1,-1),0.4,colors.lightgrey),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("TOPPADDING",(0,1),(-1,-1),2),
    ]))
    elems += [t, Spacer(1,10)]

    cgst  = round(subtotal * 0.09, 2)
    sgst  = round(subtotal * 0.09, 2)
    grand = subtotal + cgst + sgst
    summary = Table([
        ["", para("Taxable Amount", 8, bold=True, align=TA_RIGHT), para(money(subtotal, sym), 8, align=TA_RIGHT)],
        ["", para("CGST @ 9%", 8, align=TA_RIGHT),   para(money(cgst, sym), 8, align=TA_RIGHT)],
        ["", para("SGST @ 9%", 8, align=TA_RIGHT),   para(money(sgst, sym), 8, align=TA_RIGHT)],
        ["", para("Grand Total", 9, bold=True, align=TA_RIGHT), para(money(grand, sym), 9, bold=True, align=TA_RIGHT)],
    ], colWidths=["60%","25%","15%"])
    summary.setStyle(TableStyle([
        ("LINEABOVE",(1,-1),(-1,-1),1,colors.black),
        ("TOPPADDING",(0,0),(-1,-1),3),
    ]))
    elems.append(summary)
    elems.append(Spacer(1,8))
    elems.append(para("Declaration: We declare that this invoice shows the actual price of the goods/services described and that all particulars are true and correct.", 7, color=colors.grey))
    elems.append(para("Bank Details: HDFC Bank | A/C: 50200012345678 | IFSC: HDFC0001234 | Branch: BKC Mumbai", 7, color=colors.grey))

    doc.build(elems)
    print(f"✓  {path.name}  ({len(rows)} items)")


# ══════════════════════════════════════════════════════════════════════════════
# PDF 2 ── US-style Commercial Invoice (minimalist, left-aligned, USD)
# Layout: simple left-column, no grid on header, condensed item table
# ══════════════════════════════════════════════════════════════════════════════
def make_external_6(path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)
    elems = []

    elems.append(para("MERIDIAN INDUSTRIAL SUPPLY CO.", 18, bold=True))
    elems.append(para("1200 Commerce Drive, Houston TX 77001  |  EIN: 74-2839021", 8, color=colors.grey))
    elems.append(Spacer(1, 10))
    elems.append(HRFlowable(width="100%", thickness=2, color=colors.black))
    elems.append(Spacer(1, 4))

    row1 = Table([[
        para("COMMERCIAL INVOICE", 14, bold=True),
        para(f"Invoice #: MIS-{random.randint(100000,999999)}", 9, align=TA_RIGHT),
    ]], colWidths=["60%","40%"])
    row1.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"BOTTOM")]))
    elems += [row1, Spacer(1,6)]

    meta = Table([
        [para("Date Issued:", 8, bold=True), para("June 25, 2026", 8),
         para("Payment Due:", 8, bold=True), para("July 25, 2026", 8)],
        [para("Terms:", 8, bold=True), para("Net 30", 8),
         para("Ship Via:", 8, bold=True), para("FedEx Freight Priority", 8)],
        [para("Sales Rep:", 8, bold=True), para("Jennifer L. Collins", 8),
         para("FOB:", 8, bold=True), para("Houston, TX", 8)],
    ], colWidths=["15%","35%","15%","35%"])
    meta.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),1),("VALIGN",(0,0),(-1,-1),"TOP")]))
    elems += [meta, Spacer(1,10)]

    party = Table([[
        para("SOLD TO:\nAcuity Manufacturing Inc.\n3840 N. Industrial Blvd\nDallas, TX 75207\nAttn: Procurement Dept", 8),
        para("SHIP TO:\nAcuity Manufacturing – Plant 3\n7200 S. Interstate 35\nAustin, TX 78744\nContact: warehouse@acuity.mfg", 8),
    ]], colWidths=["50%","50%"])
    party.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.75,colors.black),
        ("INNERGRID",(0,0),(-1,-1),0.75,colors.lightgrey),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    elems += [party, Spacer(1,10)]

    # Items
    rows, subtotal = rand_items(220)
    hdr = ["Item No.", "Part #", "Description", "Qty Ordered", "Unit Price", "Disc%", "Net Amount"]
    tdata = [hdr]
    for i, qty, rate, disc, disc_amt, line in rows:
        pn = f"MIS-{random.randint(10000,99999)}"
        tdata.append([str(i), pn, wrap(wrap(f"Industrial Component – Grade A – Spec {random.choice([\'4140\',\'4340\',\'304SS\',\'316SS\'])}", 8), 8), str(qty), f"${rate:.2f}", f"{disc}%", f"${line:,.2f}"])

    t = Table(tdata, repeatRows=1, colWidths=["7%","12%","31%","12%","11%","7%","13%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.black),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7.5),
        ("ALIGN",(3,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#EEEEEE")]),
        ("GRID",(0,0),(-1,-1),0.3,colors.grey),
    ]))
    elems += [t, Spacer(1,8)]

    freight = round(subtotal * 0.02, 2)
    tax     = round(subtotal * 0.0825, 2)
    total   = subtotal + freight + tax
    footer = Table([
        [para("Sub-Total", 8, bold=True, align=TA_RIGHT), para(f"${subtotal:,.2f}", 8, align=TA_RIGHT)],
        [para("Freight & Handling", 8, align=TA_RIGHT), para(f"${freight:,.2f}", 8, align=TA_RIGHT)],
        [para("TX State Tax (8.25%)", 8, align=TA_RIGHT), para(f"${tax:,.2f}", 8, align=TA_RIGHT)],
        [para("AMOUNT DUE (USD)", 9, bold=True, align=TA_RIGHT), para(f"${total:,.2f}", 9, bold=True, align=TA_RIGHT)],
    ], colWidths=["50%","50%"])
    footer.setStyle(TableStyle([("LINEABOVE",(0,-1),(-1,-1),1.5,colors.black),("TOPPADDING",(0,0),(-1,-1),3)]))
    elems.append(footer)
    elems.append(Spacer(1,8))
    elems.append(para("Remittance: Bank of America | ABA: 111000025 | Acct: 485920178433 | SWIFT: BOFAUS3N", 7, color=colors.grey))
    elems.append(para("Please reference the invoice number on all payments. Late payments subject to 1.5% monthly interest.", 7, color=colors.grey))

    doc.build(elems)
    print(f"✓  {path.name}  ({len(rows)} items)")


# ══════════════════════════════════════════════════════════════════════════════
# PDF 3 ── Australian Tax Invoice (AUD, ABN, GST)
# Layout: Standard formal layout with clear GST breakdown
# ══════════════════════════════════════════════════════════════════════════════
def make_external_7(path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            topMargin=20*mm, bottomMargin=15*mm,
                            leftMargin=20*mm, rightMargin=20*mm)
    elems = []

    header = Table([[
        para("SYDNEY HARBOUR SUPPLIES PTY LTD", 14, bold=True),
        para("ABN: 51 824 391 882\n100 George Street, Sydney NSW 2000\nPh: (02) 9876 5432", 8, align=TA_RIGHT, color=colors.grey),
    ]], colWidths=["50%","50%"])
    header.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")]))
    elems += [header, HRFlowable(width="100%", thickness=1.5, color=colors.black), Spacer(1,8)]

    elems.append(para("TAX INVOICE", 16, bold=True, color=colors.black))
    elems.append(Spacer(1,6))

    meta = Table([
        [para("Invoice Number:", 8, bold=True), para(f"INV-{random.randint(10000,99999)}", 8),
         para("Date of Issue:", 8, bold=True), para("25/06/2026", 8)],
        [para("Customer Ref:", 8, bold=True), para(f"PO-{random.randint(1000,9999)}", 8),
         para("Terms:", 8, bold=True), para("Net 14 Days", 8)],
    ], colWidths=["20%","30%","20%","30%"])
    meta.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),2),("VALIGN",(0,0),(-1,-1),"TOP")]))
    elems += [meta, Spacer(1,8)]

    elems.append(para("Bill To:", 8, bold=True))
    elems.append(para("Coastal Developments Group\nLevel 4, 150 Pacific Highway\nNorth Sydney NSW 2060\nAttention: Accounts Payable", 8))
    elems.append(Spacer(1,10))

    rows, subtotal = rand_items(160, sym="AUD ")
    sym = "AUD "
    hdr = ["Item", "Description", "Qty", "Unit Price", "GST", "Total Amount"]
    tdata = [hdr]
    for i, qty, rate, disc, disc_amt, line in rows:
        gst_amt = round(line * 0.10, 2)
        total_inc_gst = line + gst_amt
        tdata.append([
            str(i),
            wrap(f"Construction Material / Fitting Type {random.choice(['A','B','C','D'])} - Batch {random.randint(100,999)}", 8),
            str(qty),
            f"{rate:.2f} {sym}",
            f"{gst_amt:.2f} {sym}",
            f"{total_inc_gst:,.2f} {sym}",
        ])

    t = Table(tdata, repeatRows=1, colWidths=["8%","40%","10%","14%","14%","14%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#333333")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),8),
        ("ALIGN",(2,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#F5F5F5")]),
        ("GRID",(0,0),(-1,-1),0.5,colors.lightgrey),
        ("TOPPADDING",(0,1),(-1,-1),4),
        ("BOTTOMPADDING",(0,1),(-1,-1),4),
    ]))
    elems += [t, Spacer(1,8)]

    total_ex_gst = subtotal
    total_gst   = round(total_ex_gst * 0.10, 2)
    total_inc_gst = total_ex_gst + total_gst
    
    summ = Table([
        [para("Total Exclusive of GST:", 8, bold=True, align=TA_RIGHT), para(f"{total_ex_gst:,.2f} {sym}", 8, align=TA_RIGHT)],
        [para("Total GST (10%):", 8, align=TA_RIGHT), para(f"{total_gst:,.2f} {sym}", 8, align=TA_RIGHT)],
        [para("Total Amount Due:", 10, bold=True, align=TA_RIGHT), para(f"{total_inc_gst:,.2f} {sym}", 10, bold=True, align=TA_RIGHT)],
    ], colWidths=["70%","30%"])
    summ.setStyle(TableStyle([("LINEABOVE",(0,-1),(-1,-1),1.5,colors.black),("TOPPADDING",(0,0),(-1,-1),4)]))
    elems.append(summ)
    elems.append(Spacer(1,10))
    elems.append(para("Payment Details: Commonwealth Bank | BSB: 062-123 | Acct: 10293847", 7, color=colors.grey))

    doc.build(elems)
    print(f"✓  {path.name}  ({len(rows)} items)")


# ══════════════════════════════════════════════════════════════════════════════
# PDF 4 ── Freelancer / Consulting Invoice (no-table header, very simple layout)
# Layout: Plain prose blocks, no heavy tables, GBP
# ══════════════════════════════════════════════════════════════════════════════
def make_external_8(path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            topMargin=20*mm, bottomMargin=15*mm,
                            leftMargin=25*mm, rightMargin=25*mm)
    elems = []

    elems.append(para("INVOICE", 24, bold=True, align=TA_CENTER))
    elems.append(Spacer(1, 4))
    elems.append(para(f"Reference No: CONS-2026-{random.randint(100,999)}", 9, align=TA_CENTER, color=colors.grey))
    elems.append(Spacer(1, 14))

    party = Table([[
        para("From:\nMarcus Webb Consulting Ltd.\n14 Regent Street, London W1B 5TB\nCompany No: 12398745\nVAT Reg: GB 345 2819 12\nmarcus@webbconsulting.co.uk", 8),
        para("To:\nNovabridge Capital Partners\n30 St Mary Axe, London EC3A 8BF\nAccounts Payable: ap@novabridge.com\nClient Reference: NBC-20260580", 8, align=TA_RIGHT),
    ]], colWidths=["50%","50%"])
    party.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),0)]))
    elems += [party, Spacer(1,6)]
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elems.append(Spacer(1,6))

    dt = Table([
        [para("Invoice Date:", 8, bold=True), para("25 June 2026", 8)],
        [para("Service Period:", 8, bold=True), para("1 June 2026 – 25 June 2026", 8)],
        [para("Due Date:", 8, bold=True), para("25 July 2026 (30 days)", 8)],
        [para("Currency:", 8, bold=True), para("GBP (£)", 8)],
    ], colWidths=["35%","65%"])
    dt.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),1)]))
    elems += [dt, Spacer(1,10)]

    # Services (consulting-style — descriptions, hours, day rates)
    rows, subtotal = rand_items(140, sym="GBP ")
    sym = "GBP "
    hdr = ["#", "Service Description", "Days/Units", "Day Rate (£)", "Discount", "Amount (£)"]
    tdata = [hdr]
    services = ["Strategic Advisory", "Financial Modelling", "Regulatory Compliance Review", "Market Research",
                "Board Report Preparation", "Data Analytics Support", "Risk Assessment", "IT Architecture Review"]
    for i, qty, rate, disc, disc_amt, line in rows:
        tdata.append([str(i), wrap(wrap(f"{random.choice(services)} – Phase {i}", 8), 8), str(qty), f"£{rate:,.2f}", f"{disc}%", f"£{line:,.2f}"])

    t = Table(tdata, repeatRows=1, colWidths=["5%","40%","13%","14%","10%","14%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#37474F")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),8),
        ("ALIGN",(2,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#ECEFF1")]),
        ("LINEBELOW",(0,0),(-1,-1),0.3,colors.lightgrey),
    ]))
    elems += [t, Spacer(1,8)]

    vat = round(subtotal * 0.20, 2)
    total = subtotal + vat
    sf = Table([
        [para("Net Total:", 9, bold=True, align=TA_RIGHT), para(f"£{subtotal:,.2f}", 9, align=TA_RIGHT)],
        [para("VAT @ 20%:", 8, align=TA_RIGHT), para(f"£{vat:,.2f}", 8, align=TA_RIGHT)],
        [para("Total Due:", 10, bold=True, align=TA_RIGHT), para(f"£{total:,.2f}", 10, bold=True, align=TA_RIGHT)],
    ], colWidths=["75%","25%"])
    sf.setStyle(TableStyle([("LINEABOVE",(0,-1),(-1,-1),1.5,colors.black),("TOPPADDING",(0,0),(-1,-1),3)]))
    elems.append(sf)
    elems.append(Spacer(1,8))
    elems.append(para("Payment Method: BACS  |  Sort Code: 20-00-00  |  Account No: 53497812  |  Reference: CONS-2026-" + str(random.randint(100,999)), 7, color=colors.grey))
    elems.append(para("If payment is not received within 30 days, Late Payment Act 1998 interest charges will apply at 8% + Bank of England base rate.", 7, color=colors.grey))

    doc.build(elems)
    print(f"✓  {path.name}  ({len(rows)} items)")


# ══════════════════════════════════════════════════════════════════════════════
# PDF 5 ── Pharmaceutical Purchase Order / Vendor Invoice (India, complex GST)
# Layout: Formal letterhead, complex header table, multi-slab GST
# ══════════════════════════════════════════════════════════════════════════════
def make_external_9(path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            topMargin=15*mm, bottomMargin=15*mm,
                            leftMargin=18*mm, rightMargin=18*mm)
    elems = []

    elems.append(para("MEDILABS HEALTHCARE SOLUTIONS LLP", 15, bold=True, color=colors.HexColor("#1B5E20")))
    elems.append(para("Reg. Office: 88, Pharma City, Hyderabad – 500078  |  GSTIN: 36AAAFM0021G1ZS", 7.5, color=colors.grey))
    elems.append(para("Drug Licence: AP/20B/1234  |  FSSAI: 10022112001234  |  ISO 9001:2015 Certified", 7.5, color=colors.grey))
    elems.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1B5E20")))
    elems.append(para("GST TAX INVOICE – PHARMACEUTICAL", 12, bold=True, color=colors.HexColor("#1B5E20"), align=TA_CENTER))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elems.append(Spacer(1,6))

    # Header grid
    hg = Table([
        [para("Invoice No:", 8, bold=True), para(f"MHL/HYD/2026/{random.randint(1000,9999)}", 8),
         para("Invoice Date:", 8, bold=True), para("25/06/2026", 8),
         para("E-Invoice IRN:", 8, bold=True), para(f"{''.join(random.choices('ABCDEF0123456789',k=16))}", 7)],
        [para("Challan No:", 8, bold=True), para(f"CH-{random.randint(100,999)}", 8),
         para("PO Number:", 8, bold=True), para(f"PO-MHL-2026-{random.randint(10,99)}", 8),
         para("Vehicle No:", 8, bold=True), para(f"TS{random.randint(10,99)}AB{random.randint(1000,9999)}", 8)],
    ], colWidths=["12%","20%","12%","16%","14%","26%"])
    hg.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),2),("GRID",(0,0),(-1,-1),0.3,colors.lightgrey)]))
    elems += [hg, Spacer(1,6)]

    buyer = Table([[
        para("Consignee / Ship To:\nSree Balaji Medicals\n42, Jubilee Hills Road No. 10,\nHyderabad – 500033\nGSTIN: 36ABCBA1234F1ZZ\nDL No: TS/20B/04128", 8),
        para("Buyer / Bill To:\nSree Balaji Medicals\n42, Jubilee Hills Road No. 10,\nHyderabad – 500033\nGSTIN: 36ABCBA1234F1ZZ\nState: Telangana (36)", 8),
        para("Supplier / From:\nMediLabs Healthcare Solutions LLP\n88 Pharma City, Hyderabad – 500078\nGSTIN: 36AAAFM0021G1ZS\nPAN: AAAFM0021G", 8),
    ]], colWidths=["34%","33%","33%"])
    buyer.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.5,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.5,colors.lightgrey),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("TOPPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),4),
    ]))
    elems += [buyer, Spacer(1,8)]

    rows, subtotal = rand_items(170, sym="INR ")
    sym = "INR "
    hdr = ["S/N", "Product Name / Batch", "HSN", "Pack", "Qty", "MRP", "Rate", "GST%", "GST Amt", "Net Amt"]
    tdata = [hdr]
    products = ["Paracetamol 500mg", "Amoxicillin 250mg", "Metformin 500mg", "Atorvastatin 10mg",
                "Omeprazole 20mg", "Azithromycin 500mg", "Cetirizine 10mg", "Ibuprofen 400mg"]
    for i, qty, rate, disc, disc_amt, line in rows:
        gst_rate = random.choice([5, 12, 18])
        gst_amt  = round(line * gst_rate / 100, 2)
        net = line + gst_amt
        tdata.append([
            str(i),
            wrap(wrap(f"{random.choice(products)}\nBatch: {random.choice(\'ABCDE\')}{random.randint(10,99)}26", 8), 8),
            "30049099",
            f"{random.randint(1,10)}x{random.choice([10,15,30])}",
            str(qty),
            money(rate * 1.3, sym),
            money(rate, sym),
            f"{gst_rate}%",
            money(gst_amt, sym),
            money(net, sym),
        ])

    t = Table(tdata, repeatRows=1, colWidths=["4%","24%","7%","5%","5%","8%","8%","6%","8%","13%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1B5E20")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7),
        ("ALIGN",(4,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F1F8F1")]),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#C8E6C9")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("TOPPADDING",(0,1),(-1,-1),2),
    ]))
    elems += [t, Spacer(1,8)]

    total_gst = round(subtotal * 0.12, 2)
    grand = subtotal + total_gst
    sm = Table([
        ["", para("Total Taxable Value:", 8, bold=True, align=TA_RIGHT), para(money(subtotal, sym), 8, align=TA_RIGHT)],
        ["", para("Total CGST:", 8, align=TA_RIGHT), para(money(total_gst/2, sym), 8, align=TA_RIGHT)],
        ["", para("Total SGST:", 8, align=TA_RIGHT), para(money(total_gst/2, sym), 8, align=TA_RIGHT)],
        ["", para("Total Invoice Value:", 9, bold=True, align=TA_RIGHT), para(money(grand, sym), 9, bold=True, align=TA_RIGHT)],
    ], colWidths=["55%","30%","15%"])
    sm.setStyle(TableStyle([("LINEABOVE",(1,-1),(-1,-1),1,colors.black),("TOPPADDING",(0,0),(-1,-1),2)]))
    elems.append(sm)
    elems.append(Spacer(1,6))
    elems.append(para("This is a computer generated invoice. Subject to Hyderabad Jurisdiction.", 7, color=colors.grey))

    doc.build(elems)
    print(f"✓  {path.name}  ({len(rows)} items)")


# ══════════════════════════════════════════════════════════════════════════════
# PDF 6 ── SaaS / Software Subscription Invoice (minimal, bold brand colour)
# Layout: Brand-coloured top strip, right-aligned totals, simple item table
# Field labels: "Account", "Plan", "Billing Period", not typical invoice fields
# ══════════════════════════════════════════════════════════════════════════════
def make_invoice_complex_a(path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            topMargin=0.5*inch, bottomMargin=0.75*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)
    elems = []

    # Brand strip
    strip = Table([[para("  NEXUS CLOUD PLATFORM", 14, bold=True, color=colors.white), para(f"Invoice  #NCL-{random.randint(10000,99999)}", 10, color=colors.white, align=TA_RIGHT)]],
                  colWidths=["60%","40%"])
    strip.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#4A00E0")),
        ("TOPPADDING",(0,0),(-1,-1),10),
        ("BOTTOMPADDING",(0,0),(-1,-1),10),
        ("LEFTPADDING",(0,0),(-1,-1),12),
    ]))
    elems += [strip, Spacer(1,12)]

    info = Table([[
        para("BILLED TO:\nAlpha Dynamics Pte. Ltd.\n10 Marina Boulevard, #22-01\nSingapore 018983\naccts@alphadynamics.sg", 8),
        para(f"Account ID: AD-00281-SG\nBilling Period: Jun 1 – Jun 30 2026\nIssue Date: 25 Jun 2026\nDue Date: 10 Jul 2026\nPO Ref: PO-AD-20260601", 8, align=TA_RIGHT),
    ]], colWidths=["50%","50%"])
    info.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")]))
    elems += [info, Spacer(1,10), HRFlowable(width="100%",thickness=0.5,color=colors.lightgrey), Spacer(1,8)]

    rows, subtotal = rand_items(120)
    hdr = ["#", "Plan / Feature", "SKU", "Quantity (Seats/Units)", "Unit Price (USD)", "Total (USD)"]
    plans = ["Professional Seat License", "Enterprise API Calls – Block of 1M",
             "Data Storage – 100GB Block", "Premium Support SLA",
             "Advanced Analytics Module", "Single Sign-On Addon",
             "Dedicated Infrastructure Unit", "Compliance Vault Module"]
    tdata = [hdr]
    for i, qty, rate, disc, disc_amt, line in rows:
        tdata.append([str(i), wrap(wrap(random.choice(plans), 8), 8), f"SKU-{random.randint(1000,9999)}", str(qty), f"${rate:.2f}", f"${line:,.2f}"])

    t = Table(tdata, repeatRows=1, colWidths=["4%","35%","12%","18%","15%","14%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#4A00E0")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),8),
        ("ALIGN",(3,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F3F0FF")]),
        ("LINEBELOW",(0,0),(-1,-1),0.3,colors.HexColor("#D0C4FF")),
    ]))
    elems += [t, Spacer(1,8)]

    gst = round(subtotal * 0.09, 2)  # Singapore GST 9%
    total = subtotal + gst
    sf = Table([
        [para("Subtotal:", 8, bold=True, align=TA_RIGHT), para(f"${subtotal:,.2f}", 8, align=TA_RIGHT)],
        [para("Singapore GST (9%):", 8, align=TA_RIGHT), para(f"${gst:,.2f}", 8, align=TA_RIGHT)],
        [para("Total Amount Due (USD):", 10, bold=True, align=TA_RIGHT), para(f"${total:,.2f}", 10, bold=True, align=TA_RIGHT)],
    ], colWidths=["75%","25%"])
    sf.setStyle(TableStyle([("LINEABOVE",(0,-1),(-1,-1),2,colors.HexColor("#4A00E0")),("TOPPADDING",(0,0),(-1,-1),4)]))
    elems.append(sf)
    elems.append(Spacer(1,8))
    elems.append(para("Payment: Stripe  |  Credit Card on file ending ****4821 will be charged on the due date.", 7, color=colors.grey))
    elems.append(para("Questions? billing@nexuscloud.io  |  Nexus Cloud Pte. Ltd., 1 Fusionopolis Way, Singapore 138632", 7, color=colors.grey))

    doc.build(elems)
    print(f"✓  {path.name}  ({len(rows)} items)")


# ══════════════════════════════════════════════════════════════════════════════
# PDF 7 ── Construction / Contractor Invoice (progress billing, milestone-based)
# Layout: Wide table, milestone sections, retention deduction
# ══════════════════════════════════════════════════════════════════════════════
def make_invoice_complex_b(path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            topMargin=0.75*inch, bottomMargin=0.75*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)
    elems = []

    elems.append(para("STERLING CONSTRUCTION GROUP", 16, bold=True))
    elems.append(para("License #: CA-B-1-850234  |  Bond: Hartford Casualty  |  Ins: GL/WC Current", 8, color=colors.grey))
    elems.append(Spacer(1,4))
    elems.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#E65100")))
    elems.append(para("PROGRESS PAYMENT INVOICE", 13, bold=True, color=colors.HexColor("#E65100")))
    elems.append(Spacer(1,6))

    hdr_info = Table([
        [para("Invoice No:", 8, bold=True), para(f"SCG-PROG-{random.randint(100,999)}", 8),
         para("Invoice Date:", 8, bold=True), para("June 25, 2026", 8)],
        [para("Project Name:", 8, bold=True), para("Lakeview Corporate Campus – Phase 2", 8),
         para("Project No:", 8, bold=True), para(f"PRJ-{random.randint(1000,9999)}", 8)],
        [para("Contract Amount:", 8, bold=True), para(f"${random.randint(2000000,9000000):,}.00", 8),
         para("Application #:", 8, bold=True), para(str(random.randint(4,18)), 8)],
        [para("Period Covered:", 8, bold=True), para("June 1 – June 25, 2026", 8),
         para("Retainage:", 8, bold=True), para("10% per contract", 8)],
    ], colWidths=["16%","34%","16%","34%"])
    hdr_info.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),2),("VALIGN",(0,0),(-1,-1),"TOP")]))
    elems += [hdr_info, Spacer(1,6)]

    party = Table([[
        para("FROM (Contractor):\nSterling Construction Group\n4800 N. Industrial Park Way\nSacramento, CA 95811\nFEIN: 91-4382019", 8),
        para("TO (Owner / GC):\nPacific Bay Development LLC\n600 California Street, Ste 1800\nSan Francisco, CA 94108\nAttn: Project Accounting", 8),
    ]], colWidths=["50%","50%"])
    party.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.75,colors.black),
        ("INNERGRID",(0,0),(-1,-1),0.75,colors.lightgrey),
        ("TOPPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),5),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    elems += [party, Spacer(1,10)]

    rows, subtotal = rand_items(200)
    divisions = ["02 – Sitework", "03 – Concrete", "04 – Masonry", "05 – Metals",
                 "06 – Wood/Plastics", "07 – Thermal/Moisture", "08 – Doors/Windows",
                 "09 – Finishes", "10 – Specialties", "15 – Mechanical", "16 – Electrical"]
    hdr_cols = ["Item", "CSI Division", "Description of Work", "Scheduled Value", "Previous Billing", "This Period", "% Complete", "Balance to Finish"]
    tdata = [hdr_cols]
    for i, qty, rate, disc, disc_amt, line in rows:
        sv = round(qty * rate * random.uniform(3, 10), 2)
        prev = round(sv * random.uniform(0.1, 0.7), 2)
        this = round(sv * random.uniform(0, 0.2), 2)
        pct = round((prev + this) / sv * 100, 1)
        bal = round(sv - prev - this, 2)
        tdata.append([
            str(i),
            random.choice(divisions),
            wrap(wrap(f"Work Item {i} – {random.choice([\'Labor\',\'Material\',\'Equipment\',\'Subcontract\'])}", 8), 8),
            f"${sv:,.2f}",
            f"${prev:,.2f}",
            f"${this:,.2f}",
            f"{pct}%",
            f"${bal:,.2f}",
        ])

    t = Table(tdata, repeatRows=1, colWidths=["4%","13%","25%","12%","12%","10%","9%","12%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E65100")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7),
        ("ALIGN",(3,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#FFF3E0")]),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#FFCC80")),
        ("TOPPADDING",(0,1),(-1,-1),2),
    ]))
    elems += [t, Spacer(1,8)]

    retention = round(subtotal * 0.10, 2)
    net_due = subtotal - retention
    sf = Table([
        [para("Gross Amount This Application:", 8, bold=True, align=TA_RIGHT), para(f"${subtotal:,.2f}", 8, align=TA_RIGHT)],
        [para("Less: Retainage (10%):", 8, align=TA_RIGHT), para(f"(${retention:,.2f})", 8, align=TA_RIGHT)],
        [para("NET AMOUNT DUE:", 10, bold=True, align=TA_RIGHT), para(f"${net_due:,.2f}", 10, bold=True, align=TA_RIGHT)],
    ], colWidths=["75%","25%"])
    sf.setStyle(TableStyle([("LINEABOVE",(0,-1),(-1,-1),2,colors.black),("TOPPADDING",(0,0),(-1,-1),4)]))
    elems.append(sf)
    elems.append(Spacer(1,6))
    elems.append(para("Contractor Certification: The undersigned Contractor certifies that to the best of Contractor's knowledge the work covered by this Application has been completed in accordance with the Contract Documents.", 7, color=colors.grey))

    doc.build(elems)
    print(f"✓  {path.name}  ({len(rows)} items)")


# ══════════════════════════════════════════════════════════════════════════════
# PDF 8 ── Logistics / Freight Invoice (carrier-style, weight/dimension data)
# ══════════════════════════════════════════════════════════════════════════════
def make_invoice_complex_c(path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            topMargin=0.5*inch, bottomMargin=0.5*inch,
                            leftMargin=0.6*inch, rightMargin=0.6*inch)
    elems = []

    elems.append(Table([[
        para("ATLAS GLOBAL LOGISTICS", 14, bold=True, color=colors.white),
        para(f"Pro #: AGL-{random.randint(100000,999999)}\nInvoice Date: Jun 25 2026", 8, color=colors.white, align=TA_RIGHT),
    ]], colWidths=["60%","40%"]))
    elems[-1].setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#0D47A1")),
                                    ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
                                    ("LEFTPADDING",(0,0),(-1,-1),10)]))
    elems.append(Spacer(1,8))

    party = Table([[
        para("Shipper / Origin:\nTechGear International Ltd.\n1800 Harbour Road, Kwai Chung\nHong Kong SAR\nContact: shipping@techgearintl.hk", 8),
        para("Consignee / Destination:\nBest Buy Distribution Center\n7601 Penn Ave South\nRichfield, MN 55423 USA\nNOTIFY: logistics@bestbuy.com", 8),
        para(f"Bill To / 3rd Party:\nFreight Broker Solutions Inc.\n400 N Michigan Ave, Chicago IL 60611\nAcct: FBS-{random.randint(10000,99999)}", 8),
    ]], colWidths=["34%","33%","33%"])
    party.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,colors.grey),
                                ("INNERGRID",(0,0),(-1,-1),0.5,colors.lightgrey),
                                ("TOPPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),4),
                                ("VALIGN",(0,0),(-1,-1),"TOP")]))
    elems += [party, Spacer(1,6)]

    ship_info = Table([
        [para("Mode of Transport:", 8, bold=True), para("FCL Ocean + Domestic Truck", 8),
         para("Vessel / Voyage:", 8, bold=True), para(f"MSC Catalina V.{random.randint(100,999)}W", 8)],
        [para("Port of Loading:", 8, bold=True), para("Hong Kong (HKHKG)", 8),
         para("Port of Discharge:", 8, bold=True), para("Los Angeles (USLAX)", 8)],
        [para("ETD:", 8, bold=True), para("02 Jun 2026", 8),
         para("ETA:", 8, bold=True), para("25 Jun 2026", 8)],
        [para("Incoterms:", 8, bold=True), para("CIF Los Angeles", 8),
         para("Currency:", 8, bold=True), para("USD", 8)],
    ], colWidths=["16%","34%","16%","34%"])
    ship_info.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),2),("GRID",(0,0),(-1,-1),0.3,colors.lightgrey)]))
    elems += [ship_info, Spacer(1,8)]

    rows, subtotal = rand_items(150)
    hdr = ["#", "Charge Description", "Container/Ref #", "Weight (KG)", "Volume (CBM)", "Rate (USD)", "Amount (USD)"]
    tdata = [hdr]
    charges = ["Ocean Freight", "Port Handling (Origin)", "Port Handling (Destination)", "Documentation Fee",
               "Customs Clearance", "Inland Truck Delivery", "Terminal Handling", "Peak Season Surcharge",
               "Fuel Surcharge (BAF)", "Security Surcharge (CAF)", "Telex Release Fee", "ISF Filing Fee"]
    for i, qty, rate, disc, disc_amt, line in rows:
        wt = round(qty * random.uniform(10, 500), 1)
        vol = round(qty * random.uniform(0.1, 2.0), 3)
        tdata.append([str(i), wrap(wrap(random.choice(charges), 8), 8), f"TGIU{random.randint(1000000,9999999)}", str(wt), str(vol), f"${rate:.2f}", f"${line:,.2f}"])

    t = Table(tdata, repeatRows=1, colWidths=["4%","26%","15%","11%","11%","11%","14%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#0D47A1")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7.5),
        ("ALIGN",(3,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#E8EAF6")]),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#9FA8DA")),
    ]))
    elems += [t, Spacer(1,8)]

    sf = Table([
        [para("Total Charges (USD):", 9, bold=True, align=TA_RIGHT), para(f"${subtotal:,.2f}", 9, bold=True, align=TA_RIGHT)],
        [para("Advance Paid:", 8, align=TA_RIGHT), para(f"(${round(subtotal*0.3,2):,.2f})", 8, align=TA_RIGHT)],
        [para("BALANCE DUE:", 10, bold=True, align=TA_RIGHT), para(f"${round(subtotal*0.7,2):,.2f}", 10, bold=True, align=TA_RIGHT)],
    ], colWidths=["75%","25%"])
    sf.setStyle(TableStyle([("LINEABOVE",(0,-1),(-1,-1),2,colors.HexColor("#0D47A1")),("TOPPADDING",(0,0),(-1,-1),3)]))
    elems.append(sf)
    elems.append(Spacer(1,6))
    elems.append(para("Wire Transfer: Citibank N.A. | ABA: 021000089 | Acct: 40620012883 | Beneficiary: Atlas Global Logistics Inc. | Ref: Pro#", 7, color=colors.grey))

    doc.build(elems)
    print(f"✓  {path.name}  ({len(rows)} items)")


# ══════════════════════════════════════════════════════════════════════════════
# PDF 9 ── Advertising / Media Agency Invoice (project-based billing, AED)
# ══════════════════════════════════════════════════════════════════════════════
def make_invoice_complex_d(path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            topMargin=15*mm, bottomMargin=15*mm,
                            leftMargin=20*mm, rightMargin=20*mm)
    elems = []

    elems.append(para("CANVAS MEDIA GROUP", 18, bold=True, color=colors.HexColor("#880E4F")))
    elems.append(para("Dubai Media City, Building 8, Suite 402, Dubai UAE  |  TRN: 100295863100003", 8, color=colors.grey))
    elems.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#880E4F")))
    elems.append(Spacer(1,6))

    meta = Table([[
        para(f"INVOICE No: CMG/DXB/{random.randint(1000,9999)}/2026\nDate: 25 June 2026\nDue: 25 July 2026\nClient PO: PO-EMARAT-2026-0043", 9),
        para("Client:\nEMIRATES NATIONAL OIL COMPANY\nCorps Road, Oud Metha, Dubai UAE\nTRN: 100012345600003\nAttn: Marketing Finance Team", 9, align=TA_RIGHT),
    ]], colWidths=["50%","50%"])
    meta.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")]))
    elems += [meta, Spacer(1,8), HRFlowable(width="100%",thickness=0.5,color=colors.lightgrey), Spacer(1,6)]

    rows, subtotal = rand_items(130, sym="AED ")
    sym = "AED "
    hdr = ["#", "Campaign / Deliverable", "Platform", "Duration", "Units", "Rate (AED)", "Amount (AED)"]
    platforms = ["Instagram", "TikTok", "Google Display", "YouTube Pre-Roll", "LinkedIn Sponsored",
                 "Facebook Carousel", "OOH Billboard – SZR", "Arabic TV Spot (30s)", "Radio – Dubai Eye 103.8"]
    tdata = [hdr]
    for i, qty, rate, disc, disc_amt, line in rows:
        tdata.append([str(i), wrap(wrap(f"Campaign Deliverable – {i:03d}", 8), 8), random.choice(platforms), f"{random.randint(7,90)} days", str(qty), money(rate, sym), money(line, sym)])

    t = Table(tdata, repeatRows=1, colWidths=["4%","30%","16%","11%","8%","14%","14%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#880E4F")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),8),
        ("ALIGN",(4,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#FCE4EC")]),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#F48FB1")),
    ]))
    elems += [t, Spacer(1,8)]

    vat = round(subtotal * 0.05, 2)
    total = subtotal + vat
    sf = Table([
        [para("Sub-Total:", 8, bold=True, align=TA_RIGHT), para(money(subtotal, sym), 8, align=TA_RIGHT)],
        [para("UAE VAT (5%):", 8, align=TA_RIGHT), para(money(vat, sym), 8, align=TA_RIGHT)],
        [para("Total Amount Due:", 10, bold=True, align=TA_RIGHT), para(money(total, sym), 10, bold=True, align=TA_RIGHT)],
    ], colWidths=["70%","30%"])
    sf.setStyle(TableStyle([("LINEABOVE",(0,-1),(-1,-1),2,colors.HexColor("#880E4F")),("TOPPADDING",(0,0),(-1,-1),4)]))
    elems.append(sf)
    elems.append(Spacer(1,6))
    elems.append(para("Bank: Emirates NBD  |  IBAN: AE070260001015077288001  |  SWIFT: EBILAEAD  |  Ref: Invoice Number", 7, color=colors.grey))

    doc.build(elems)
    print(f"✓  {path.name}  ({len(rows)} items)")


# ══════════════════════════════════════════════════════════════════════════════
# PDF 10 ── Credit Note / Debit Memo (reversal document, negative amounts)
# ══════════════════════════════════════════════════════════════════════════════
def make_invoice_complex_e(path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            topMargin=15*mm, bottomMargin=15*mm,
                            leftMargin=18*mm, rightMargin=18*mm)
    elems = []

    elems.append(para("CREDIT NOTE", 20, bold=True, color=colors.HexColor("#B71C1C"), align=TA_CENTER))
    elems.append(para("This document is not an invoice — it is a Credit Note issued as a partial reversal", 8, color=colors.grey, align=TA_CENTER))
    elems.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#B71C1C")))
    elems.append(Spacer(1,6))

    meta = Table([
        [para("Credit Note No:", 8, bold=True), para(f"CN-{random.randint(10000,99999)}", 8),
         para("Original Invoice:", 8, bold=True), para(f"INV-{random.randint(10000,99999)}", 8)],
        [para("Issue Date:", 8, bold=True), para("25 June 2026", 8),
         para("Original Inv. Date:", 8, bold=True), para("15 May 2026", 8)],
        [para("Reason Code:", 8, bold=True), para("RET-003 – Goods Returned / Defective", 8),
         para("Vendor Code:", 8, bold=True), para(f"VND-{random.randint(1000,9999)}", 8)],
    ], colWidths=["18%","32%","18%","32%"])
    meta.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),2),("GRID",(0,0),(-1,-1),0.3,colors.lightgrey)]))
    elems += [meta, Spacer(1,6)]

    party = Table([[
        para("Issued By:\nPinnacle Electronics Wholesale\n23 Tech Hub, Bengaluru – 560100\nGSTIN: 29AAHCP0123A1ZA", 8),
        para("Issued To:\nZoom Retail Chain Ltd.\n5th Floor, Tower B, Connaught Place,\nNew Delhi – 110001\nGSTIN: 07AABCZ1234F1ZY", 8),
    ]], colWidths=["50%","50%"])
    party.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,colors.grey),("INNERGRID",(0,0),(-1,-1),0.5,colors.lightgrey),
                                ("TOPPADDING",(0,0),(-1,-1),4),("VALIGN",(0,0),(-1,-1),"TOP")]))
    elems += [party, Spacer(1,8)]

    rows, subtotal = rand_items(160, sym="INR ")
    sym = "INR "
    hdr = ["Sl.", "Original Inv. Line", "HSN Code", "Description of Goods Returned", "Qty Returned", "Unit Value", "Credit Amount"]
    tdata = [hdr]
    for i, qty, rate, disc, disc_amt, line in rows:
        tdata.append([str(i), f"Line {i:03d}", f"{random.randint(80000000,99999999)}",
                      f"Electronics Component – SKU {random.randint(10000,99999)}", str(qty), money(rate, sym), f"({money(line, sym)})"])

    t = Table(tdata, repeatRows=1, colWidths=["4%","12%","9%","33%","10%","12%","14%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#B71C1C")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7.5),
        ("ALIGN",(4,0),(-1,-1),"RIGHT"),
        ("TEXTCOLOR",(6,1),(-1,-1),colors.HexColor("#B71C1C")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#FFEBEE")]),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#FFCDD2")),
    ]))
    elems += [t, Spacer(1,8)]

    igst = round(subtotal * 0.18, 2)
    total = subtotal + igst
    sf = Table([
        [para("Total Taxable Credit:", 8, bold=True, align=TA_RIGHT), para(f"({money(subtotal, sym)})", 8, color=colors.HexColor("#B71C1C"), align=TA_RIGHT)],
        [para("IGST @ 18%:", 8, align=TA_RIGHT), para(f"({money(igst, sym)})", 8, color=colors.HexColor("#B71C1C"), align=TA_RIGHT)],
        [para("TOTAL CREDIT:", 10, bold=True, align=TA_RIGHT), para(f"({money(total, sym)})", 10, bold=True, color=colors.HexColor("#B71C1C"), align=TA_RIGHT)],
    ], colWidths=["70%","30%"])
    sf.setStyle(TableStyle([("LINEABOVE",(0,-1),(-1,-1),2,colors.HexColor("#B71C1C")),("TOPPADDING",(0,0),(-1,-1),4)]))
    elems.append(sf)
    elems.append(Spacer(1,6))
    elems.append(para("This credit will be adjusted against your next invoice or may be claimed as refund. Ref: GST Rule 53(3).", 7, color=colors.grey))

    doc.build(elems)
    print(f"✓  {path.name}  ({len(rows)} items)")


# ══════════════════════════════════════════════════════════════════════════════
# Run all generators
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=== Generating structurally diverse test PDFs ===\n")
    
    def try_make(func, path):
        try:
            func(path)
        except PermissionError:
            new_path = path.with_name(path.stem + "_updated" + path.suffix)
            print(f"Warning: {path.name} is locked, writing to {new_path.name} instead.")
            func(new_path)

    try_make(make_external_5, OUT / "external_5.pdf")
    try_make(make_external_6, OUT / "external_6.pdf")
    try_make(make_external_7, OUT / "external_7.pdf")
    try_make(make_external_8, OUT / "external_8.pdf")
    try_make(make_external_9, OUT / "external_9.pdf")
    print()
    try_make(make_invoice_complex_a, OUT / "invoice_complex_a_saas.pdf")
    try_make(make_invoice_complex_b, OUT / "invoice_complex_b_construction.pdf")
    try_make(make_invoice_complex_c, OUT / "invoice_complex_c_logistics.pdf")
    try_make(make_invoice_complex_d, OUT / "invoice_complex_d_media.pdf")
    try_make(make_invoice_complex_e, OUT / "invoice_complex_e_credit_note.pdf")
    print("\n=== All PDFs generated in data/samples/ ===")
