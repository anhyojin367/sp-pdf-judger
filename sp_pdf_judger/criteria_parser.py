from __future__ import annotations

import re
from dataclasses import dataclass

from .unit_normalizer import ParsedMeasurement, parse_number_and_unit
from .utils import clean_text


@dataclass
class ParsedCriteria:
    kind: str
    comparator: str | None = None
    threshold: ParsedMeasurement | None = None
    lower: ParsedMeasurement | None = None
    upper: ParsedMeasurement | None = None
    raw: str = ""


def parse_criteria_text(criteria: str | None) -> ParsedCriteria:
    raw = clean_text(criteria)
    if not raw:
        return ParsedCriteria(kind="unknown", raw=raw)

    m_range = re.search(r"(\d+(?:\.\d+)?)\s*~\s*(\d+(?:\.\d+)?)\s*([A-Za-zμ%/²0-9\-\.·]*)", raw)
    if m_range:
        lo = parse_number_and_unit(f"{m_range.group(1)} {m_range.group(3)}")
        hi = parse_number_and_unit(f"{m_range.group(2)} {m_range.group(3)}")
        return ParsedCriteria(kind="range", lower=lo, upper=hi, raw=raw)

    for ko, op in [("이하", "<="), ("미만", "<"), ("이상", ">="), ("초과", ">")]:
        if ko in raw:
            base = raw.split(ko, 1)[0].strip()
            threshold = parse_number_and_unit(base)
            if threshold:
                return ParsedCriteria(kind="compare", comparator=op, threshold=threshold, raw=raw)

    if "일치" in raw or "검출" in raw:
        threshold = parse_number_and_unit(raw)
        if threshold:
            if "일치" in raw:
                return ParsedCriteria(kind="compare", comparator=">=", threshold=threshold, raw=raw)
            return ParsedCriteria(kind="compare", comparator="<=", threshold=threshold, raw=raw)

    threshold = parse_number_and_unit(raw)
    if threshold:
        return ParsedCriteria(kind="exact", comparator="==", threshold=threshold, raw=raw)

    return ParsedCriteria(kind="unknown", raw=raw)
