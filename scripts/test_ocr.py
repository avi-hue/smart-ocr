"""
test_ocr.py – Standalone OCR verification script.
Prints the raw text extracted from an image to verify Tesseract is working.

Usage:
    python scripts/test_ocr.py data/samples/ocr_sample_1.jpg
"""

import sys
from pathlib import Path

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from src.ocr_engine.preprocessor import preprocess_for_ocr
from src.ocr_engine.tesseract_runner import extract_text_from_images

def test_ocr(image_path: str):
    path = Path(image_path)
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  OCR Test: {path.name}")
    print(f"{'='*60}\n")

    # 1. Load image
    print("[1/3] Loading image...")
    img = Image.open(path)
    print(f"      Size: {img.width}x{img.height} px | Mode: {img.mode}")

    # 2. Preprocess
    print("[2/3] Preprocessing (grayscale, denoise, threshold)...")
    processed = preprocess_for_ocr(img)

    # 3. OCR
    print("[3/3] Running Tesseract OCR...\n")
    text, confidence = extract_text_from_images([processed])

    print(f"{'='*60}")
    print(f"  OCR CONFIDENCE: {confidence:.2f}%")
    print(f"{'='*60}")
    print("\n--- RAW EXTRACTED TEXT ---\n")
    print(text if text.strip() else "[WARNING: No text was extracted!]")
    print("\n--------------------------\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_ocr.py <path_to_image>")
        sys.exit(1)
    test_ocr(sys.argv[1])
