from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image, ImageDraw

from config import VOTER_END_MARKER
from logger import setup_logger

logger = setup_logger()


def detect_ocr_language_from_filename(filename: str) -> str:
    """
    Detect OCR language based on PNG/PDF filename.

    Returns:
        "eng"      for English-only OCR
        "tam+eng"  for Tamil + English OCR
    """
    fname = filename.upper()

    if "-TAM-" in fname:
        return "tam+eng"
    if "-ENG-" in fname:
        return "eng"
    return "eng"


def extract_epic_region(crop: Image.Image, epic_x_ratio: float = 0.60, epic_y_ratio: float = 0.25):
    cw, ch = crop.size

    x1 = int(cw * epic_x_ratio)
    y1 = 10
    x2 = cw
    y2 = int(ch * epic_y_ratio)

    return crop.crop((x1, y1, x2, y2))


def relocate_epic_id_region(
    crop: Image.Image,
    epic_x_ratio: float = 0.60,
    epic_y_ratio: float = 0.25,
    bottom_empty_ratio: float = 0.30,
    padding: int = 6,
    bg_color: str = "white",
) -> Image.Image:
    cw, ch = crop.size

    epic_region = extract_epic_region(crop, epic_x_ratio=epic_x_ratio, epic_y_ratio=epic_y_ratio)
    epic_w, epic_h = epic_region.size

    draw = ImageDraw.Draw(crop)
    draw.rectangle([int(cw * epic_x_ratio), 0, cw, int(ch * epic_y_ratio)], fill=bg_color)

    bottom_start_y = int(ch * (1 - bottom_empty_ratio))
    paste_x = padding
    paste_y = bottom_start_y + padding

    if paste_y + epic_h <= ch:
        crop.paste(epic_region, (paste_x, paste_y))
    else:
        visible_h = ch - paste_y
        crop.paste(epic_region.crop((0, 0, epic_w, visible_h)), (paste_x, paste_y))

    return crop


def append_voter_end_marker(
    crop: Image.Image,
    marker_img: Image.Image,
    scale: float = 2.0,
    bottom_padding_px: int = 8,
    left_padding_px: int = 8,
) -> Image.Image:
    """
    Appends a scaled VOTER_END marker image at bottom-left of the crop.
    """

    cw, ch = crop.size
    mw, mh = marker_img.size

    new_mw = int(mw * scale)
    new_mh = int(mh * scale)
    marker_resized = marker_img.resize((new_mw, new_mh), Image.BICUBIC)

    if new_mh + bottom_padding_px > ch:
        raise ValueError(
            f"Marker too tall ({new_mh}px) for crop height ({ch}px). Reduce scale or padding."
        )

    paste_x = left_padding_px
    paste_y = ch - new_mh - bottom_padding_px

    out = crop.copy()
    bg = Image.new("RGB", (new_mw, new_mh), "white")
    out.paste(bg, (paste_x, paste_y))
    out.paste(marker_resized, (paste_x, paste_y))

    return out


def save_street_crop_image(
    input_jpg: str, output_path: str, *, top_height_ratio: float = 0.05
) -> None:
    img = Image.open(input_jpg)
    w, h = img.size
    top_area_height = int(h * top_height_ratio)
    top_area = img.crop((0, 0, w, top_area_height))
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".png":
        top_area.save(output_path, "PNG")
    else:
        top_area.save(output_path, "JPEG")


def crop_voter_boxes_dynamic(input_jpg: str, *, crops_dir: str) -> None:
    """
    Crops voter boxes from a single voter-grid page JPG and writes:
    - `<page>_street.jpg` (header crop image)
    - `<page>_stacked_crops.jpg` (stacked voter crops)
    """

    os.makedirs(crops_dir, exist_ok=True)

    img = Image.open(input_jpg)
    w, h = img.size

    page_stem = os.path.splitext(os.path.basename(input_jpg))[0]

    save_street_crop_image(
        input_jpg,
        os.path.join(crops_dir, f"{page_stem}_street.png"),
        top_height_ratio=0.05,
    )

    top_header_pct = 0.032
    bottom_footer_pct = 0.032
    left_margin_pct = 0.024
    right_margin_pct = 0.024

    top_header = int(h * top_header_pct)
    bottom_footer = int(h * bottom_footer_pct)
    left_margin = int(w * left_margin_pct)
    right_margin = int(w * right_margin_pct)

    content_x = left_margin
    content_y = top_header
    content_w = w - left_margin - right_margin
    content_h = h - top_header - bottom_footer

    rows, cols = 10, 3
    box_w = content_w / cols
    box_h = content_h / rows

    photo_w_ratio = 380 / 1555
    photo_y_ratio = (620 - 480) / 620

    crops: list[dict] = []
    count = 1
    for r in range(rows):
        for c in range(cols):
            left = int(content_x + c * box_w)
            upper = int(content_y + r * box_h)
            right = int(left + box_w)
            lower = int(upper + box_h)

            crop = img.crop((left, upper, right, lower))

            cw, ch = crop.size
            px_left = int(cw * (1 - photo_w_ratio))
            px_top = int(ch * photo_y_ratio)
            px_right = cw
            px_bottom = int(ch)

            pad_x = int(cw * 0.02)
            pad_y = int(ch * 0.02)

            px_left = max(0, px_left - pad_x)
            px_top = max(0, px_top - pad_y)
            px_right = min(cw, px_right + pad_x)
            px_bottom = min(ch, px_bottom + pad_y)

            draw = ImageDraw.Draw(crop)
            draw.rectangle([px_left, px_top, px_right, px_bottom], fill="white")

            crop = relocate_epic_id_region(crop)
            crop = append_voter_end_marker(
                crop, marker_img=VOTER_END_MARKER, scale=2.0, left_padding_px=500
            )

            crops.append(
                {
                    "crop_name": f"{page_stem}_voter_{count:02d}.jpg",
                    "crop": crop,
                    "lang": detect_ocr_language_from_filename(input_jpg),
                }
            )
            count += 1

    stacked_image = stack_voter_crops_vertically(crops)
    stacked_path = os.path.join(crops_dir, f"{page_stem}_stacked_crops.jpg")
    stacked_image.save(stacked_path, "JPEG")


def crop_voter_pages_to_stacks(
    jpg_pdf_dir: str, crops_dir: str, progress=None, limit: int | None = None
) -> None:
    start_time = time.perf_counter()

    jpgs = sorted(
        f for f in os.listdir(jpg_pdf_dir) if f.lower().endswith(".jpg") and "_page_" in f.lower()
    )
    if limit is not None:
        jpgs = jpgs[:limit]

    task = None
    if progress:
        task = progress.add_task("JPGs -> Stacked crops", total=len(jpgs))

    for jpg in jpgs:
        input_jpg_path = os.path.join(jpg_pdf_dir, jpg)
        crop_voter_boxes_dynamic(input_jpg_path, crops_dir=crops_dir)
        if progress and task:
            progress.advance(task)

    elapsed = time.perf_counter() - start_time
    logger.info(f"Cropping completed for {len(jpgs)} page(s) in {elapsed:.2f}s")


def crop_voter_pages_to_stacks_parallel(
    jpg_pdf_dir: str,
    crops_dir: str,
    progress=None,
    max_workers: int = 4,
    limit: int | None = None,
) -> None:
    start_time = time.perf_counter()

    jpgs = sorted(
        f for f in os.listdir(jpg_pdf_dir) if f.lower().endswith(".jpg") and "_page_" in f.lower()
    )
    if limit is not None:
        jpgs = jpgs[:limit]

    task = None
    if progress:
        task = progress.add_task("JPGs -> Stacked crops", total=len(jpgs))

    def _worker(jpg: str) -> None:
        crop_voter_boxes_dynamic(os.path.join(jpg_pdf_dir, jpg), crops_dir=crops_dir)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, jpg): jpg for jpg in jpgs}
        for future in as_completed(futures):
            _ = future.result()
            if progress and task:
                progress.advance(task)

    elapsed = time.perf_counter() - start_time
    logger.info(f"Cropping completed for {len(jpgs)} page(s) in {elapsed:.2f}s")


def stack_voter_crops_vertically(
    crops: list[dict], padding: int = 10, bg_color: str = "white"
) -> Image.Image:
    assert crops, "No crops provided"

    images = [c["crop"] for c in crops]
    max_width = max(img.width for img in images)

    normalized = []
    for img in images:
        if img.width != max_width:
            padded = Image.new("RGB", (max_width, img.height), bg_color)
            padded.paste(img, (0, 0))
            normalized.append(padded)
        else:
            normalized.append(img)

    total_height = sum(img.height for img in normalized) + padding * (len(normalized) - 1)
    stacked = Image.new("RGB", (max_width, total_height), bg_color)

    y_offset = 0
    for img in normalized:
        stacked.paste(img, (0, y_offset))
        y_offset += img.height + padding

    return stacked
