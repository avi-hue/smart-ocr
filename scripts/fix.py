import re
from pathlib import Path

file_path = Path('scripts/generate_multipage_pdfs.py')
code = file_path.read_text(encoding='utf-8')

# 1. Fix currency symbols globally
code = code.replace('sym="₹"', 'sym="INR "')
code = code.replace('sym="€"', 'sym="EUR "')
code = code.replace('sym="£"', 'sym="GBP "')
code = code.replace('"₹"', '"INR "')
code = code.replace('"€"', '"EUR "')
code = code.replace('"£"', '"GBP "')

# 2. Add wrap function
if "def wrap(" not in code:
    code = code.replace(
        "def money(amount, sym=\"$\"):", 
        "def wrap(txt, size=8, align=TA_LEFT):\n    st = ParagraphStyle('p', parent=styles['Normal'], fontSize=size, fontName='Helvetica', alignment=align)\n    # ReportLab Paragraphs use <br/> for newlines\n    txt = str(txt).replace('\\n', '<br/>')\n    return Paragraph(txt, st)\n\ndef money(amount, sym=\"$\"):"
    )

# 3. Use wrap() for the description/item name column in each table
replacements = [
    # PDF 1
    (r'f"IT Service Component {i}\\nRef: SOW-{2026\+i}-{random.randint\(100,999\)}",',
     r'wrap(f"IT Service Component {i}\\nRef: SOW-{2026+i}-{random.randint(100,999)}", 8),'),
    
    # PDF 2
    (r'f"Industrial Component – Grade A – Spec {random.choice\(\[\'4140\',\'4340\',\'304SS\',\'316SS\'\]\)}",',
     r'wrap(f"Industrial Component – Grade A – Spec {random.choice([\'4140\',\'4340\',\'304SS\',\'316SS\'])}", 8),'),
     
    # PDF 4
    (r'f"{random.choice\(services\)} – Phase {i}",',
     r'wrap(f"{random.choice(services)} – Phase {i}", 8),'),
     
    # PDF 5
    (r'f"{random.choice\(products\)}\\nBatch: {random.choice\(\'ABCDE\'\)}{random.randint\(10,99\)}26",',
     r'wrap(f"{random.choice(products)}\\nBatch: {random.choice(\'ABCDE\')}{random.randint(10,99)}26", 8),'),
     
    # PDF 6
    (r'random.choice\(plans\),',
     r'wrap(random.choice(plans), 8),'),
     
    # PDF 7
    (r'f"Work Item {i} – {random.choice\(\[\'Labor\',\'Material\',\'Equipment\',\'Subcontract\'\]\)}",',
     r'wrap(f"Work Item {i} – {random.choice([\'Labor\',\'Material\',\'Equipment\',\'Subcontract\'])}", 8),'),
     
    # PDF 8
    (r'random.choice\(charges\),',
     r'wrap(random.choice(charges), 8),'),
     
    # PDF 9
    (r'f"Campaign Deliverable – {i:03d}",',
     r'wrap(f"Campaign Deliverable – {i:03d}", 8),'),
]

for old, new in replacements:
    code = re.sub(old, new, code)

# 4. Replace external_7 (German) with an Australian Invoice
german_section = re.search(r'# ══════════════════════════════════════════════════════════════════════════════\n# PDF 3 ── European VAT Invoice.*?# ══════════════════════════════════════════════════════════════════════════════\ndef make_external_7.*?print\(f"✓  {path.name}  \({len\(rows\)} items\)"\)\n\n', code, flags=re.DOTALL)

australian_code = """# ══════════════════════════════════════════════════════════════════════════════
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
        para("ABN: 51 824 391 882\\n100 George Street, Sydney NSW 2000\\nPh: (02) 9876 5432", 8, align=TA_RIGHT, color=colors.grey),
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
    elems.append(para("Coastal Developments Group\\nLevel 4, 150 Pacific Highway\\nNorth Sydney NSW 2060\\nAttention: Accounts Payable", 8))
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

"""

if german_section:
    code = code.replace(german_section.group(0), australian_code)
else:
    print("Warning: Could not find make_external_7 to replace!")

file_path.write_text(code, encoding='utf-8')
print("Successfully patched generator script.")
