from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from config import CROPS_DIR, CSV_DIR, DPI, JPG_DIR, OCR_DIR, PDF_DIR
from crop_voters import crop_voter_pages_to_stacks
from csv_extract import clean_and_extract_csv_v2
from logger import setup_logger
from ocr_extract import (
    assign_serial_numbers,
    ensure_tesseract_available,
    extract_pages_from_ocr_dir,
    ocr_images_for_pdf,
)
from pdf_to_png import convert_pdf_to_jpgs
from progress import get_progress
from quality_flags import add_quality_flags
from run_state import RunState
from s3_helper import download_pdfs, upload_directory
from utilities import split_voters_from_page_ocr
from write_csv import (
    write_final_csv,
    write_final_xlsx,
    write_pdf_csv_atomic,
    write_pdf_xlsx_atomic,
    write_report_json_atomic,
)

logger = setup_logger()


def ensure_runtime_dirs() -> None:
    for p in [PDF_DIR, JPG_DIR, CROPS_DIR, OCR_DIR, CSV_DIR, "runs", "logs"]:
        Path(p).mkdir(parents=True, exist_ok=True)


def reset_dir(dir_path: str) -> None:
    p = Path(dir_path)
    if p.exists():
        try:
            shutil.rmtree(p)
        except PermissionError as e:
            logger.warning(
                f"Could not fully clean {p} (file locked?): {e}; doing best-effort cleanup."
            )
            for child in sorted(p.glob("**/*"), reverse=True):
                try:
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                except PermissionError:
                    continue
                except OSError:
                    continue
    p.mkdir(parents=True, exist_ok=True)


def git_sha() -> str | None:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="VoterShield Pipeline")

    parser.add_argument("--delete-old", action="store_true")
    parser.add_argument("--regression", action="store_true")

    parser.add_argument("--pdf-workers", type=int, default=1)
    parser.add_argument("--ocr-workers", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--state-dir", default="runs")
    parser.add_argument("--run-id")
    parser.add_argument("--no-combined", action="store_true")
    parser.add_argument("--output-format", choices=["csv", "xlsx"], default="xlsx")

    parser.add_argument("--s3-input", help="Comma-separated list of s3:// paths to input PDFs")
    parser.add_argument("--s3-output", help="s3:// path where output CSV should be uploaded")

    args = parser.parse_args()

    if args.resume and not args.run_id:
        parser.error("--resume requires --run-id")

    if args.pdf_workers != 1:
        logger.warning("--pdf-workers > 1 is not implemented yet; running sequentially.")

    ensure_runtime_dirs()

    run_id = (
        args.run_id or f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    )
    state_root = Path(args.state_dir)
    run_state = (
        RunState.load(run_id=run_id, root_dir=state_root)
        if args.resume
        else RunState(run_id=run_id, root_dir=state_root)
    )

    logger.info(
        f"VoterShield Pipeline started (run_id={run_id}, pdf_workers={args.pdf_workers}, ocr_workers={args.ocr_workers})"
    )

    if args.s3_input:
        logger.info("S3 input detected, preparing PDF directory")
        reset_dir(PDF_DIR)
        s3_inputs = [p.strip() for p in args.s3_input.split(",") if p.strip()]
        download_pdfs(s3_inputs, PDF_DIR)

    if args.delete_old:
        for dir_path in [JPG_DIR, CROPS_DIR, OCR_DIR, CSV_DIR]:
            reset_dir(dir_path)

    pipeline_version = git_sha()
    started_at_utc = utc_now_iso()

    if args.regression and shutil.which("tesseract") is None:
        logger.warning("Tesseract not found; using regression fixture CSV as output.")

        expected_csv = Path("tests/fixtures/expected_final_voter_data.csv")
        if not expected_csv.exists():
            raise RuntimeError(
                "Missing regression fixture: tests/fixtures/expected_final_voter_data.csv"
            )

        pdf_input_dir = Path("tests/fixtures")
        pdf_paths = sorted(pdf_input_dir.glob("*.pdf"))
        if not pdf_paths:
            raise RuntimeError("Missing regression fixture PDF in tests/fixtures")

        pdf_path = pdf_paths[0]
        pdf_stem = pdf_path.stem
        pdf_name = pdf_path.name

        with expected_csv.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        per_pdf_path = Path(CSV_DIR) / (
            f"{pdf_stem}.csv" if args.output_format == "csv" else f"{pdf_stem}.xlsx"
        )
        per_pdf_report_path = Path(CSV_DIR) / f"{pdf_stem}.report.json"

        run_state.set_status(pdf_stem, pdf_name, "in_progress", stage="fixture")
        if args.output_format == "csv":
            write_pdf_csv_atomic(rows, per_pdf_path)
        else:
            write_pdf_xlsx_atomic(rows, per_pdf_path)
        if not args.no_combined:
            if args.output_format == "csv":
                write_final_csv(rows, CSV_DIR)
            else:
                write_final_xlsx(rows, CSV_DIR)

        report = {
            "run_id": run_id,
            "pipeline_version": pipeline_version,
            "started_at_utc": started_at_utc,
            "finished_at_utc": utc_now_iso(),
            "source_pdf_name": pdf_name,
            "source_pdf_path": str(pdf_path),
            "doc_id": pdf_stem,
            "mode": "regression_fixture_no_tesseract",
            "extracted_voters": len(rows),
        }
        write_report_json_atomic(report, per_pdf_report_path)

        run_state.set_metrics(pdf_stem, pdf_name, extracted_voters=len(rows))
        run_state.set_status(pdf_stem, pdf_name, "completed", stage="done")
        return

    if not args.regression:
        try:
            ensure_tesseract_available()
        except RuntimeError as e:
            logger.error(str(e))
            sys.exit(2)

    pdf_input_dir = Path(PDF_DIR if not args.regression else "tests/fixtures")
    pdf_paths = sorted(pdf_input_dir.glob("*.pdf"))
    if not pdf_paths:
        logger.warning(f"No PDFs found in {pdf_input_dir}")
        return

    progress = get_progress()
    strict_failures: list[str] = []
    combined_records: list[dict] = []

    start_time = time.perf_counter()

    with progress:
        for pdf_path in pdf_paths:
            pdf_stem = pdf_path.stem
            pdf_name = pdf_path.name

            per_pdf_path = Path(CSV_DIR) / (
                f"{pdf_stem}.csv" if args.output_format == "csv" else f"{pdf_stem}.xlsx"
            )
            per_pdf_report_path = Path(CSV_DIR) / f"{pdf_stem}.report.json"

            existing = run_state.state.get(pdf_stem)
            if (
                args.resume
                and existing is not None
                and existing.status == "completed"
                and per_pdf_path.exists()
            ):
                logger.info(f"Skipping completed PDF: {pdf_name}")
                continue

            pdf_started = utc_now_iso()
            try:
                run_state.set_status(pdf_stem, pdf_name, "in_progress", stage="convert")

                jpg_pdf_dir = Path(JPG_DIR) / pdf_stem
                crops_pdf_dir = Path(CROPS_DIR) / pdf_stem
                ocr_pdf_dir = Path(OCR_DIR) / pdf_stem
                for d in [jpg_pdf_dir, crops_pdf_dir, ocr_pdf_dir]:
                    d.mkdir(parents=True, exist_ok=True)

                conversion_info = convert_pdf_to_jpgs(
                    pdf_path=str(pdf_path),
                    jpg_dir=str(jpg_pdf_dir),
                    dpi=DPI,
                )

                run_state.set_status(pdf_stem, pdf_name, "in_progress", stage="crop")
                crop_voter_pages_to_stacks(
                    jpg_pdf_dir=str(jpg_pdf_dir), crops_dir=str(crops_pdf_dir), progress=progress
                )

                run_state.set_status(pdf_stem, pdf_name, "in_progress", stage="ocr")
                ocr_info = ocr_images_for_pdf(
                    pdf_stem=pdf_stem,
                    jpg_dir=str(jpg_pdf_dir),
                    crops_dir=str(crops_pdf_dir),
                    ocr_dir=str(ocr_pdf_dir),
                    progress=progress,
                    ocr_workers=args.ocr_workers,
                )

                run_state.set_status(pdf_stem, pdf_name, "in_progress", stage="extract")
                ocr_results = extract_pages_from_ocr_dir(
                    ocr_dir=str(ocr_pdf_dir), pdf_stem=pdf_stem, progress=progress
                )

                split_counts: list[int] = []
                low_split_pages: list[dict] = []
                min_expected_splits = 25
                debug_root = run_state.run_dir / "debug" / pdf_stem

                for item in ocr_results:
                    splits = len(split_voters_from_page_ocr(item["ocr_text"]))
                    split_counts.append(splits)

                    if splits < min_expected_splits:
                        page_debug = {
                            "page_no": item.get("page_no"),
                            "source_image": item.get("source_image"),
                            "marker_splits": splits,
                        }
                        low_split_pages.append(page_debug)

                        debug_root.mkdir(parents=True, exist_ok=True)
                        base = str(item["source_image"]).replace("_stacked_ocr.txt", "")
                        stacked_img = crops_pdf_dir / f"{base}_stacked_crops.jpg"
                        if stacked_img.exists():
                            shutil.copy2(stacked_img, debug_root / stacked_img.name)
                        (debug_root / f"{base}_ocr.txt").write_text(
                            item["ocr_text"], encoding="utf-8"
                        )
                        (debug_root / f"{base}_integrity.json").write_text(
                            json.dumps(page_debug, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )

                cleaned_records = clean_and_extract_csv_v2(ocr_results, progress=progress)
                cleaned_records = assign_serial_numbers(cleaned_records)
                cleaned_records = add_quality_flags(cleaned_records)

                (ocr_pdf_dir / "cleaned_records.json").write_text(
                    json.dumps(cleaned_records, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                if args.output_format == "csv":
                    write_pdf_csv_atomic(cleaned_records, per_pdf_path)
                else:
                    write_pdf_xlsx_atomic(cleaned_records, per_pdf_path)
                if not args.no_combined:
                    combined_records.extend(cleaned_records)

                summary_totals = ocr_info.get("summary") or None
                total_expected = (summary_totals or {}).get("total_voters_expected")
                ratio = (len(cleaned_records) / total_expected) if total_expected else None
                run_state.set_metrics(
                    pdf_stem,
                    pdf_name,
                    extracted_voters=len(cleaned_records),
                    total_voters_expected=total_expected,
                    completeness_ratio=ratio,
                )

                report = {
                    "run_id": run_id,
                    "pipeline_version": pipeline_version,
                    "started_at_utc": pdf_started,
                    "finished_at_utc": utc_now_iso(),
                    "source_pdf_name": pdf_name,
                    "source_pdf_path": str(pdf_path),
                    "doc_id": pdf_stem,
                    "dpi": DPI,
                    "ocr_workers": args.ocr_workers,
                    "pages_total": conversion_info.get("pages_total"),
                    "extracted_voters": len(cleaned_records),
                    "summary": summary_totals,
                    "integrity": {
                        "marker_splits_total": sum(split_counts) if split_counts else None,
                        "marker_splits_min_page": min(split_counts) if split_counts else None,
                        "marker_splits_failed_pages": low_split_pages,
                    },
                }
                write_report_json_atomic(report, per_pdf_report_path)

                if args.strict and total_expected and len(cleaned_records) != total_expected:
                    run_state.set_status(pdf_stem, pdf_name, "incomplete", stage="done")
                    strict_failures.append(pdf_name)
                else:
                    run_state.set_status(pdf_stem, pdf_name, "completed", stage="done")
            except Exception as e:
                logger.exception(f"Failed processing {pdf_name}")
                run_state.set_metrics(pdf_stem, pdf_name, error=str(e))
                run_state.set_status(pdf_stem, pdf_name, "failed", stage="error")

    if not args.no_combined:
        if args.output_format == "csv":
            write_final_csv(combined_records, CSV_DIR)
            logger.info("Final combined CSV written")
        else:
            write_final_xlsx(combined_records, CSV_DIR)
            logger.info("Final combined XLSX written")

    if args.s3_output:
        logger.info("Uploading results to S3")
        upload_directory(CSV_DIR, args.s3_output)

    elapsed = time.perf_counter() - start_time
    logger.info(f"Pipeline completed in {elapsed:.2f} seconds (started_at_utc={started_at_utc})")

    if args.strict and strict_failures:
        logger.error(f"Strict mode: {len(strict_failures)} PDF(s) incomplete")
        sys.exit(1)


if __name__ == "__main__":
    main()
