from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .utils import clean_text


@dataclass
class ParsedMeasurement:
    value: float
    unit_raw: str
    unit_canonical: str
    value_canonical: float
    pretty: str


MASS_FACTORS = {
    "g": 1.0,
    "mg": 1e-3,
    "ug": 1e-6,
    "μg": 1e-6,
    "ng": 1e-9,
}

VOLUME_FACTORS = {
    "L": 1.0,
    "l": 1.0,
    "mL": 1e-3,
    "ml": 1e-3,
    "uL": 1e-6,
    "μL": 1e-6,
}

FRACTION_FACTORS = {
    "%": 1e-2,
    "ppm": 1e-6,
    "ppb": 1e-9,
    "ppth": 1e-3,
}

OSMOLALITY_FACTORS = {
    "Osm/kg": 1.0,
    "mOsm/kg": 1e-3,
}

DIMENSIONLESS_UNITS = {
    "",
    "배",
    "비중",
    "ratio",
    "scalar",
}

KNOWN_UNIT_PREFIXES = [
    "mOsm/kg",
    "Osm/kg",
    "CFU/mL",
    "CFU/ml",
    "CFU/m",
    "PFU/mL",
    "PFU/ml",
    "PFU/m",
    "EU/mL",
    "EU/ml",
    "IU/mL",
    "IU/ml",
    "LD50/mL",
    "LD40/mL",
    "mL",
    "ml",
    "uL",
    "μL",
    "kg",
    "mg",
    "μg",
    "ug",
    "ng",
    "g",
    "ppm",
    "ppb",
    "ppth",
    "%",
    "배",
    "비중",
    "pH",
]


def _pretty_number(value: float) -> str:
    return f"{value:.12g}"


def _normalize_unit_alias(unit: str) -> str:
    aliases = {
        "％": "%",
        "㎖": "mL",
        "ℓ": "L",
    }
    return aliases.get(unit, unit)


def _extract_unit_prefix(tail: str) -> str:
    tail = clean_text(tail)
    if not tail:
        return ""

    tail = re.sub(r"^[~\-=:：\s]+", "", tail)

    for unit in sorted(KNOWN_UNIT_PREFIXES, key=len, reverse=True):
        if tail.startswith(unit):
            return _normalize_unit_alias(unit)

    # 알려진 단위가 아니면 한글이 나오기 전까지의 비한글 토큰만 unit 후보로 사용
    m = re.match(r"([A-Za-zμ%/²0-9\-\.]+)", tail)
    if m:
        return _normalize_unit_alias(m.group(1))

    return ""


def parse_number_and_unit(text: str | None) -> Optional[ParsedMeasurement]:
    if not text:
        return None

    text = clean_text(text)
    m = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not m:
        return None

    value = float(m.group(1))
    tail = text[m.end():]
    unit = _extract_unit_prefix(tail)

    if "pH" in text or unit.lower() == "ph":
        return ParsedMeasurement(
            value=value,
            unit_raw="pH",
            unit_canonical="pH",
            value_canonical=value,
            pretty=f"{_pretty_number(value)} pH",
        )

    if unit in FRACTION_FACTORS:
        factor = FRACTION_FACTORS[unit]
        canonical_value = value * factor
        return ParsedMeasurement(
            value=value,
            unit_raw=unit,
            unit_canonical="fraction",
            value_canonical=canonical_value,
            pretty=f"{_pretty_number(canonical_value)} fraction",
        )

    if unit in OSMOLALITY_FACTORS:
        canonical_value = value * OSMOLALITY_FACTORS[unit]
        return ParsedMeasurement(
            value=value,
            unit_raw=unit,
            unit_canonical="Osm/kg",
            value_canonical=canonical_value,
            pretty=f"{_pretty_number(canonical_value)} Osm/kg",
        )

    if "/" in unit:
        num_u, den_u = unit.split("/", 1)
        num_u = num_u.strip()
        den_u = den_u.strip()

        if num_u in MASS_FACTORS and den_u in VOLUME_FACTORS:
            canonical = "g/L"
            value_canonical = value * MASS_FACTORS[num_u] / VOLUME_FACTORS[den_u]
            return ParsedMeasurement(
                value=value,
                unit_raw=unit,
                unit_canonical=canonical,
                value_canonical=value_canonical,
                pretty=f"{_pretty_number(value_canonical)} {canonical}",
            )

        if num_u in {"CFU", "PFU", "EU", "IU", "LD50", "LD40"}:
            canonical = f"{num_u}/{den_u}"
            return ParsedMeasurement(
                value=value,
                unit_raw=unit,
                unit_canonical=canonical,
                value_canonical=value,
                pretty=f"{_pretty_number(value)} {canonical}",
            )

    if unit in MASS_FACTORS:
        canonical_value = value * MASS_FACTORS[unit]
        return ParsedMeasurement(
            value=value,
            unit_raw=unit,
            unit_canonical="g",
            value_canonical=canonical_value,
            pretty=f"{_pretty_number(canonical_value)} g",
        )

    if unit in VOLUME_FACTORS:
        canonical_value = value * VOLUME_FACTORS[unit]
        return ParsedMeasurement(
            value=value,
            unit_raw=unit,
            unit_canonical="L",
            value_canonical=canonical_value,
            pretty=f"{_pretty_number(canonical_value)} L",
        )

    if unit in DIMENSIONLESS_UNITS:
        return ParsedMeasurement(
            value=value,
            unit_raw=unit,
            unit_canonical="scalar",
            value_canonical=value,
            pretty=_pretty_number(value),
        )

    if "log" in text.lower():
        return ParsedMeasurement(
            value=value,
            unit_raw=unit or "log",
            unit_canonical=unit or "log",
            value_canonical=value,
            pretty=f"{_pretty_number(value)} {unit or 'log'}",
        )

    return ParsedMeasurement(
        value=value,
        unit_raw=unit,
        unit_canonical=unit or "scalar",
        value_canonical=value,
        pretty=_pretty_number(value) if not unit else f"{_pretty_number(value)} {unit}",
    )