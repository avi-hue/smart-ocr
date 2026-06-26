"""
rasterizer.py – Convert scanned PDF pages into high-resolution images.
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF
from src.utils.logger import get_logger
from src.pdf_processor.classifier import ClassificationResult

log = get_logger(__name__)

def rasterize_scanned_pages(pdf_path: Path | str, classification: ClassificationResult, dpi: int = 300) -> list[Image.Image]:
    """
    Render all 'scanned' pages from the PDF into PIL Images at the specified DPI.
    """
    pdf_path = Path(pdf_path)
    images = []
    
    if not classification.scanned_pages:
        return images

    log.info("Rasterizing {} scanned page(s) from '{}' at {} DPI", len(classification.scanned_pages), pdf_path.name, dpi)
    
    # Calculate PyMuPDF zoom factor for desired DPI (default is 72)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    with fitz.open(str(pdf_path)) as doc:
        for page_num in sorted(classification.scanned_pages):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            
            # Convert PyMuPDF Pixmap to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
            log.debug("  Rasterized page {} ({}x{})", page_num + 1, img.width, img.height)
            
    return images
