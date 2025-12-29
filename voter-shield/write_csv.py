from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path

from openpyxl import Workbook


def _fieldnames_for_records(cleaned_records: list[dict]) -> list[str]:
    all_fieldnames: set[str] = set()
    for record in cleaned_records:
        all_fieldnames.update(record.keys())

    preferred_order = [
        "assembly",
        "part_no",
        "street",
        "serial_no",
        "epic_id",
        "name",
        "father_name",
        "mother_name",
        "husband_name",
        "other_name",
        "house_no",
        "age",
        "gender",
        "TOTAL_FLAGS",
        "FLAG_REASONS",
        "EXPLANATION_1",
    ]

    filtered_columns = ["source_image", "ocr_text", "doc_id", "page_no", "voter_no"]

    return [f for f in preferred_order if f in all_fieldnames] + [
        f for f in sorted(all_fieldnames) if f not in preferred_order and f not in filtered_columns
    ]


def _xlsx_cell(v):
    if v is None:
        return ""
    if isinstance(v, str | int | float | bool):
        return v
    return json.dumps(v, ensure_ascii=False)


def write_pdf_csv_atomic(cleaned_records: list[dict], csv_path: Path) -> None:
    """
    Writes a per-PDF CSV to an explicit path using an atomic replace.
    """

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = _fieldnames_for_records(cleaned_records)

    with tempfile.NamedTemporaryFile(
        mode="w",
        newline="",
        encoding="utf-8",
        delete=False,
        dir=str(csv_path.parent),
        prefix=csv_path.stem + ".",
        suffix=".tmp",
    ) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in cleaned_records:
            writer.writerow(record)
        tmp_path = Path(tmp.name)

    os.replace(tmp_path, csv_path)


def write_pdf_xlsx_atomic(cleaned_records: list[dict], xlsx_path: Path) -> None:
    """
    Writes a per-PDF XLSX to an explicit path using an atomic replace.
    """

    xlsx_path = Path(xlsx_path)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = _fieldnames_for_records(cleaned_records)

    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=str(xlsx_path.parent),
        prefix=xlsx_path.stem + ".",
        suffix=".tmp",
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        wb = Workbook(write_only=True)
        ws = wb.create_sheet(title="voters")
        ws.append(fieldnames)
        for record in cleaned_records:
            ws.append([_xlsx_cell(record.get(k)) for k in fieldnames])
        wb.save(tmp_path)
        wb.close()
        os.replace(tmp_path, xlsx_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def write_final_csv(cleaned_records: list[dict], csv_dir: str) -> None:
    """
    Backwards-compatible combined output CSV (`csv/final_voter_data.csv`).
    """

    csv_dir_path = Path(csv_dir)
    csv_dir_path.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir_path / "final_voter_data.csv"

    write_pdf_csv_atomic(cleaned_records, csv_path)
    print(f"Final CSV (voters: {len(cleaned_records)}) written to {csv_path}")


def write_final_xlsx(cleaned_records: list[dict], out_dir: str) -> None:
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    xlsx_path = out_dir_path / "final_voter_data.xlsx"

    write_pdf_xlsx_atomic(cleaned_records, xlsx_path)
    print(f"Final XLSX (voters: {len(cleaned_records)}) written to {xlsx_path}")


def write_report_json_atomic(report: dict, report_path: Path) -> None:
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=str(report_path.parent),
        prefix=report_path.stem + ".",
        suffix=".tmp",
    ) as tmp:
        json.dump(report, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)

    os.replace(tmp_path, report_path)
