"""
create_sample_invoice.py – Generate a sample text-based invoice PDF for testing.
Run once: python scripts/create_sample_invoice.py
"""

from pathlib import Path
import sys

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
except ImportError:
    print("reportlab not installed. Run: pip install reportlab")
    sys.exit(1)

OUTPUT = Path(__file__).resolve().parent.parent / "data" / "samples" / "sample_invoice.pdf"

def build():
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    bold   = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10)
    normal = styles["Normal"]
    h1     = ParagraphStyle("h1", parent=styles["Title"], fontSize=20, textColor=colors.HexColor("#1F4E79"))
    small  = ParagraphStyle("small", parent=styles["Normal"], fontSize=8)

    story = []

    # Header
    story.append(Paragraph("TAX INVOICE", h1))
    story.append(Spacer(1, 0.3*cm))

    # Meta info table
    meta = [
        ["Invoice No.:", "INV-2024-00842",   "Invoice Date:", "15/11/2024"],
        ["PO Number:",   "PO-2024-5091",      "Due Date:",     "15/12/2024"],
    ]
    meta_table = Table(meta, colWidths=[3.5*cm, 6*cm, 3.5*cm, 4*cm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME",  (0,0),(-1,-1), "Helvetica"),
        ("FONTNAME",  (0,0),(0,-1),  "Helvetica-Bold"),
        ("FONTNAME",  (2,0),(2,-1),  "Helvetica-Bold"),
        ("FONTSIZE",  (0,0),(-1,-1), 9),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.5*cm))

    # Vendor & Buyer
    party = [
        [Paragraph("<b>Bill From:</b>", normal), Paragraph("<b>Bill To:</b>", normal)],
        [Paragraph("Acme Supplies Pvt. Ltd.", bold), Paragraph("XYZ Enterprises Ltd.", bold)],
        [Paragraph("123 Industrial Area, Andheri East", normal), Paragraph("456 Business Park, Whitefield", normal)],
        [Paragraph("Mumbai, MH 400069", normal),                 Paragraph("Bengaluru, KA 560066", normal)],
        [Paragraph("GSTIN: 27AABCU9603R1ZX", normal),           Paragraph("GSTIN: 29AABCX1234R1ZY", normal)],
        [Paragraph("PAN: AABCU9603R", normal),                   Paragraph("", normal)],
    ]
    party_table = Table(party, colWidths=[9*cm, 9*cm])
    party_table.setStyle(TableStyle([
        ("FONTSIZE",      (0,0),(-1,-1), 9),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    story.append(party_table)
    story.append(Spacer(1, 0.5*cm))

    # Line items
    story.append(Paragraph("Line Items", bold))
    story.append(Spacer(1, 0.2*cm))

    header = ["Sr. No.", "Description", "HSN/SAC", "Qty", "Unit Price (₹)", "Tax Rate", "Tax Amt (₹)", "Total (₹)"]
    rows   = [
        ["1", "Industrial Grade Bolts (M12)", "7318", "500", "12.00",  "18%", "1,080.00",  "7,080.00"],
        ["2", "Stainless Steel Nuts (M12)",   "7318", "500",  "8.00",  "18%",   "720.00",  "4,720.00"],
        ["3", "Rubber Gaskets (50mm)",        "4016", "200", "35.00",  "12%",   "840.00",  "7,840.00"],
        ["4", "Packaging & Handling",         "9987",   "1", "500.00",  "18%",    "90.00",    "590.00"],
    ]
    data = [header] + rows

    col_widths = [1.2*cm, 5.5*cm, 2*cm, 1.2*cm, 2.5*cm, 2*cm, 2.2*cm, 2.2*cm]
    item_table = Table(data, colWidths=col_widths)
    item_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8),
        ("ALIGN",         (3,1), (-1,-1), "RIGHT"),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#B8B8B8")),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, colors.HexColor("#DCE6F1")]),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
    ]))
    story.append(item_table)
    story.append(Spacer(1, 0.5*cm))

    # Totals
    totals = [
        ["",            "Subtotal:",     "₹ 19,640.00"],
        ["",            "GST (18%/12%):", "₹ 2,730.00"],
        ["",            "Grand Total:",   "₹ 22,370.00"],
    ]
    totals_table = Table(totals, colWidths=[11*cm, 4.5*cm, 3*cm])
    totals_table.setStyle(TableStyle([
        ("FONTNAME",  (1,0), (1,-1),  "Helvetica-Bold"),
        ("FONTNAME",  (1,2), (-1,2),  "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("ALIGN",     (1,0), (-1,-1), "RIGHT"),
        ("LINEABOVE", (1,2), (-1,2),  1, colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (1,2), (-1,2),  colors.HexColor("#1F4E79")),
        ("BACKGROUND",(1,2), (-1,2),  colors.HexColor("#DCE6F1")),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Payment Terms: Net 30 days from invoice date.", small))
    story.append(Paragraph("Bank: HDFC Bank | A/C: 1234567890 | IFSC: HDFC0001234", small))

    doc.build(story)
    print(f"Sample invoice created: {OUTPUT}")

if __name__ == "__main__":
    build()
