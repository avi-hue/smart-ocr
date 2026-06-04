# Smart-OCR — Invoice Data Extraction System

> Automated OCR pipeline that reads PDF invoices and exports structured Excel reports.

---

## Project Structure

```
Smart-OCR/
├── data/
│   ├── samples/          ← Place your input PDF invoices here
│   └── processed/        ← Intermediate processed images
├── output/
│   ├── excel/            ← Generated Excel reports
│   └── logs/             ← Rotating log files
├── src/
│   ├── utils/
│   │   ├── config.py              ← Central configuration
│   │   ├── logger.py              ← Shared logger
│   │   └── invoice_structures.py  ← Field taxonomy & regex hints
│   ├── pdf_processor/    ← Week 1–2: PDF reading & classification
│   ├── ocr_engine/       ← Week 2: OCR + image preprocessing
│   ├── data_cleaner/     ← Week 1–2: Cleaning & normalisation
│   └── excel_exporter/   ← Week 1–2: Excel generation
├── scripts/
│   └── verify_env.py     ← Week 1: Environment checker
├── tests/                ← Week 4: Test suite
├── docs/                 ← Documentation
├── Deliverables/         ← Project reports
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Start

### 1. Install Tesseract OCR
Download and install from:  
https://github.com/UB-Mannheim/tesseract/wiki  
*(Recommended: install to `C:\Program Files\Tesseract-OCR\`)*

### 2. Set up Python environment
```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 3. Configure environment
```bash
copy .env.example .env
# Edit .env and set TESSERACT_CMD to your Tesseract path
```

### 4. Verify setup
```bash
python scripts/verify_env.py
```

### 5. Add sample invoices
Place PDF invoice files in `data/samples/`.

---

## Tech Stack

| Component        | Library                        |
|-----------------|-------------------------------|
| PDF Reading      | PyMuPDF, pdfplumber           |
| OCR              | Tesseract + pytesseract       |
| Image Processing | OpenCV, Pillow                |
| Data Cleaning    | Pandas, Regex                 |
| Excel Export     | OpenPyXL, XlsxWriter          |
| Web UI           | Streamlit                     |
| Logging          | Loguru                        |
| Config           | python-dotenv                 |

---

## Progress

> Each week delivers a working, end-to-end slice of functionality.

### Week 1 — Text-Based Extraction + Excel Export ✅ In Progress
- [x] Environment setup, config, logging
- [x] Invoice field taxonomy + regex patterns
- [x] PDF classifier (text vs scanned detection)
- [x] Text extractor (pdfplumber)
- [x] Field extractor (regex → structured fields)
- [x] Normalizer (dates, amounts, strings)
- [x] Excel exporter (Summary + Line Items sheets)
- [x] CLI pipeline (`main.py`)
- [ ] Regex accuracy improvements
- [ ] End-to-end test with real invoices

### Week 2 — Image-Based OCR Extraction + Excel Export ⬜
- [ ] Image preprocessor (grayscale, denoise, deskew)
- [ ] Tesseract OCR runner + confidence scores
- [ ] PDF page rasterizer (scanned → image at 300 DPI)
- [ ] Route scanned pages through OCR in `main.py`
- [ ] Excel: add confidence score column + flag low-confidence rows

### Week 3 — Streamlit UI Development ⬜
- [ ] Design and develop Streamlit interface
- [ ] PDF upload functionality
- [ ] Display extracted invoice data in tabular format
- [ ] Excel download button
- [ ] Processing status and extraction results display
- [ ] Integrate text-based and OCR pipelines into the UI

### Week 4 — Accuracy Improvement, Testing & Documentation ⬜
- [ ] Test on multiple invoice formats and layouts
- [ ] Improve OCR accuracy through preprocessing and tuning
- [ ] Refine regex patterns and extraction logic
- [ ] Handle edge cases (multi-page, rotated scans, low-quality images)
- [ ] Implement validation checks for extracted fields
- [ ] End-to-end testing
- [ ] Complete project documentation, README, and final report
