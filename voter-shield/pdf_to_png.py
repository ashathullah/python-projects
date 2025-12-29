from __future__ import annotations

import os
from dataclasses import dataclass

from pdf2image import convert_from_path, pdfinfo_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError

from crop_voters import detect_ocr_language_from_filename
from logger import setup_logger

logger = setup_logger()

ENG_START_PAGE = 3  # cover pages: 1..2
TAM_START_PAGE = 4  # cover pages: 1..3


@dataclass(frozen=True)
class PdfConversionInfo:
    pages_total: int
    lang: str
    voter_start_page: int
    cover_pages_count: int
    voter_pages_count: int
    summary_image_path: str | None

    def to_dict(self) -> dict:
        return {
            "pages_total": self.pages_total,
            "lang": self.lang,
            "voter_start_page": self.voter_start_page,
            "cover_pages_count": self.cover_pages_count,
            "voter_pages_count": self.voter_pages_count,
            "summary_image_path": self.summary_image_path,
        }


def _convert_single_page(pdf_path: str, page_no: int, *, dpi: int) -> object:
    pages = convert_from_path(
        pdf_path,
        dpi=dpi,
        fmt="jpeg",
        thread_count=1,  # avoid nested parallelism; bound concurrency at pipeline level
        jpegopt={"quality": 95},
        first_page=page_no,
        last_page=page_no,
    )
    if not pages:
        raise RuntimeError(f"Failed to render page {page_no} for {pdf_path}")
    return pages[0]


def _pdfium_page_count(pdf_path: str) -> int:
    try:
        import pypdfium2 as pdfium  # type: ignore[import-not-found]
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Poppler is not available (pdfinfo missing) and pypdfium2 is not installed."
        ) from e

    doc = pdfium.PdfDocument(pdf_path)
    try:
        return len(doc)
    finally:
        _safe_close(doc)


def _pdfium_render_page(pdf_path: str, page_no: int, *, dpi: int):
    import pypdfium2 as pdfium  # type: ignore[import-not-found]

    scale = dpi / 72.0
    doc = pdfium.PdfDocument(pdf_path)
    page = None
    bitmap = None
    try:
        page = doc.get_page(page_no - 1)
        bitmap = page.render(scale=scale)
        return bitmap.to_pil()
    finally:
        if bitmap is not None:
            _safe_close(bitmap)
        if page is not None:
            _safe_close(page)
        _safe_close(doc)


def _safe_close(obj: object) -> None:
    close = getattr(obj, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            return


def convert_pdf_to_jpgs(pdf_path: str, jpg_dir: str, dpi: int) -> dict:
    """
    Converts a PDF to JPGs in 3 classes:
    - Cover pages: <stem>_cover_01.jpg ... (if any)
    - Voter grid pages: <stem>_page_01.jpg ...
    - Summary page: <stem>_summary.jpg (if any)
    """

    os.makedirs(jpg_dir, exist_ok=True)

    pdf_name = os.path.basename(pdf_path)
    pdf_stem = os.path.splitext(pdf_name)[0]

    lang = detect_ocr_language_from_filename(pdf_name)
    voter_start_page = TAM_START_PAGE if "tam+eng" in lang else ENG_START_PAGE

    use_pdfium = False
    try:
        info = pdfinfo_from_path(pdf_path)
        pages_total = int(info.get("Pages", 0))
    except (PDFInfoNotInstalledError, FileNotFoundError, OSError):
        use_pdfium = True
        pages_total = _pdfium_page_count(pdf_path)
    if pages_total <= 0:
        raise RuntimeError(f"Could not determine page count for {pdf_path}")

    logger.info(f"Converting {pdf_name} (pages_total={pages_total}, lang={lang})")

    cover_pages = list(range(1, min(voter_start_page, pages_total + 1)))
    summary_page = pages_total if pages_total >= voter_start_page else None
    voter_page_nos = (
        list(range(voter_start_page, pages_total)) if pages_total > voter_start_page else []
    )

    for idx, page_no in enumerate(cover_pages, start=1):
        out = os.path.join(jpg_dir, f"{pdf_stem}_cover_{idx:02d}.jpg")
        page = (
            _pdfium_render_page(pdf_path, page_no, dpi=dpi)
            if use_pdfium
            else _convert_single_page(pdf_path, page_no, dpi=dpi)
        )
        page.save(out, "JPEG")

    for idx, page_no in enumerate(voter_page_nos, start=1):
        out = os.path.join(jpg_dir, f"{pdf_stem}_page_{idx:02d}.jpg")
        page = (
            _pdfium_render_page(pdf_path, page_no, dpi=dpi)
            if use_pdfium
            else _convert_single_page(pdf_path, page_no, dpi=dpi)
        )
        page.save(out, "JPEG")

    summary_image_path: str | None = None
    if summary_page is not None:
        summary_image_path = os.path.join(jpg_dir, f"{pdf_stem}_summary.jpg")
        page = (
            _pdfium_render_page(pdf_path, summary_page, dpi=dpi)
            if use_pdfium
            else _convert_single_page(pdf_path, summary_page, dpi=dpi)
        )
        page.save(summary_image_path, "JPEG")

    return PdfConversionInfo(
        pages_total=pages_total,
        lang=lang,
        voter_start_page=voter_start_page,
        cover_pages_count=len(cover_pages),
        voter_pages_count=len(voter_page_nos),
        summary_image_path=summary_image_path,
    ).to_dict()
