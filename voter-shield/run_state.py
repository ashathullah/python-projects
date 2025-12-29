from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PdfState:
    pdf_name: str
    status: str = "pending"  # pending|in_progress|completed|failed|incomplete
    stage: str | None = None
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    extracted_voters: int | None = None
    total_voters_expected: int | None = None
    completeness_ratio: float | None = None
    warnings: str | None = None
    error: str | None = None


@dataclass
class RunState:
    run_id: str
    root_dir: Path = Path("runs")
    state: dict[str, PdfState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)

    @property
    def run_dir(self) -> Path:
        return self.root_dir / self.run_id

    @property
    def events_path(self) -> Path:
        return self.run_dir / "events.jsonl"

    @property
    def progress_path(self) -> Path:
        return self.run_dir / "progress.csv"

    def log_event(self, event_type: str, pdf_stem: str, **fields: Any) -> None:
        event = {"ts_utc": utc_now_iso(), "event": event_type, "pdf_stem": pdf_stem, **fields}
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def upsert_pdf(self, pdf_stem: str, pdf_name: str) -> PdfState:
        if pdf_stem not in self.state:
            self.state[pdf_stem] = PdfState(pdf_name=pdf_name)
        return self.state[pdf_stem]

    def set_status(
        self, pdf_stem: str, pdf_name: str, status: str, stage: str | None = None
    ) -> None:
        s = self.upsert_pdf(pdf_stem, pdf_name)
        if status == "in_progress" and s.started_at_utc is None:
            s.started_at_utc = utc_now_iso()
        if status in {"completed", "failed", "incomplete"}:
            s.finished_at_utc = utc_now_iso()
        s.status = status
        if stage is not None:
            s.stage = stage
        self.log_event("status", pdf_stem, status=status, stage=stage)
        self.write_snapshot()

    def set_metrics(
        self,
        pdf_stem: str,
        pdf_name: str,
        *,
        extracted_voters: int | None = None,
        total_voters_expected: int | None = None,
        completeness_ratio: float | None = None,
        warnings: str | None = None,
        error: str | None = None,
    ) -> None:
        s = self.upsert_pdf(pdf_stem, pdf_name)
        if extracted_voters is not None:
            s.extracted_voters = extracted_voters
        if total_voters_expected is not None:
            s.total_voters_expected = total_voters_expected
        if completeness_ratio is not None:
            s.completeness_ratio = completeness_ratio
        if warnings is not None:
            s.warnings = warnings
        if error is not None:
            s.error = error
        self.log_event(
            "metrics",
            pdf_stem,
            extracted_voters=extracted_voters,
            total_voters_expected=total_voters_expected,
            completeness_ratio=completeness_ratio,
            warnings=warnings,
            error=error,
        )
        self.write_snapshot()

    def write_snapshot(self) -> None:
        fieldnames = [
            "pdf_stem",
            "pdf_name",
            "status",
            "stage",
            "started_at_utc",
            "finished_at_utc",
            "extracted_voters",
            "total_voters_expected",
            "completeness_ratio",
            "warnings",
            "error",
        ]
        with self.progress_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for pdf_stem in sorted(self.state.keys()):
                s = self.state[pdf_stem]
                writer.writerow(
                    {
                        "pdf_stem": pdf_stem,
                        "pdf_name": s.pdf_name,
                        "status": s.status,
                        "stage": s.stage,
                        "started_at_utc": s.started_at_utc,
                        "finished_at_utc": s.finished_at_utc,
                        "extracted_voters": s.extracted_voters,
                        "total_voters_expected": s.total_voters_expected,
                        "completeness_ratio": s.completeness_ratio,
                        "warnings": s.warnings,
                        "error": s.error,
                    }
                )

    @classmethod
    def load(cls, run_id: str, root_dir: Path = Path("runs")) -> RunState:
        rs = cls(run_id=run_id, root_dir=root_dir)
        if not rs.progress_path.exists():
            return rs
        with rs.progress_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = row.get("status") or "pending"
                if status == "in_progress":
                    status = "pending"
                rs.state[row["pdf_stem"]] = PdfState(
                    pdf_name=row.get("pdf_name") or row["pdf_stem"],
                    status=status,
                    stage=row.get("stage") or None,
                    started_at_utc=row.get("started_at_utc") or None,
                    finished_at_utc=row.get("finished_at_utc") or None,
                    extracted_voters=_to_int(row.get("extracted_voters")),
                    total_voters_expected=_to_int(row.get("total_voters_expected")),
                    completeness_ratio=_to_float(row.get("completeness_ratio")),
                    warnings=row.get("warnings") or None,
                    error=row.get("error") or None,
                )
        return rs


def _to_int(v: str | None) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _to_float(v: str | None) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None
