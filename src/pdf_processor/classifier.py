"""
classifier.py – Detect whether each page in a PDF is text-based or scanned.

Strategy:
  - Open with PyMuPDF (fitz)
  - Call page.get_text() on each page
  - If character count > TEXT_THRESHOLD → "text"
  - Otherwise → "scanned"

Returns a per-page dict and an overall PDF type label.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal

import fitz  # PyMuPDF

from src.utils.logger import get_logger

log = get_logger(__name__)

# Minimum characters on a page to consider it text-based
TEXT_THRESHOLD = 50

PageType = Literal["text", "scanned"]


@dataclass
class ClassificationResult:
    """Result of classifying a single PDF."""

    pdf_path: Path
    page_types: Dict[int, PageType]      # {0: "text", 1: "scanned", ...}
    overall_type: Literal["text", "scanned", "mixed"]
    total_pages: int

    @property
    def text_pages(self) -> list[int]:
        return [p for p, t in self.page_types.items() if t == "text"]

    @property
    def scanned_pages(self) -> list[int]:
        return [p for p, t in self.page_types.items() if t == "scanned"]


def classify_pdf(pdf_path: str | Path) -> ClassificationResult:
    """
    Classify each page of a PDF as 'text' or 'scanned'.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        ClassificationResult with per-page types and overall label.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    log.info("Classifying PDF: {}", pdf_path.name)

    page_types: Dict[int, PageType] = {}

    with fitz.open(str(pdf_path)) as doc:
        total_pages = doc.page_count
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text()
            char_count = len(text.strip())

            page_type: PageType = "text" if char_count >= TEXT_THRESHOLD else "scanned"
            page_types[page_num] = page_type

            log.debug(
                "  Page {:>3}: {:>7} chars → {}",
                page_num + 1,
                char_count,
                page_type.upper(),
            )

    # Determine overall PDF type
    unique_types = set(page_types.values())
    if unique_types == {"text"}:
        overall = "text"
    elif unique_types == {"scanned"}:
        overall = "scanned"
    else:
        overall = "mixed"

    log.info(
        "Classification complete → {} ({}/{} text pages)",
        overall.upper(),
        len([t for t in page_types.values() if t == "text"]),
        total_pages,
    )

    return ClassificationResult(
        pdf_path=pdf_path,
        page_types=page_types,
        overall_type=overall,
        total_pages=total_pages,
    )
