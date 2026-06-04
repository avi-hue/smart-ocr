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

### 1. Set up Python virtual environment
```bash
python -m venv venv
venv\Scripts\activate          # Windows (always run this first!)
pip install -r requirements.txt
```

### 2. Verify setup
```bash
python scripts/verify_env.py
```

---

## Running the Pipeline

### Step 1 — Generate sample invoices (optional, for testing)
Creates 5 randomized text-based PDF invoices in `data/samples/`:
```bash
python scripts/generate_multiple_samples.py
```
> Run this again anytime to generate a fresh set of 5 different invoices.

---

### Step 2 — Convert PDFs to Excel

**Convert all PDFs in a folder:**
```bash
python main.py --input data/samples/
```

**Convert a single specific PDF:**
```bash
python main.py --input data/samples/my_invoice.pdf
```

**Convert multiple specific PDFs:**
```bash
python main.py --input data/samples/invoice_a.pdf data/samples/invoice_b.pdf
```

**Specify a custom output Excel path:**
```bash
python main.py --input data/samples/ --output my_report.xlsx
```

> Output Excel is saved to `output/excel/invoices.xlsx` by default.

---

### Step 3 — Open the Excel report

The Excel file contains **two sheets**:
| Sheet | Contents |
|---|---|
| **Invoice Summary** | One row per PDF — Invoice #, Vendor, Buyer, Totals, Dates |
| **Line Items** | All individual line items from all PDFs with source file column |

---

### CLI Reference

| Flag | Short | Description |
|------|-------|-------------|
| `--input` | `-i` | One or more PDF file paths or a folder path *(required)* |
| `--output` | `-o` | Custom output `.xlsx` path *(optional)* |

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

### Week 1 — Text-Based Extraction + Excel Export ✅ Complete
- [x] Environment setup, config, logging
- [x] Invoice field taxonomy + regex patterns
- [x] PDF classifier (text vs scanned detection)
- [x] Text extractor (pdfplumber, layout-aware)
- [x] Columnar party extractor (vendor & buyer from two-column layout)
- [x] Field extractor (regex → structured fields)
- [x] Normalizer (dates, Net N terms → real dates, amounts, strings)
- [x] Excel exporter (Invoice Summary + Line Items sheets, fully styled)
- [x] CLI pipeline (`main.py`) with multi-file `--input` support
- [x] Sample invoice generator (randomized: names, addresses, GSTIN, PAN, dates, currencies)
- [x] Accuracy evaluation script (`scripts/evaluate_accuracy.py`)

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
