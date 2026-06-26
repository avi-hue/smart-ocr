"""
tesseract_runner.py – Execute Tesseract OCR on processed images.
"""

from __future__ import annotations

import os
from PIL import Image
import pytesseract
from dotenv import load_dotenv

from src.utils.logger import get_logger

log = get_logger(__name__)

# Ensure env vars are loaded so we can find TESSERACT_CMD
load_dotenv()

tess_cmd = os.environ.get("TESSERACT_CMD")
if tess_cmd:
    pytesseract.pytesseract.tesseract_cmd = tess_cmd
else:
    # Fallback for linux/mac or if in PATH
    pytesseract.pytesseract.tesseract_cmd = "tesseract"

from pytesseract import Output

def extract_text_from_image(image: Image.Image, lang: str = "eng") -> tuple[str, float]:
    """
    Run Tesseract OCR on a single PIL Image.
    Returns (extracted_text, average_confidence).
    """
    log.debug("Running Tesseract OCR (lang={})...", lang)
    try:
        custom_config = r'--oem 3 --psm 6'
        
        # Get text
        text = pytesseract.image_to_string(image, lang=lang, config=custom_config)
        
        # Get word-level confidence data
        data = pytesseract.image_to_data(image, lang=lang, config=custom_config, output_type=Output.DICT)
        
        # Filter out empty words (-1 conf or purely whitespace)
        confidences = [int(c) for c, t in zip(data['conf'], data['text']) if int(c) != -1 and str(t).strip()]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        return text, avg_conf
    except pytesseract.TesseractNotFoundError:
        log.error("Tesseract not found! Is it installed and TESSERACT_CMD set in .env?")
        raise
    except Exception as e:
        log.error("OCR failed: {}", e)
        return "", 0.0

def extract_text_from_images(images: list[Image.Image]) -> tuple[str, float]:
    """
    Run OCR on multiple images and return concatenated text and average confidence.
    """
    if not images:
        return "", 0.0
    
    log.info("Running OCR on {} image(s)", len(images))
    extracted_texts = []
    total_conf = 0.0
    
    for i, img in enumerate(images):
        text, conf = extract_text_from_image(img)
        extracted_texts.append(text)
        total_conf += conf
        log.debug("  OCR complete for image {} (Conf: {:.2f}%)", i + 1, conf)
        
    avg_conf = total_conf / len(images)
    return "\n\n".join(extracted_texts), avg_conf
