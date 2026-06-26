"""
web_server.py – Smart-OCR Flask Web Server.

Serves the premium Stitch-designed UI and wires it to the OCR pipeline.

Run with:
    python web_server.py

Then open: http://localhost:5000
"""

from __future__ import annotations

import io
import json
import os
import queue
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Request

# ── App setup ─────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

Request.max_form_parts = 10000  # Allow up to 10,000 files/fields to prevent 413 on 1000+ files

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB max upload
app.config["MAX_FORM_PARTS"] = 100000  # Actually works for Flask 3.x to allow >1000 files

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response

PROJECT_ROOT = Path(__file__).resolve().parent
JOBS_DIR = PROJECT_ROOT / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = PROJECT_ROOT / "web_settings.json"

# In-memory job store: job_id -> {status, log_queue, result, excel_path, ...}
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

# ── Default settings ──────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "extractor_mode": "local",
    "parallel": False,
    "workers": 4,
    "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
    "tesseract_path": os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    "confidence_threshold": 80,
}


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
            merged = {**DEFAULT_SETTINGS, **saved}
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


# ── Log capture ───────────────────────────────────────────────────────────────

class QueueLogCapture:
    """
    Redirects stdout/stderr to a thread-safe queue so the SSE endpoint
    can stream them to the browser in real time.
    """

    def __init__(self, log_q: queue.Queue):
        self._q = log_q
        self._orig_stdout = None
        self._orig_stderr = None

    def write(self, text: str):
        text = text.strip()
        if not text:
            return
        level = "info"
        lower = text.lower()
        if any(k in lower for k in ("error", "failed", "exception", "traceback")):
            level = "error"
        elif any(k in lower for k in ("warning", "warn", "skipped")):
            level = "warn"
        elif any(k in lower for k in ("done", "ok", "success", "complete", "saved", "exported")):
            level = "success"
        self._q.put({"type": "log", "level": level, "text": text})

    def flush(self):
        pass

    def __enter__(self):
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        sys.stdout = self
        sys.stderr = self
        return self

    def __exit__(self, *_):
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr


# ── Background processing ─────────────────────────────────────────────────────

def _run_job(job_id: str, file_paths: list[Path], settings: dict):
    """Process files in a background thread, streaming logs + results."""
    from main import process_file
    from src.excel_exporter.exporter import export_to_excel

    # Ensure environment variables are loaded and set for the current thread/process execution
    if settings.get("gemini_api_key"):
        os.environ["GEMINI_API_KEY"] = settings["gemini_api_key"]
    if settings.get("tesseract_path"):
        os.environ["TESSERACT_CMD"] = settings["tesseract_path"]

    job = _jobs[job_id]
    log_q: queue.Queue = job["log_q"]
    extractor_mode = settings.get("extractor_mode", "local")
    total = len(file_paths)

    def emit(msg: str, level: str = "info"):
        log_q.put({"type": "log", "level": level, "text": msg})

    def progress(current: int, total: int, filename: str):
        log_q.put({
            "type": "progress",
            "current": current,
            "total": total,
            "filename": filename,
            "pct": round(current / total * 100),
        })

    emit(f"🚀 Starting pipeline — {total} file(s), mode={extractor_mode}", "info")
    
    invoices = []
    errors = 0
    log_capture = QueueLogCapture(log_q)

    for i, fp in enumerate(file_paths, start=1):
        progress(i - 1, total, fp.name)
        emit(f"Processing file {i}/{total}: {fp.name}", "info")
        try:
            with log_capture:
                result = process_file(fp, extractor_mode=extractor_mode)
            if result:
                invoices.append(result)
                emit(f"✅ OK — {fp.name}", "success")
            else:
                errors += 1
                emit(f"⚠️ SKIP — {fp.name}: no data extracted", "warn")
        except Exception as exc:
            errors += 1
            emit(f"❌ ERROR — {fp.name}: {exc}", "error")

    progress(total, total, "")
    emit(f"Pipeline complete: {len(invoices)}/{total} invoices extracted", "success")

    # Build results JSON
    results_data = []
    for inv in invoices:
        d = inv.to_flat_dict()
        # Add line items count
        d["line_items_count"] = len(inv.line_items)
        d["line_items"] = []
        for item in inv.line_items:
            if item.extra_fields:
                d["line_items"].append(item.extra_fields)
            else:
                d["line_items"].append({
                    "Sr. No.": item.sr_no,
                    "Description": item.description,
                    "HSN/SAC": item.hsn_sac_code,
                    "Qty": item.quantity,
                    "Unit Price": item.unit_price,
                    "Disc. %": item.discount,
                    "Tax Rate": item.tax_rate,
                    "Tax Amount": item.tax_amount,
                    "CGST %": item.cgst_rate,
                    "CGST Amt": item.cgst_amount,
                    "SGST %": item.sgst_rate,
                    "SGST Amt": item.sgst_amount,
                    "Line Total": item.line_total,
                })
        results_data.append(d)

    excel_path = None
    if invoices:
        try:
            job_out_dir = JOBS_DIR / job_id
            job_out_dir.mkdir(parents=True, exist_ok=True)
            excel_path = job_out_dir / "invoices.xlsx"
            with log_capture:
                export_to_excel(invoices, output_path=excel_path)
            excel_size_kb = excel_path.stat().st_size // 1024
            emit(f"📊 Excel report ready ({excel_size_kb} KB)", "success")
        except Exception as exc:
            emit(f"❌ Excel export failed: {exc}", "error")

    # Save results to disk
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    results_json_path = job_dir / "results.json"
    with open(results_json_path, "w") as f:
        json.dump({
            "job_id": job_id,
            "total": total,
            "extracted": len(invoices),
            "errors": errors,
            "extractor_mode": extractor_mode,
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "results": results_data,
        }, f, indent=2, default=str)

    # Update in-memory job state
    with _jobs_lock:
        job["status"] = "complete"
        job["results"] = results_data
        job["excel_path"] = str(excel_path) if excel_path else None
        job["extracted"] = len(invoices)
        job["errors"] = errors

    log_q.put({"type": "done", "extracted": len(invoices), "errors": errors})


# ── Routes ────────────────────────────────────────────────────────────────────

from werkzeug.exceptions import HTTPException

@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    return jsonify({"error": str(e)}), code

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/process", methods=["POST"])
def api_process():
    """Accept uploaded files and start a background OCR job."""
    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Empty file list"}), 400

    settings = load_settings()
    # Allow per-request overrides from form fields
    extractor_mode = request.form.get("extractor_mode", settings["extractor_mode"])
    parallel = request.form.get("parallel", str(settings["parallel"])).lower() in ("true", "1", "yes")
    workers = int(request.form.get("workers", settings["workers"]))

    job_id = str(uuid.uuid4())[:8]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded files to job directory
    saved_paths = []
    for uf in files:
        if uf.filename:
            dest = job_dir / uf.filename
            uf.save(str(dest))
            saved_paths.append(dest)

    if not saved_paths:
        return jsonify({"error": "No valid files saved"}), 400

    log_q: queue.Queue = queue.Queue()
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "running",
            "log_q": log_q,
            "results": None,
            "excel_path": None,
            "total": len(saved_paths),
            "extracted": 0,
            "errors": 0,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "files": [p.name for p in saved_paths],
            "extractor_mode": extractor_mode,
        }

    job_settings = {**settings, "extractor_mode": extractor_mode, "parallel": parallel, "workers": workers}
    thread = threading.Thread(target=_run_job, args=(job_id, saved_paths, job_settings), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id, "total": len(saved_paths)})


@app.route("/api/stream/<job_id>")
def api_stream(job_id: str):
    """SSE endpoint that streams live log lines and progress for a job."""
    if job_id not in _jobs:
        return jsonify({"error": "Job not found"}), 404

    def generate():
        job = _jobs[job_id]
        log_q: queue.Queue = job["log_q"]
        while True:
            try:
                event = log_q.get(timeout=30)
            except queue.Empty:
                yield "data: {\"type\":\"heartbeat\"}\n\n"
                continue

            yield f"data: {json.dumps(event)}\n\n"

            if event.get("type") == "done":
                break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/results/<job_id>")
def api_results(job_id: str):
    """Return the full results JSON for a completed job."""
    # Try in-memory first
    if job_id in _jobs:
        job = _jobs[job_id]
        return jsonify({
            "job_id": job_id,
            "status": job["status"],
            "total": job["total"],
            "extracted": job["extracted"],
            "errors": job["errors"],
            "results": job.get("results", []),
            "excel_available": bool(job.get("excel_path")),
        })
    # Fallback: read from disk
    results_json = JOBS_DIR / job_id / "results.json"
    if results_json.exists():
        with open(results_json) as f:
            data = json.load(f)
        data["status"] = "complete"
        data["excel_available"] = (JOBS_DIR / job_id / "invoices.xlsx").exists()
        return jsonify(data)
    return jsonify({"error": "Job not found"}), 404


@app.route("/api/download/<job_id>")
def api_download(job_id: str):
    """Serve the Excel file for a completed job."""
    excel_path = None
    if job_id in _jobs:
        excel_path = _jobs[job_id].get("excel_path")
    if not excel_path:
        excel_path = str(JOBS_DIR / job_id / "invoices.xlsx")
    p = Path(excel_path)
    if not p.exists():
        return jsonify({"error": "Excel file not found"}), 404
    return send_file(
        str(p),
        as_attachment=True,
        download_name="invoices.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/api/history")
def api_history():
    """Return a list of all past jobs (from disk + in-memory)."""
    history = []

    # Scan jobs directory
    for job_dir in sorted(JOBS_DIR.iterdir(), reverse=True):
        if not job_dir.is_dir():
            continue
        job_id = job_dir.name
        results_json = job_dir / "results.json"
        status = _jobs[job_id]["status"] if job_id in _jobs else "complete"

        if results_json.exists():
            try:
                with open(results_json) as f:
                    data = json.load(f)
                history.append({
                    "job_id": job_id,
                    "status": status,
                    "total": data.get("total", 0),
                    "extracted": data.get("extracted", 0),
                    "errors": data.get("errors", 0),
                    "extractor_mode": data.get("extractor_mode", "local"),
                    "completed_at": data.get("completed_at", ""),
                    "files": data.get("results", [{}])[0].get("source_file", "") if data.get("results") else "",
                    "excel_available": (job_dir / "invoices.xlsx").exists(),
                })
            except Exception:
                pass
        elif job_id in _jobs:
            job = _jobs[job_id]
            history.append({
                "job_id": job_id,
                "status": job["status"],
                "total": job["total"],
                "extracted": job["extracted"],
                "errors": job["errors"],
                "extractor_mode": job["extractor_mode"],
                "completed_at": "",
                "files": ", ".join(job["files"][:2]),
                "excel_available": False,
            })

    # Compute aggregate stats
    total_processed = sum(h["total"] for h in history)
    total_extracted = sum(h["extracted"] for h in history)
    avg_conf = "N/A"

    return jsonify({
        "jobs": history[:50],  # last 50
        "stats": {
            "total_jobs": len(history),
            "total_processed": total_processed,
            "total_extracted": total_extracted,
        },
    })


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    settings = load_settings()
    # Mask API key
    masked = dict(settings)
    if masked.get("gemini_api_key"):
        key = masked["gemini_api_key"]
        masked["gemini_api_key"] = key[:8] + "•" * (len(key) - 8) if len(key) > 8 else "•" * len(key)
        masked["has_api_key"] = True
    else:
        masked["has_api_key"] = False
    return jsonify(masked)


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    data = request.get_json(force=True)
    current = load_settings()
    # Only update known keys; keep existing API key if placeholder sent
    for key in DEFAULT_SETTINGS:
        if key in data:
            val = data[key]
            # Don't overwrite real key with masked placeholder
            if key == "gemini_api_key" and "•" in str(val):
                continue
            current[key] = val
    save_settings(current)
    return jsonify({"ok": True})


@app.route("/api/test_connection")
def api_test_connection():
    """Test the Gemini API key."""
    settings = load_settings()
    key = settings.get("gemini_api_key", "")
    if not key:
        return jsonify({"ok": False, "message": "No API key configured"})
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        # Minimal test — list models
        list(genai.list_models())
        return jsonify({"ok": True, "message": "Gemini API connected ✅"})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  Smart-OCR Web Server")
    print("  Open: http://localhost:5000")
    print("=" * 55)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
