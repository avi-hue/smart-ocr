"""
main.py – Smart-OCR CLI entry point.

Usage:
    python main.py --input data/samples/
    python main.py --input data/samples/ --output output/excel/my_report.xlsx
    python main.py --input path/to/invoice.pdf

Pipeline per PDF:
  1. Classify pages (text vs scanned)
  2. Extract text from text-based pages (pdfplumber)
  3. Apply regex → structured invoice fields
  4. Normalize fields (dates, amounts, strings)
  5. Export all invoices to Excel

Note: Scanned pages are logged as warnings and skipped in this phase.
      OCR support for scanned pages will be added in the next phase.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

# Force UTF-8 output on Windows so Unicode symbols render correctly
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from tqdm import tqdm

from src.pdf_processor.classifier import classify_pdf
from src.pdf_processor.text_extractor import extract_text_pages
from src.ocr_engine.field_extractor import extract_invoice_fields, ExtractedInvoice
from src.data_cleaner.normalizer import normalize_invoice
from src.excel_exporter.exporter import export_to_excel
from src.utils.logger import get_logger

log = get_logger(__name__)


def collect_pdfs(input_path: Path) -> list[Path]:
    """Collect all PDF files from a path (file or directory)."""
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            log.error("Input file is not a PDF: {}", input_path)
            sys.exit(1)
        return [input_path]
    elif input_path.is_dir():
        pdfs = sorted(input_path.glob("**/*.pdf"))
        if not pdfs:
            log.error("No PDF files found in: {}", input_path)
            sys.exit(1)
        return pdfs
    else:
        log.error("Input path does not exist: {}", input_path)
        sys.exit(1)


def process_pdf(pdf_path: Path) -> ExtractedInvoice | None:
    """
    Run the full extraction pipeline on a single PDF.

    Returns:
        ExtractedInvoice if any text content was found, else None.
    """
    log.info("=" * 55)
    log.info("Processing: {}", pdf_path.name)

    # Step 1: Classify pages
    classification = classify_pdf(pdf_path)

    if not classification.text_pages:
        log.warning(
            "No text-based pages found in '{}'. "
            "Scanned PDF support coming in next phase. Skipping.",
            pdf_path.name,
        )
        return None

    if classification.scanned_pages:
        log.warning(
            "{} scanned page(s) found in '{}' — these will be skipped in this phase.",
            len(classification.scanned_pages),
            pdf_path.name,
        )

    # Step 2: Extract text from text pages
    doc_content = extract_text_pages(pdf_path, classification)

    if not doc_content.full_text.strip():
        log.warning("No text extracted from '{}'", pdf_path.name)
        return None

    # Step 3: Extract structured invoice fields
    invoice = extract_invoice_fields(
        text=doc_content.full_text,
        source_file=pdf_path,
        tables=doc_content.all_tables,
    )

    # Step 4: Normalize
    invoice = normalize_invoice(invoice)

    return invoice


def run(input_path: Path, output_path: Path | None) -> None:
    """Main pipeline runner."""
    pdfs = collect_pdfs(input_path)
    log.info("Found {} PDF file(s) to process", len(pdfs))

    invoices: list[ExtractedInvoice] = []
    skipped = 0

    for pdf_path in tqdm(pdfs, desc="Processing PDFs", unit="pdf"):
        result = process_pdf(pdf_path)
        if result:
            invoices.append(result)
        else:
            skipped += 1

    log.info("=" * 55)
    log.info("Pipeline complete: {}/{} invoices extracted", len(invoices), len(pdfs))

    if skipped:
        log.warning("{} PDF(s) skipped (no text content or unsupported type)", skipped)

    if not invoices:
        log.error("Nothing to export. No invoices were successfully processed.")
        sys.exit(1)

    # Step 5: Export to Excel
    out_file = export_to_excel(invoices, output_path)

    print()
    print("=" * 55)
    print(f"  [OK]  Done! Processed {len(invoices)} invoice(s)")
    print(f"  [>>]  Excel report: {out_file}")
    print("=" * 55)


# ──────────────────────────────────────────────────────────────────────────────
# CLI argument parsing
# ──────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Smart-OCR — Extract structured data from PDF invoices and export to Excel",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        type=Path,
        help="Path to a single PDF file or a directory containing PDF files",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output Excel file path (default: output/excel/invoices.xlsx)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(input_path=args.input, output_path=args.output)
