"""
text_extractor.py – Extract text and tables from text-based PDF pages.

Uses pdfplumber for layout-aware extraction (handles columns, tables).
Only processes pages classified as "text" by classifier.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import pdfplumber

from src.pdf_processor.classifier import ClassificationResult
from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class PageContent:
    """Extracted content from a single PDF page."""

    page_num: int                          # 0-indexed
    raw_text: str                          # full text of the page
    tables: List[List[List[Optional[str]]]] = field(default_factory=list)
    # tables: list of tables → each table is list of rows → each row is list of cells


@dataclass
class DocumentContent:
    """Extracted content from the entire PDF."""

    pdf_path: Path
    pages: List[PageContent] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """Concatenated text of all extracted pages."""
        return "\n\n".join(p.raw_text for p in self.pages if p.raw_text)

    @property
    def all_tables(self) -> List[List[List[Optional[str]]]]:
        """All tables across all pages."""
        tables = []
        for page in self.pages:
            tables.extend(page.tables)
        return tables


def extract_text_pages(
    pdf_path: str | Path,
    classification: ClassificationResult,
) -> DocumentContent:
    """
    Extract text and tables from all text-based pages.

    Args:
        pdf_path:       Path to the PDF file.
        classification: Result from classify_pdf().

    Returns:
        DocumentContent with text and table data for each text page.
    """
    pdf_path = Path(pdf_path)
    doc_content = DocumentContent(pdf_path=pdf_path)

    if not classification.text_pages:
        log.warning("No text-based pages found in {}", pdf_path.name)
        return doc_content

    log.info(
        "Extracting text from {} text page(s) in {}",
        len(classification.text_pages),
        pdf_path.name,
    )

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num in classification.text_pages:
            page = pdf.pages[page_num]

            # ── Raw text ────────────────────────────────────────────────────────
            raw_text = page.extract_text(x_tolerance=3, y_tolerance=3, layout=True) or ""

            # ── Tables ──────────────────────────────────────────────────────────
            tables = page.extract_tables() or []

            page_content = PageContent(
                page_num=page_num,
                raw_text=raw_text.strip(),
                tables=tables,
            )
            doc_content.pages.append(page_content)

            log.debug(
                "  Page {:>3}: {:>5} chars, {} table(s)",
                page_num + 1,
                len(raw_text),
                len(tables),
            )

    log.info("Extraction complete — {} pages processed", len(doc_content.pages))
    return doc_content
