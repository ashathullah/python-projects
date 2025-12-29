import os
import shutil

import fitz  # PyMuPDF

pdf_path = os.environ.get(
    "PDF_PATH",
    r"C:\Users\ashat\persnal\projects\python-projects\voter-shield-altenative-approach\pdf\2026-EROLLGEN-S22-114-SIR-DraftRoll-Revision1-TAM-1-WI.pdf",
)
output_path = os.environ.get("PDF_TEXT_OUTPUT", "output.txt")

use_ocr = os.environ.get("PDF_USE_OCR", "0") == "1"
ocr_language = os.environ.get("PDF_OCR_LANG", "eng")
ocr_dpi = int(os.environ.get("PDF_OCR_DPI", "300"))

doc = fitz.open(pdf_path)
pages_text: list[str] = []
total_chars = 0

for i, page in enumerate(doc, start=1):
    t = page.get_text("text")
    if not t.strip() and use_ocr:
        if shutil.which("tesseract") is None:
            raise RuntimeError(
                "This PDF appears to be scanned (no extractable text). "
                "OCR was requested (PDF_USE_OCR=1), but 'tesseract' was not found on PATH. "
                "Install Tesseract OCR and re-run, or set PDF_USE_OCR=0."
            )
        tp = page.get_textpage_ocr(language=ocr_language, dpi=ocr_dpi, full=True)
        t = page.get_text("text", textpage=tp)

    page_chars = len(t)
    total_chars += page_chars
    print("page", i, "chars", page_chars)
    pages_text.append(t)

with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(pages_text))

if total_chars == 0:
    print(
        "done (0 chars). This PDF likely has no text layer (scanned images). "
        "Try OCR: set PDF_USE_OCR=1 after installing Tesseract."
    )
else:
    print("done")
