from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import pytesseract
from pytesseract import TesseractNotFoundError

from crop_voters import detect_ocr_language_from_filename
from logger import isDebugMode, setup_logger
from summary_extract import parse_summary_totals
from utilities import parse_page_metadata_tamil

logger = setup_logger()

FILENAME_RE = re.compile(r"^(?P<doc>.+?)_page_(?P<page>\d+)_stacked_ocr\.txt$", re.IGNORECASE)


def configure_tesseract_from_env() -> None:
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def ensure_tesseract_available() -> None:
    configure_tesseract_from_env()
    cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "") or ""
    if cmd and Path(cmd).exists():
        return
    if shutil.which("tesseract") is not None:
        return

    for candidate in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]:
        if Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return

    raise RuntimeError(
        "Tesseract is not installed or not on PATH. "
        "Install it (and Tamil language data if needed) or set `TESSERACT_CMD` to the full path "
        "to `tesseract.exe`."
    )


def _tesseract_cmd() -> str:
    cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "") or ""
    return cmd if cmd else "tesseract"


def _tessdata_dir() -> str | None:
    d = os.environ.get("TESSDATA_DIR")
    if not d:
        return None
    p = Path(d)
    return str(p) if p.exists() else None


def _augment_config(base_config: str) -> str:
    d = _tessdata_dir()
    if not d:
        return base_config
    return f'--tessdata-dir "{d}" {base_config}'.strip()


def get_installed_tesseract_langs() -> set[str]:
    args = [_tesseract_cmd(), "--list-langs"]
    d = _tessdata_dir()
    if d:
        args.extend(["--tessdata-dir", d])
    out = subprocess.check_output(args, stderr=subprocess.STDOUT)
    langs: set[str] = set()
    for line in out.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of available languages"):
            continue
        langs.add(line)
    return langs


def extract_text_from_image_path(image_path: str, *, lang: str, config: str) -> str:
    try:
        text = pytesseract.image_to_string(image_path, lang=lang, config=config)
    except TesseractNotFoundError as e:
        raise RuntimeError(
            "Tesseract is not installed or not on PATH. "
            "Install it (and Tamil language data if needed) or set `TESSERACT_CMD`."
        ) from e
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def _ocr_one(image_path: str, output_txt_path: str, *, lang: str, config: str) -> None:
    text = extract_text_from_image_path(image_path, lang=lang, config=config)
    Path(output_txt_path).write_text(text, encoding="utf-8")


def ocr_images_for_pdf(
    *,
    pdf_stem: str,
    jpg_dir: str,
    crops_dir: str,
    ocr_dir: str,
    progress=None,
    ocr_workers: int = 2,
) -> dict:
    """
    OCR stage (bounded concurrency):
    - Stacked voter crops: `*_stacked_crops.jpg` -> `*_stacked_ocr.txt`
    - Street/header crop: `*_street.jpg` -> `*_street.txt`
    - Cover pages: `*_cover_XX.jpg` -> `*_cover_XX_ocr.txt`
    - Summary page: `*_summary.jpg` -> `*_summary_ocr.txt`

    Returns:
        dict with extracted summary totals (best-effort).
    """

    ensure_tesseract_available()
    os.makedirs(ocr_dir, exist_ok=True)

    crops = Path(crops_dir)
    jpgs = Path(jpg_dir)
    out = Path(ocr_dir)

    stacked_images = sorted(crops.glob("*_stacked_crops.jpg"))
    street_images = sorted(list(crops.glob("*_street.png")) + list(crops.glob("*_street.jpg")))
    cover_images = sorted(jpgs.glob("*_cover_*.jpg"))
    summary_images = list(jpgs.glob("*_summary.jpg"))

    jobs: list[tuple[str, str, str, str]] = []

    for p in stacked_images:
        out_txt = out / p.name.replace("_stacked_crops.jpg", "_stacked_ocr.txt")
        jobs.append(
            (
                str(p),
                str(out_txt),
                detect_ocr_language_from_filename(p.name),
                _augment_config("--psm 6 --oem 1"),
            )
        )

    for p in street_images:
        out_txt = out / re.sub(r"_street\.(png|jpg)$", "_street.txt", p.name, flags=re.IGNORECASE)
        jobs.append(
            (
                str(p),
                str(out_txt),
                detect_ocr_language_from_filename(p.name),
                _augment_config("--psm 6"),
            )
        )

    for p in cover_images:
        out_txt = out / p.name.replace(".jpg", "_ocr.txt")
        jobs.append(
            (
                str(p),
                str(out_txt),
                detect_ocr_language_from_filename(p.name),
                _augment_config("--psm 6 --oem 1"),
            )
        )

    for p in summary_images:
        out_txt = out / p.name.replace(".jpg", "_ocr.txt")
        jobs.append(
            (
                str(p),
                str(out_txt),
                detect_ocr_language_from_filename(p.name),
                _augment_config("--psm 6 --oem 1"),
            )
        )

    required: set[str] = set()
    for _, _, lang, _ in jobs:
        if lang == "tam+eng":
            required.update({"tam", "eng"})
        elif lang == "eng":
            required.add("eng")

    installed = get_installed_tesseract_langs()
    missing = sorted(required - installed)
    if missing:
        tessdata_hint = r"C:\Program Files\Tesseract-OCR\tessdata"
        raise RuntimeError(
            "Tesseract language data missing: "
            + ", ".join(missing)
            + ". Install the missing languages (e.g. re-run the installer and select languages) "
            + f"or place the `*.traineddata` files into `{tessdata_hint}`."
        )

    task = None
    if progress:
        task = progress.add_task("Images -> OCR text", total=len(jobs))

    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=max(1, ocr_workers)) as executor:
        futures = {
            executor.submit(_ocr_one, image_path, txt_path, lang=lang, config=config): txt_path
            for (image_path, txt_path, lang, config) in jobs
        }
        for future in as_completed(futures):
            _ = future.result()
            if progress and task:
                progress.advance(task)

    elapsed = time.perf_counter() - start_time
    logger.info(f"OCR completed for {len(jobs)} image(s) in {elapsed:.2f}s")

    summary_totals: dict | None = None
    summary_txt = out / f"{pdf_stem}_summary_ocr.txt"
    if summary_txt.exists():
        summary_totals = parse_summary_totals(summary_txt.read_text(encoding="utf-8"))

    return {"summary": summary_totals}


def parse_page_metadata(ocr_text: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {"assembly": None, "part_no": None, "street": None}
    if not ocr_text:
        return result

    lines = [ln.strip() for ln in ocr_text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return result

    line1, line2 = lines[0], lines[1]

    m_assembly = re.search(r"Name\s*:\s*([A-Za-z0-9\- ]+?)\s+Part", line1, re.I)
    if m_assembly:
        result["assembly"] = m_assembly.group(1).strip()

    m_part = re.search(r"Part\s*No\.?\s*[:\-]?\s*(\d+)", line1, re.I)
    if m_part:
        result["part_no"] = int(m_part.group(1))

    m_street = re.search(r"Section\s+No\s+and\s+Name\s*[:\-]?\s*(.+)$", line2, re.I)
    if m_street:
        result["street"] = m_street.group(1).strip()

    return result


@dataclass(frozen=True)
class ParsedFile:
    doc_id: str
    page_no: int
    assembly: str | None
    part_no: int | None
    street: str | None


def parse_filename(filename: str, *, street_dir: str) -> ParsedFile | None:
    m = FILENAME_RE.match(filename)
    if not m:
        return None

    street_txt = Path(street_dir) / filename.replace("stacked_ocr", "street")
    metadata_text = ""
    if street_txt.exists():
        metadata_text = street_txt.read_text(encoding="utf-8")

    lang = detect_ocr_language_from_filename(filename)
    if lang.startswith("tam"):
        metadata = parse_page_metadata_tamil(metadata_text)
    else:
        metadata = parse_page_metadata(metadata_text)

    return ParsedFile(
        doc_id=m.group("doc"),
        page_no=int(m.group("page")),
        assembly=metadata.get("assembly"),
        part_no=metadata.get("part_no"),
        street=metadata.get("street"),
    )


def extract_pages_from_ocr_dir(
    *,
    ocr_dir: str,
    pdf_stem: str,
    progress=None,
    limit: int | None = None,
) -> list[dict]:
    """
    Reads `*_stacked_ocr.txt` files and emits page-level OCR results with page metadata.
    """

    ocr_path = Path(ocr_dir)
    files = sorted(ocr_path.glob(f"{pdf_stem}_page_*_stacked_ocr.txt"))
    if limit is not None:
        files = files[:limit]

    task = None
    if progress:
        task = progress.add_task("OCR text -> Page blocks", total=len(files))

    results: list[dict] = []
    start_time = time.perf_counter()

    for p in files:
        ocr_text = p.read_text(encoding="utf-8")
        if not ocr_text.strip():
            if progress and task:
                progress.advance(task)
            continue

        parsed = parse_filename(p.name, street_dir=ocr_dir)
        if not parsed:
            logger.warning(f"Failed to parse metadata from filename {p.name}, skipping.")
            if progress and task:
                progress.advance(task)
            continue

        results.append(
            {
                "source_image": p.name,
                "ocr_text": ocr_text,
                "doc_id": parsed.doc_id,
                "assembly": parsed.assembly,
                "part_no": parsed.part_no,
                "street": parsed.street,
                "page_no": parsed.page_no,
            }
        )

        if progress and task:
            progress.advance(task)

    (ocr_path / "ocr_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    elapsed = time.perf_counter() - start_time
    logger.info(f"Loaded {len(results)} page OCR block(s) in {elapsed:.2f}s")

    return results


def assign_serial_numbers(results: list[dict]) -> list[dict]:
    """
    Assigns serial_no resetting per doc_id.
    """

    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        grouped[r["doc_id"]].append(r)

    if isDebugMode():
        logger.debug(f"Assigning serial numbers for {len(grouped)} documents")

    final: list[dict] = []

    for _, voters in grouped.items():
        voters.sort(key=lambda x: (x["page_no"]))
        for idx, voter in enumerate(voters, start=1):
            if isDebugMode():
                logger.debug(
                    f"Assigning serial_no {idx} to voter from doc {voter['doc_id']} (page {voter['page_no']})"
                )
            voter["serial_no"] = idx
            final.append(voter)

    final.sort(key=lambda x: (x["doc_id"], x["serial_no"]))
    return final
