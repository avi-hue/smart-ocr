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
│   ├── ocr_engine/       ← Week 1–2: Regex & Semantic LLM extraction
│   │   ├── field_extractor.py     ← Spatial & Regex parsing
│   │   └── llm_extractor.py       ← Google Gemini JSON extraction
│   ├── data_cleaner/     ← Week 1–2: Cleaning & normalisation
│   └── excel_exporter/   ← Week 1–2: Excel generation
├── scripts/
│   └── verify_env.py     ← Week 1: Environment checker
├── tests/                ← Week 4: Test suite
├── docs/                 ← Documentation
├── Deliverables/         ← Project reports
├── main.py               ← Core CLI entrypoint
├── requirements.txt
├── .gitignore            ← Ignore list for git
├── .env                  ← Local API keys (ignored by git)
├── .env.example          ← Template for API keys
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

### 2. Configure API Keys
Create a `.env` file in the root directory and add your Google Gemini API key:
```env
GEMINI_API_KEY=your_api_key_here
```
*(This is required for the LLM semantic fallback engine. Without it, the pipeline uses the regex/spatial extractor).*

### 3. Verify setup
```bash
python scripts/verify_env.py
```

---

## Running the Pipeline

### Step 1 — Generate sample invoices (optional, for testing)
Generates diverse invoice PDFs — each with a **different schema, columns, and header fields** — into `data/samples/`:

```bash
python scripts/generate_multiple_samples.py
```
> Generates **6 PDFs by default** (one per profile). Use `--count N` to generate more:
> ```bash
> python scripts/generate_multiple_samples.py --count 12
> ```

**Available invoice profiles (schemas):**

| Profile | Label | Key Differences |
|---|---|---|
| `standard_gst` | TAX INVOICE | Full 8-column table; GSTIN, PAN, PO#, Due Date in header |
| `no_po_no_pan` | INVOICE | No PO Number or Vendor PAN |
| `split_gst` | TAX INVOICE | 10 columns — CGST % and SGST % shown separately |
| `with_discount` | SALES INVOICE | Extra Disc. % column; no Due Date |
| `minimal` | BILL / RECEIPT | Only 5 columns (no tax columns); no GSTIN/PAN/PO# |
| `international` | COMMERCIAL INVOICE | Uses VAT instead of GST; USD / EUR / GBP currencies |

> PDFs are named with their profile, e.g. `invoice_03_abc123_split_gst.pdf`, so you can tell them apart at a glance. Fields missing from a profile appear as **empty cells** in the Excel output.


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

**Convert multiple specific PDFs or use wildcards (Globs):**
```bash
python main.py --input data/samples/invoice_a.pdf data/samples/invoice_b.pdf
python main.py --input data/samples/external_*.pdf
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
| Semantic LLM AI  | google-genai, pydantic        |
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
- [x] Sample invoice generator — 6 schema profiles (standard GST, split CGST/SGST, discount, minimal, international, no-PO/PAN); `--count N` flag
- [x] Accuracy evaluation script (`scripts/evaluate_accuracy.py`)

### Step 2 — Semantic LLM Fallback & Unstructured Data ✅ Complete
- [x] Integrate `google-genai` and `pydantic` strict JSON schema validation
- [x] Build `llm_extractor.py` for semantic zero-shot extraction
- [x] Automatic pipeline routing (detects API key and switches to LLM)
- [x] Excel exporter graceful failovers (auto-pruning empty columns, `PermissionError` handling)

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
