"""
Smart-OCR: Invoice Data Extraction System
==========================================
Week 1 – Environment validation and configuration setup.

Run this script to verify that all dependencies and tools
(Tesseract, OpenCV, PyMuPDF, etc.) are correctly installed.
"""

import sys
import io
import os
import importlib

# Force UTF-8 output on Windows so Unicode symbols render correctly
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ──────────────────────────────────────────────────────────────────────────────
# Colour helpers (no external deps)
# ──────────────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}[OK]  {RESET} {msg}")
def fail(msg): print(f"  {RED}[FAIL]{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}[WARN]{RESET} {msg}")


# ──────────────────────────────────────────────────────────────────────────────
# 1. Python version check
# ──────────────────────────────────────────────────────────────────────────────
def check_python():
    print("\n[1] Python Version")
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        ok(f"Python {version.major}.{version.minor}.{version.micro} — compatible")
    else:
        fail(f"Python {version.major}.{version.minor} — requires 3.9+")


# ──────────────────────────────────────────────────────────────────────────────
# 2. Required packages
# ──────────────────────────────────────────────────────────────────────────────
REQUIRED_PACKAGES = {
    "fitz"          : "PyMuPDF",
    "pdfplumber"    : "pdfplumber",
    "pytesseract"   : "pytesseract",
    "cv2"           : "opencv-python",
    "PIL"           : "Pillow",
    "pandas"        : "pandas",
    "numpy"         : "numpy",
    "openpyxl"      : "openpyxl",
    "xlsxwriter"    : "XlsxWriter",
    "dotenv"        : "python-dotenv",
    "loguru"        : "loguru",
    "tqdm"          : "tqdm",
    "streamlit"     : "streamlit",
}

def check_packages():
    print("\n[2] Python Packages")
    all_ok = True
    for import_name, package_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(import_name)
            ok(f"{package_name}")
        except ImportError:
            fail(f"{package_name} — not installed  →  pip install {package_name}")
            all_ok = False
    return all_ok


# ──────────────────────────────────────────────────────────────────────────────
# 3. Tesseract OCR binary
# ──────────────────────────────────────────────────────────────────────────────
def check_tesseract():
    print("\n[3] Tesseract OCR")
    try:
        import pytesseract
        from dotenv import load_dotenv
        load_dotenv()

        tess_path = os.getenv("TESSERACT_CMD", "")
        if tess_path:
            pytesseract.pytesseract.tesseract_cmd = tess_path

        version = pytesseract.get_tesseract_version()
        ok(f"Tesseract {version} found")
        return True
    except Exception as e:
        fail(f"Tesseract not found: {e}")
        warn("Download from: https://github.com/UB-Mannheim/tesseract/wiki")
        warn("Then set TESSERACT_CMD in your .env file")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# 4. Directory structure
# ──────────────────────────────────────────────────────────────────────────────
REQUIRED_DIRS = [
    "data/samples",
    "data/processed",
    "output/excel",
    "output/logs",
    "src/pdf_processor",
    "src/ocr_engine",
    "src/data_cleaner",
    "src/excel_exporter",
    "src/utils",
    "tests",
    "docs",
    "Deliverables",
]

def check_directories():
    print("\n[4] Project Directory Structure")
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for d in REQUIRED_DIRS:
        full = os.path.join(base, d)
        if os.path.isdir(full):
            ok(d)
        else:
            os.makedirs(full, exist_ok=True)
            warn(f"{d}  — created")


# ──────────────────────────────────────────────────────────────────────────────
# 5. OpenCV smoke-test
# ──────────────────────────────────────────────────────────────────────────────
def check_opencv():
    print("\n[5] OpenCV Smoke Test")
    try:
        import cv2
        import numpy as np
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        assert gray.shape == (100, 100)
        ok(f"OpenCV {cv2.__version__} — image processing OK")
    except Exception as e:
        fail(f"OpenCV error: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# 6. .env file presence
# ──────────────────────────────────────────────────────────────────────────────
def check_env():
    print("\n[6] Environment Configuration")
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base, ".env")
    example_path = os.path.join(base, ".env.example")
    if os.path.exists(env_path):
        ok(".env file found")
    else:
        warn(".env not found — copy .env.example → .env and fill in your Tesseract path")
        if os.path.exists(example_path):
            ok(".env.example present — use it as a template")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("   Smart-OCR  —  Environment Validation (Week 1)")
    print("=" * 55)

    check_python()
    pkgs_ok = check_packages()
    check_tesseract()
    check_directories()
    check_opencv()
    check_env()

    print("\n" + "=" * 55)
    if pkgs_ok:
        print(f"{GREEN}  Environment ready. Proceed to Week 2!{RESET}")
    else:
        print(f"{YELLOW}  Fix the issues above, then re-run this script.{RESET}")
    print("=" * 55 + "\n")
