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


def collect_files(input_paths: list[Path]) -> list[Path]:
    """Collect all supported files (.pdf, .png, .jpg, .jpeg) from a list of paths."""
    import glob
    valid_exts = {".pdf", ".png", ".jpg", ".jpeg"}
    files = []
    for path in input_paths:
        path_str = str(path)
        
        # Handle manual globbing (important for Windows CMD/PowerShell)
        if glob.has_magic(path_str):
            matched = glob.glob(path_str, recursive=True)
            if not matched:
                log.warning("Input path pattern did not match any files: {}", path_str)
            for m in matched:
                p = Path(m)
                if p.is_file() and p.suffix.lower() in valid_exts:
                    files.append(p)
            continue

        if path.is_file():
            if path.suffix.lower() not in valid_exts:
                log.warning("Input file is not a PDF or supported image, skipping: {}", path)
                continue
            files.append(path)
        elif path.is_dir():
            dir_files = []
            for ext in valid_exts:
                dir_files.extend(path.glob(f"**/*{ext}"))
            if not dir_files:
                log.warning("No supported files found in directory: {}", path)
            files.extend(sorted(dir_files))
        else:
            log.warning("Input path does not exist: {}", path)
            
    if not files:
        log.error("No valid files found to process.")
        sys.exit(1)
        
    # Remove duplicates if any (while preserving order)
    return list(dict.fromkeys(files))

def process_file(file_path: Path, extractor_mode: str = "hybrid") -> ExtractedInvoice | None:
    """
    Run the full extraction pipeline on a single file.

    Returns:
        ExtractedInvoice if any text content was found, else None.
    """
    log.info("=" * 55)
    log.info("Processing: {} (mode={})", file_path.name, extractor_mode)
    
    full_text = ""
    avg_conf = None
    tables = []
    is_scanned = True

    if file_path.suffix.lower() == ".pdf":
        # Step 1: Classify pages
        try:
            classification = classify_pdf(file_path)
            if classification.overall_type == "text":
                is_scanned = False
        except Exception as e:
            log.error("Failed to classify PDF '{}': {}", file_path.name, e)
            return None

        # Step 2: Extract text from native text pages
        doc_content = extract_text_pages(file_path, classification)
        full_text = doc_content.full_text
        tables = doc_content.all_tables
        
        # Step 2.5: Extract text from scanned pages via OCR
        if classification.scanned_pages:
            log.info("Processing {} scanned page(s) via OCR...", len(classification.scanned_pages))
            from src.pdf_processor.rasterizer import rasterize_scanned_pages
            from src.ocr_engine.preprocessor import preprocess_for_ocr
            from src.ocr_engine.tesseract_runner import extract_text_from_images
            
            # 1. Rasterize
            raw_images = rasterize_scanned_pages(file_path, classification)
            
            # 2. Preprocess
            processed_images = [preprocess_for_ocr(img) for img in raw_images]
            
            # 3. OCR
            ocr_text, avg_conf = extract_text_from_images(processed_images)
            
            # Merge OCR text into the main document content
            if ocr_text:
                full_text += "\n\n" + ocr_text

    else:
        # Handle Raw Image File (e.g. .jpg, .png)
        log.info("Processing image file natively via OCR...")
        from PIL import Image
        from src.ocr_engine.preprocessor import preprocess_for_ocr
        from src.ocr_engine.tesseract_runner import extract_text_from_images
        
        try:
            img = Image.open(file_path)
            processed_img = preprocess_for_ocr(img)
            ocr_text, avg_conf = extract_text_from_images([processed_img])
            full_text = ocr_text
        except Exception as e:
            log.error("Failed to process image '{}': {}", file_path.name, e)
            return None

    if not full_text.strip():
        log.warning("No text extracted from '{}' (both native and OCR failed)", file_path.name)
        return None

    # Step 3: Extract structured invoice fields (LLM preferred, spatial fallback)
    import os
    from dotenv import load_dotenv
    from src.ocr_engine.llm_extractor import extract_invoice_via_llm
    
    load_dotenv(override=True) # Load variables from .env file and override cached session vars

    api_key = os.environ.get("GEMINI_API_KEY")
    use_llm = False
    
    if api_key:
        if extractor_mode == "llm":
            use_llm = True
        elif extractor_mode == "hybrid" and is_scanned:
            use_llm = True

    if use_llm:
        log.info("Routing to LLM Semantic Extractor.")
        invoice = extract_invoice_via_llm(text=full_text, source_file=file_path)
        
        # Graceful fallback: If LLM failed due to 503 overload, fallback to local regex
        if invoice.vendor_name is None and invoice.total_amount is None and not invoice.line_items:
            log.warning("LLM Extraction returned empty results (API may be down). Falling back to local Regex Extractor...")
            invoice = extract_invoice_fields(
                text=full_text,
                source_file=file_path,
                tables=tables,
            )
    else:
        log.info("Using Local Regex/Spatial Extractor.")
        invoice = extract_invoice_fields(
            text=full_text,
            source_file=file_path,
            tables=tables,
        )
        
        # Check extraction quality (critical fields & line items). If poor, and Gemini API key is available, fallback to LLM.
        has_vendor = bool(invoice.vendor_name and invoice.vendor_name.strip())
        has_total = bool(invoice.total_amount and invoice.total_amount.strip())
        has_line_items = len(invoice.line_items) > 0
        
        if extractor_mode == "hybrid" and (not has_line_items or not has_vendor or not has_total) and api_key:
            log.warning("Local extraction quality is low (missing vendor, total, or line items). Falling back to LLM Semantic Extractor...")
            invoice = extract_invoice_via_llm(text=full_text, source_file=file_path)
        
    # Attach OCR confidence
    invoice.overall_ocr_confidence = avg_conf

    # Step 4: Normalize
    invoice = normalize_invoice(invoice)

    return invoice


def run(input_paths: list[Path], output_path: Path | None, extractor_mode: str = "hybrid", parallel: bool = False, workers: int = 4, limit: int | None = None) -> None:
    """Main pipeline runner."""
    files = collect_files(input_paths)
    log.info("Found {} file(s) to process", len(files))
    if limit is not None and limit > 0:
        log.info("Limiting process list to the first {} file(s)", limit)
        files = files[:limit]

    invoices: list[ExtractedInvoice] = []
    skipped = 0

    if parallel and len(files) > 1:
        log.info("Running in parallel with {} workers (mode={})...", workers, extractor_mode)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Store original index so we can restore submission order after as_completed()
            futures = {
                executor.submit(process_file, file_path, extractor_mode): (i, file_path)
                for i, file_path in enumerate(files)
            }
            ordered_results: list[tuple[int, object]] = []
            for future in tqdm(as_completed(futures), total=len(files), desc="Processing Files (Parallel)", unit="file"):
                i, file_path = futures[future]
                try:
                    result = future.result()
                    if result:
                        ordered_results.append((i, result))
                    else:
                        skipped += 1
                except Exception as e:
                    log.error("Unhandled error processing file '{}': {}", file_path.name, e)
                    skipped += 1
        # Sort by original file order so Excel rows match input filename order
        ordered_results.sort(key=lambda x: x[0])
        invoices = [result for _, result in ordered_results]
    else:
        for file_path in tqdm(files, desc="Processing Files", unit="file"):
            result = process_file(file_path, extractor_mode=extractor_mode)
            if result:
                invoices.append(result)
            else:
                skipped += 1

    log.info("=" * 55)
    log.info("Pipeline complete: {}/{} invoices extracted", len(invoices), len(files))

    if skipped:
        log.warning("{} file(s) skipped (no text content or unsupported type)", skipped)

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
    parser.add_argument(
        "--extractor", "-e",
        choices=["local", "llm", "hybrid"],
        default="hybrid",
        help="Extraction mode to use:\n"
             "  local  - 100% local extraction (regex & OCR table parsing, fast & offline)\n"
             "  llm    - Always use Gemini LLM for extraction (slow, api dependent)\n"
             "  hybrid - Use local for text PDFs, LLM for scanned PDFs/images (default)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Process documents in parallel using multi-threading",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Limit the number of files to process (default: process all)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        input_paths=args.input,
        output_path=args.output,
        extractor_mode=args.extractor,
        parallel=args.parallel,
        workers=args.workers,
        limit=args.limit,
    )
