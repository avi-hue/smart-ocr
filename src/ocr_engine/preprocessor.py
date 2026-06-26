"""
preprocessor.py – Image preprocessing pipeline to improve OCR accuracy.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image
from src.utils.logger import get_logger

log = get_logger(__name__)

def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """
    Apply OpenCV preprocessing to improve Tesseract OCR accuracy.
    - Convert to grayscale
    - Apply adaptive thresholding / binarization
    - Denoise
    """
    # Convert PIL Image to OpenCV format (numpy array)
    open_cv_image = np.array(image)
    
    # Convert RGB to BGR (OpenCV default)
    # If the image has an alpha channel, we drop it or convert properly
    if len(open_cv_image.shape) == 3 and open_cv_image.shape[2] == 3:
        img_bgr = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)
    elif len(open_cv_image.shape) == 3 and open_cv_image.shape[2] == 4:
        img_bgr = cv2.cvtColor(open_cv_image, cv2.COLOR_RGBA2BGR)
    else:
        img_bgr = open_cv_image

    # 1. Grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 2. Upscale 2x — single biggest improvement for small/dense text like numbers in tables
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

    # 3. Denoise — Gaussian blur is better for printed text than median
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # 4. Adaptive Thresholding — larger block size handles uneven lighting better
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )

    # Deskew could be added here, but complex for invoices without strict baselines.
    
    # Convert back to PIL Image
    result_img = Image.fromarray(binary)
    return result_img
