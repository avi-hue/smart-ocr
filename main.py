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


def collect_pdfs(input_paths: list[Path]) -> list[Path]:
    """Collect all PDF files from a list of paths (files or directories)."""
    import glob
    pdfs = []
    for path in input_paths:
        path_str = str(path)
        
        # Handle manual globbing (important for Windows CMD/PowerShell)
        if "*" in path_str or "?" in path_str:
            matched = glob.glob(path_str, recursive=True)
            if not matched:
                log.warning("Input path pattern did not match any files: {}", path_str)
            for m in matched:
                p = Path(m)
                if p.is_file() and p.suffix.lower() == ".pdf":
                    pdfs.append(p)
            continue

        if path.is_file():
            if path.suffix.lower() != ".pdf":
                log.warning("Input file is not a PDF, skipping: {}", path)
                continue
            pdfs.append(path)
        elif path.is_dir():
            dir_pdfs = sorted(path.glob("**/*.pdf"))
            if not dir_pdfs:
                log.warning("No PDF files found in directory: {}", path)
            pdfs.extend(dir_pdfs)
        else:
            log.warning("Input path does not exist: {}", path)
            
    if not pdfs:
        log.error("No valid PDF files found to process.")
        sys.exit(1)
        
    # Remove duplicates if any (while preserving order)
    return list(dict.fromkeys(pdfs))


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

    # Step 3: Extract structured invoice fields (LLM preferred, spatial fallback)
    import os
    from dotenv import load_dotenv
    from src.ocr_engine.llm_extractor import extract_invoice_via_llm
    
    load_dotenv() # Load variables from .env file

    if os.environ.get("GEMINI_API_KEY"):
        log.info("GEMINI_API_KEY detected. Routing to LLM Semantic Extractor.")
        invoice = extract_invoice_via_llm(text=doc_content.full_text, source_file=pdf_path)
    else:
        log.info("No LLM API key detected. Using Regex/Spatial Extractor.")
        invoice = extract_invoice_fields(
            text=doc_content.full_text,
            source_file=pdf_path,
            tables=doc_content.all_tables,
        )

    # Step 4: Normalize
    invoice = normalize_invoice(invoice)

    return invoice


def run(input_paths: list[Path], output_path: Path | None) -> None:
    """Main pipeline runner."""
    pdfs = collect_pdfs(input_paths)
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
        nargs="+",
        type=Path,
        help="Path to one or more PDF files or directories containing PDF files",
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
    run(input_paths=args.input, output_path=args.output)
