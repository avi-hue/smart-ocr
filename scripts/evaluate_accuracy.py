"""
Evaluate Extraction Accuracy

Randomly samples a subset of PDFs from the dataset, runs the OCR extraction pipeline,
and outputs a report indicating the extraction success rate for each field.
"""

import sys
import random
from pathlib import Path
from collections import Counter
from tqdm import tqdm

from src.pdf_processor.classifier import classify_pdf
from src.pdf_processor.text_extractor import extract_text_pages
from src.ocr_engine.field_extractor import extract_invoice_fields
from src.utils.invoice_structures import ALL_FIELDS

def main(sample_size=30):
    data_dir = Path("data/samples/Pdf")
    
    if not data_dir.exists():
        print(f"Directory {data_dir} does not exist.")
        sys.exit(1)
        
    all_pdfs = list(data_dir.glob("*.pdf"))
    if not all_pdfs:
        print(f"No PDFs found in {data_dir}")
        sys.exit(1)
        
    print(f"Found {len(all_pdfs)} total PDFs.")
    
    # Sample randomly
    sample_size = min(sample_size, len(all_pdfs))
    sample_pdfs = random.sample(all_pdfs, sample_size)
    
    print(f"Evaluating {sample_size} random PDFs...\n")
    
    field_success = Counter()
    total_processed = 0
    total_expected_fields = len([f for f in ALL_FIELDS if f.required])
    
    for pdf_path in tqdm(sample_pdfs):
        try:
            # 1. Classify
            classification = classify_pdf(pdf_path)
            if classification.overall_type == "scanned" or classification.total_pages > 50:
                continue # Skip pure scanned or massive docs for this text evaluation
                
            # 2. Extract Text
            doc_text = extract_text_pages(pdf_path, classification)
            if not doc_text.full_text.strip():
                continue
                
            # 3. Extract Fields
            extracted = extract_invoice_fields(doc_text.full_text, pdf_path, doc_text.all_tables)
            
            total_processed += 1
            
            # Record successes
            data = extracted.__dict__
            for field in ALL_FIELDS:
                val = data.get(field.name)
                # Count as success if it's not None, not empty, and not 0.0 for currency
                if val is not None and str(val).strip() != "" and str(val).strip() != "0.0":
                    field_success[field.name] += 1
                    
        except Exception as e:
            print(f"\nError processing {pdf_path.name}: {e}")
            continue
            
    print("\n\n" + "="*50)
    print("EXTRACTION ACCURACY REPORT")
    print("="*50)
    print(f"Total PDFs successfully processed: {total_processed}")
    
    if total_processed == 0:
        print("No valid text-based PDFs were processed.")
        sys.exit(0)
        
    print("\nSuccess Rate by Field:")
    for field in ALL_FIELDS:
        successes = field_success[field.name]
        rate = (successes / total_processed) * 100
        req_flag = "[REQUIRED]" if field.required else "[OPTIONAL]"
        print(f"{field.name:20s} {req_flag:10s} : {successes}/{total_processed} ({rate:.1f}%)")
        
if __name__ == "__main__":
    main(50)
