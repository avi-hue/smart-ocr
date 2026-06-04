"""
config.py – Central configuration loader for Smart-OCR.

All modules import settings from here. Values are read from
the .env file (or system environment) with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Locate project root (parent of src/) ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── Tesseract ─────────────────────────────────────────────────────────────────
TESSERACT_CMD: str = os.getenv(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
TESSERACT_LANG: str = os.getenv("TESSERACT_LANG", "eng")

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR     = PROJECT_ROOT / "data"
SAMPLES_DIR  = DATA_DIR / "samples"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR   = PROJECT_ROOT / "output" / "excel"
LOG_DIR      = PROJECT_ROOT / "output" / "logs"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Image preprocessing defaults ─────────────────────────────────────────────
IMG_DPI: int = 300          # DPI for PDF → image rasterisation
IMG_GRAYSCALE: bool = True  # convert to grayscale before OCR
DENOISE: bool = True        # apply fastNlMeansDenoising
THRESHOLD: bool = True      # apply adaptive thresholding

# ── Ensure directories exist ─────────────────────────────────────────────────
for _dir in (SAMPLES_DIR, PROCESSED_DIR, OUTPUT_DIR, LOG_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
