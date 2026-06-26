# Smart-OCR — Invoice Data Extraction System

> Automated OCR pipeline that reads PDF and scanned image invoices and exports structured Excel reports. Supports native text PDFs, scanned PDFs, and raw image files (`.jpg`, `.png`).

---

## Project Structure

```
Smart-OCR/
├── data/
│   ├── samples/          ← Place your input PDFs / images here
│   └── processed/        ← Intermediate processed images
├── output/
│   ├── excel/            ← Generated Excel reports
│   └── logs/             ← Rotating log files
├── src/
│   ├── utils/
│   │   ├── config.py              ← Central configuration
│   │   ├── logger.py              ← Shared logger
│   │   └── invoice_structures.py  ← Field taxonomy & regex hints
│   ├── pdf_processor/
│   │   ├── classifier.py          ← Detects text vs scanned pages
│   │   ├── text_extractor.py      ← pdfplumber layout-aware extractor
│   │   └── rasterizer.py          ← Converts scanned PDF pages to images (300 DPI)
│   ├── ocr_engine/
│   │   ├── field_extractor.py     ← Spatial & regex parsing
│   │   ├── llm_extractor.py       ← Google Gemini semantic extraction
│   │   ├── preprocessor.py        ← OpenCV image preprocessing (grayscale, denoise, threshold)
│   │   └── tesseract_runner.py    ← Tesseract OCR wrapper + confidence scoring
│   ├── data_cleaner/
│   │   └── normalizer.py          ← Cleans dates, amounts, Net N payment terms
│   └── excel_exporter/
│       └── exporter.py            ← Styled Excel workbook generation
├── scripts/
│   ├── verify_env.py              ← Environment & dependency checker
│   ├── generate_multiple_samples.py ← Synthetic PDF invoice generator
│   ├── evaluate_accuracy.py        ← Accuracy evaluation against ground truth
│   └── test_ocr.py                ← Standalone OCR verification script
├── tests/                ← Week 4: Test suite
├── docs/                 ← Documentation
├── Deliverables/         ← Project reports
├── main.py               ← Core CLI entrypoint
├── requirements.txt
├── .gitignore
├── .env                  ← Local API keys (never committed to git)
├── .env.example          ← Template for API keys
└── README.md
```

---

## Setup

### 1. Prerequisites

Before running the project, ensure these are installed on your system:

- **Python 3.10+**  
- **Tesseract OCR v5+** — [Download for Windows](https://github.com/UB-Mannheim/tesseract/wiki)  
  Default install path: `C:\Program Files\Tesseract-OCR\tesseract.exe`

### 2. Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

Copy the template and fill in your values:

```bash
copy .env.example .env      # Windows
# cp .env.example .env      # macOS / Linux
```

Edit `.env`:

```env
# Required for LLM extraction (optional — regex fallback used if missing)
GEMINI_API_KEY=your_gemini_api_key_here

# Required if Tesseract is not in your system PATH (Windows users usually need this)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

> **Note:** The pipeline works without `GEMINI_API_KEY` — it falls back to local regex extraction. Line items and unstructured fields require the LLM for best results.

### 5. Verify setup

```bash
python scripts/verify_env.py
```

---

## How It Works

The pipeline automatically detects the type of input and routes it through the correct engine:

```
Input File
    │
    ├─ Native Text PDF ──► [pdfplumber] ──────────────────────┐
    │                                                          │
    ├─ Scanned PDF ──► [PyMuPDF → rasterize] → [OpenCV]       │
    │                      → [Tesseract OCR]                   ├──► [LLM or Regex] ──► Excel
    │                                                          │
    └─ Image (.jpg/.png) ──► [OpenCV] → [Tesseract OCR] ───────┘
```

| File Type | Text Extraction | OCR | LLM Needed for Line Items |
|---|---|---|---|
| Native text PDF | ✅ pdfplumber | ❌ | No (Supported locally via regex & table parser) |
| Scanned PDF | ✅ (text pages) | ✅ (scanned pages) | No (Supported locally via rule-based OCR table parser) |
| Image (.jpg/.png) | ❌ | ✅ Tesseract | No (Supported locally via rule-based OCR table parser) |

---

## Ways to Run

Smart-OCR has **three entry points** — choose the one that fits your workflow:

| Entry Point | File | Best For |
|---|---|---|
| **CLI Pipeline** | `main.py` | Batch processing, scripting, automation |
| **Flask Web UI** | `web_server.py` | Interactive use, drag-and-drop uploads |
| **Developer Scripts** | `scripts/` | Testing, sample generation, accuracy checks |

---

### 1. CLI Pipeline — `main.py`

The primary command-line interface. Process one file, a folder, or a glob pattern and export results to Excel.

#### Process a single PDF or image

```bash
python main.py --input data/samples/my_invoice.pdf
python main.py --input data/samples/ocr_sample_1.jpg
```

#### Process all files in a folder sequentially

```bash
python main.py --input data/samples/
```

#### Process 100% locally — Fast & Offline (bypasses LLM)

```bash
python main.py --input data/samples/ --extractor local
```

#### Parallel Processing — great for 50–100 files at once

Concurrently process multiple invoices using a thread pool:

```bash
python main.py --input data/samples/ --parallel --workers 8
python main.py --input data/samples/ --extractor local --parallel --workers 8
```

#### Custom output path

```bash
python main.py --input data/samples/ --output reports/may_invoices.xlsx
```

> Output defaults to `output/excel/invoices.xlsx`

#### Always use LLM extraction (requires `GEMINI_API_KEY`)

```bash
python main.py --input data/samples/ --extractor llm
```

#### Limit files processed (useful for testing on large folders)

```bash
python main.py --input data/samples/ --limit 10
```

#### CLI Reference

| Flag | Short | Description |
|------|-------|-------------|
| `--input` | `-i` | One or more file paths, folder, or glob pattern *(required)* |
| `--output` | `-o` | Custom output `.xlsx` path *(optional)* |
| `--extractor` | `-e` | Extraction mode: `local` or `llm` (default: `local`) |
| `--parallel` | | Enable concurrent thread-pool processing |
| `--workers` | `-w` | Number of parallel worker threads (default: 4) |
| `--limit` | `-l` | Limit the number of files processed (e.g. `--limit 100`) |

#### Extractor Modes

| Mode | How it works | Needs API Key | Speed |
|------|-------------|--------------|-------|
| `local` | Regex + spatial key-value parser (`field_extractor.py`). Fully offline. | No | Fast |
| `llm` | Always routes to Gemini for semantic extraction. | **Yes** | Slow |


---

### 2. Flask Web UI — `web_server.py`

A premium browser interface. Upload files via drag-and-drop, choose extraction mode, monitor live logs, preview results, and download the Excel report — all in-browser.

#### Launch the web UI

```bash
# Start the Flask web server
venv\Scripts\python.exe web_server.py
```

Then open **http://localhost:5000** in your browser.

### 3. Run via Tunnel at https://e544ce5e7adc45.lhr.life/

#### UI Features

| Feature | Details |
|---|---|
| **File Uploader** | Drag-and-drop PDF / PNG / JPG files (multi-select, up to 200 MB total capacity) |
| **Extraction Mode** | Switch between `local` and `llm` from the sidebar |
| **Parallel Workers** | Enable multi-threading via sidebar toggle + slider |
| **Live Log Console** | Color-coded execution log updates during processing |
| **Results Preview** | Tabbed table view — Invoice Summary & Line Items |
| **Download Button** | One-click Excel report download |

---

### 3. Developer Scripts — `scripts/`

#### Verify your environment is set up correctly

Checks Python, Tesseract, OpenCV, and all key dependencies:

```bash
python scripts/verify_env.py
```

#### Generate synthetic test invoices

Creates diverse PDF invoices with different schemas into `data/samples/`:

```bash
python scripts/generate_multiple_samples.py           # generates 6 (one per profile)
python scripts/generate_multiple_samples.py --count 12
```

**Available invoice profiles:**

| Profile | Label | Key Differences |
|---|---|---|
| `standard_gst` | TAX INVOICE | Full 8-column table; GSTIN, PAN, PO#, Due Date |
| `no_po_no_pan` | INVOICE | No PO Number or Vendor PAN |
| `split_gst` | TAX INVOICE | 10 columns — CGST % and SGST % shown separately |
| `with_discount` | SALES INVOICE | Extra Disc. % column; no Due Date |
| `minimal` | BILL / RECEIPT | Only 5 columns, no tax/GSTIN/PAN |
| `international` | COMMERCIAL INVOICE | VAT instead of GST; USD/EUR/GBP currencies |

#### Verify OCR is working

Runs Tesseract on a single image and prints the raw extracted text:

```bash
python scripts/test_ocr.py data/samples/ocr_sample_1.jpg
```

#### Evaluate extraction accuracy

Compares pipeline output against manually verified ground truth:

```bash
python scripts/evaluate_accuracy.py
```

---

## Excel Output

The generated `.xlsx` contains two sheets:

| Sheet | Contents |
|---|---|
| **Invoice Summary** | One row per file — Invoice #, OCR Confidence, Vendor, Buyer, Subtotal, Tax, Grand Total, Dates, GSTIN, PAN |
| **Line Items** | All individual line items from all invoices, linked back to their source file |

**OCR Confidence column:**
- Shows Tesseract's word-level confidence score (0–100%)
- Cells below **80%** are automatically highlighted red to flag for human review
- Shows `N/A` for native text PDFs (no OCR needed)

---

## Tech Stack

| Component | Library |
|---|---|
| PDF Reading | PyMuPDF, pdfplumber |
| Semantic LLM AI | google-genai, pydantic |
| OCR | Tesseract + pytesseract |
| Image Processing | OpenCV, Pillow |
| Data Cleaning | Pandas, Regex |
| Excel Export | OpenPyXL, XlsxWriter |
| Web UI (Week 3) | Flask |
| Logging | Loguru |
| Config | python-dotenv |

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
- [x] Sample invoice generator — 6 schema profiles; `--count N` flag
- [x] Accuracy evaluation script (`scripts/evaluate_accuracy.py`)

### Step 2 — Semantic LLM Fallback & Unstructured Data ✅ Complete
- [x] Integrate `google-genai` and `pydantic` strict JSON schema validation
- [x] Build `llm_extractor.py` for semantic zero-shot extraction
- [x] Automatic pipeline routing (detects `GEMINI_API_KEY`, switches to LLM)
- [x] Retry logic with exponential backoff for `503 Unavailable` API errors
- [x] Graceful fallback to local regex if LLM returns empty results
- [x] Excel exporter graceful failovers (`PermissionError` handling, empty column pruning)

### Week 2 — Image-Based OCR Extraction ✅ Complete
- [x] Image preprocessor (`preprocessor.py`) — grayscale, median blur denoise, adaptive threshold
- [x] Tesseract OCR runner (`tesseract_runner.py`) — word-level confidence scoring
- [x] PDF page rasterizer (`rasterizer.py`) — scanned pages → 300 DPI images via PyMuPDF
- [x] Native image file support (`.jpg`, `.png`) — bypass PDF rasterizer, go straight to OCR
- [x] Mixed PDF handling — text pages via pdfplumber, scanned pages via OCR, merged together
- [x] Attach OCR confidence score to `ExtractedInvoice` dataclass
- [x] Excel: OCR Confidence column added; low-confidence rows (<80%) highlighted red
- [x] `scripts/test_ocr.py` — standalone OCR verification script

### Week 3 — Flask Web UI Development ✅ Complete
- [x] Design and develop premium Web interface (Stitch-designed layout)
- [x] PDF / image upload functionality (drag-and-drop multi-file uploader with size indicator)
- [x] Display extracted invoice data in tabular format (Invoice Summary + Line Items tabs)
- [x] Excel download button
- [x] Processing status and extraction results display (live log console + progress bar)
- [x] Integrate full pipeline into the UI (`web_server.py` wraps `main.process_file` + `export_to_excel`)

### Week 4 — Accuracy Improvement, Multi-page Support & Finalization ✅ Complete
- [x] Test on multiple invoice formats and layouts (using Downloads/dataset)

- [x] Support multi-page documents without text truncation (expanded character limit)
- [x] Display confidence score as `100.0% (Native)` for native text PDFs (resolves OCR confusion)
- [x] Specify maximum upload capacity (Max 200 MB total capacity) in the UI
- [x] Remove old Streamlit app file (`app.py`) and clean up documentation

