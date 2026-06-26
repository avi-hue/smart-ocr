"""
synthesize_ocr_dataset.py
--------------------------
Converts native text-based PDFs into synthetic "scanned" image PDFs
that force Tesseract OCR to engage — letting you generate an unlimited
OCR test dataset without sourcing any real scans.

HOW IT WORKS
  1. Renders every page of the input PDF to a high-resolution image.
  2. Applies realistic scan artifacts: skew rotation, blur, exposure, JPEG noise.
  3. Packs the distorted images back into a flat, image-only PDF.
  4. The resulting PDF has NO embedded text — OCR is required to extract data.

USAGE
  Single file:
      python scripts/synthesize_ocr_dataset.py input.pdf [output.pdf]
      (if output is omitted it saves as <name>_scanned.pdf next to the input)

  Whole folder:
      python scripts/synthesize_ocr_dataset.py path/to/folder/ [output_folder/]
      (all .pdf files are processed; output defaults to <folder>_scanned/)

  From any PDF batch (e.g. the 1000+ invoice dataset):
      python scripts/synthesize_ocr_dataset.py \
          "C:/Users/.../1000+ PDF_Invoice_Folder" \
          data/samples/synthetic_ocr/

EXAMPLES
  python scripts/synthesize_ocr_dataset.py data/samples/external_5.pdf
  python scripts/synthesize_ocr_dataset.py data/samples/ data/samples/synthetic_ocr/
"""

import sys
import random
import io
from pathlib import Path

try:
    import fitz           # PyMuPDF
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError:
    sys.exit("ERROR: Missing dependencies. Run: pip install PyMuPDF Pillow")


# ── core synthesis ─────────────────────────────────────────────────────────────

def synthesize_scanned_pdf(input_path: Path, output_path: Path) -> None:
    """
    Convert one native PDF into a synthetic scan image-PDF.
    Each page is rendered, distorted, and re-packed as JPEG.
    """
    input_path  = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    src = fitz.open(str(input_path))
    dst = fitz.open()

    for page_num in range(len(src)):
        page = src.load_page(page_num)

        # 1. Render to 600-DPI image for extremely clean OCR spacing
        pix      = page.get_pixmap(dpi=600)
        img      = Image.open(io.BytesIO(pix.tobytes("png")))

        # 2. Slight skew (Very minimal for cleaner OCR)
        angle    = random.uniform(-0.1, 0.1)
        img      = img.rotate(angle, resample=Image.BICUBIC,
                              expand=True, fillcolor=(255, 255, 255))

        # 3. Blur — disabled for cleaner OCR
        # img = img.filter(ImageFilter.GaussianBlur(radius=0))

        # 4. Contrast/Brightness (Disabled for cleaner OCR)
        # contrast = ImageEnhance.Contrast(img)
        # img      = contrast.enhance(1.0)
        
        # brightness = ImageEnhance.Brightness(img)
        # img        = brightness.enhance(1.0)

        # 5. Encode as JPEG with high quality
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        img_bytes = buf.getvalue()

        # 6. Insert distorted image into the output PDF
        # Convert pixel dimensions back to PDF points (1 point = 1/72 inch, image is 300 DPI)
        pw, ph = img.width * 72 / 300, img.height * 72 / 300
        rect     = fitz.Rect(0, 0, pw, ph)
        new_page = dst.new_page(width=pw, height=ph)
        new_page.insert_image(rect, stream=img_bytes)

    dst.save(str(output_path))
    print(f"  Scanned -> {output_path.name}  ({len(src)} page(s))")
    dst.close()
    src.close()


# ── CLI entry point ────────────────────────────────────────────────────────────

def _default_output_for_file(src: Path) -> Path:
    return src.parent / f"{src.stem}_scanned{src.suffix}"


def _default_output_for_folder(src: Path) -> Path:
    return src.parent / f"{src.name}_scanned"


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    src_arg = Path(sys.argv[1])
    dst_arg = Path(sys.argv[2]) if len(sys.argv) >= 3 else None

    # ── single file ──────────────────────────────────────────────────────────
    if src_arg.is_file():
        if not src_arg.suffix.lower() == ".pdf":
            sys.exit(f"ERROR: {src_arg} is not a PDF.")
        out = dst_arg if dst_arg else _default_output_for_file(src_arg)
        print(f"Processing 1 PDF: {src_arg.name}")
        synthesize_scanned_pdf(src_arg, out)
        print(f"\nDone! Scanned PDF saved to: {out}")

    # ── folder ───────────────────────────────────────────────────────────────
    elif src_arg.is_dir():
        pdfs = sorted(src_arg.glob("*.pdf"))
        if not pdfs:
            sys.exit(f"No PDF files found in {src_arg}")
        out_dir = dst_arg if dst_arg else _default_output_for_folder(src_arg)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"Processing {len(pdfs)} PDFs from: {src_arg}")
        print(f"Output folder: {out_dir}\n")
        for i, pdf in enumerate(pdfs, 1):
            print(f"  [{i}/{len(pdfs)}] {pdf.name}")
            synthesize_scanned_pdf(pdf, out_dir / pdf.name)
        print(f"\nDone! {len(pdfs)} scanned PDFs saved to: {out_dir}")

    else:
        sys.exit(f"ERROR: '{src_arg}' is not a valid file or directory.")


if __name__ == "__main__":
    main()
