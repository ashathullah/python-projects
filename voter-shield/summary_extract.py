from __future__ import annotations

import re

TAMIL_TOTAL = "மொத்தம்"


def parse_summary_totals(ocr_text: str) -> dict[str, int | None]:
    """
    Best-effort extraction of totals from the last (summary) page OCR.
    """

    if not ocr_text:
        return {
            "total_male": None,
            "total_female": None,
            "total_third_gender": None,
            "total_voters_expected": None,
        }

    text = ocr_text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)

    def first_int(pat: str) -> int | None:
        m = re.search(pat, text, flags=re.IGNORECASE | re.MULTILINE)
        if not m:
            return None
        try:
            return int(m.group(1))
        except ValueError:
            return None

    total_male = first_int(r"\bMale\b[^0-9]{0,20}(\d{1,7})")
    total_female = first_int(r"\bFemale\b[^0-9]{0,20}(\d{1,7})")
    total_third_gender = first_int(r"\bThird\s*Gender\b[^0-9]{0,20}(\d{1,7})")

    total = first_int(r"\bTotal\b[^0-9]{0,30}(\d{1,7})")
    if total is None and TAMIL_TOTAL in text:
        total = first_int(rf"{re.escape(TAMIL_TOTAL)}[^0-9]{{0,30}}(\d{{1,7}})")

    return {
        "total_male": total_male,
        "total_female": total_female,
        "total_third_gender": total_third_gender,
        "total_voters_expected": total,
    }
