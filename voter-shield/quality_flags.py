from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FlagResult:
    total_flags: int
    reasons: list[str]
    explanation: str | None


def flag_record(record: dict) -> FlagResult:
    reasons: list[str] = []

    def missing(key: str) -> bool:
        v = record.get(key)
        return v is None or (isinstance(v, str) and v.strip() == "")

    if missing("epic_id"):
        reasons.append("missing_epic_id")
    if missing("name"):
        reasons.append("missing_name")
    if missing("house_no"):
        reasons.append("missing_house_no")
    if missing("age"):
        reasons.append("missing_age")
    if missing("gender"):
        reasons.append("missing_gender")

    explanation = None
    if reasons:
        explanation = "Missing: " + ", ".join(r.replace("missing_", "") for r in reasons)

    return FlagResult(total_flags=len(reasons), reasons=reasons, explanation=explanation)


def add_quality_flags(records: list[dict]) -> list[dict]:
    """
    Adds 3 columns for downstream QC:
    - TOTAL_FLAGS: int
    - FLAG_REASONS: semicolon-separated string
    - EXPLANATION_1: short human-readable summary
    """

    for r in records:
        fr = flag_record(r)
        r["TOTAL_FLAGS"] = fr.total_flags
        r["FLAG_REASONS"] = ";".join(fr.reasons) if fr.reasons else ""
        r["EXPLANATION_1"] = fr.explanation or ""
    return records
