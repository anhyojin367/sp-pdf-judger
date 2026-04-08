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
    "µg": 1e-6,
    "ng": 1e-9,
}

VOLUME_FACTORS = {
    "L": 1.0,
    "l": 1.0,
    "mL": 1e-3,
    "ml": 1e-3,
    "uL": 1e-6,
    "μL": 1e-6,
    "µL": 1e-6,
}

AMOUNT_FACTORS = {
    "mol": 1.0,
    "mmol": 1e-3,
    "umol": 1e-6,
    "μmol": 1e-6,
    "µmol": 1e-6,
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
    "CFU/10mL",
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
    "ug/DU",
    "μg/DU",
    "µg/DU",
    "LD50/mL",
    "LD40/mL",
    "mmol/L",
    "umol/L",
    "μmol/L",
    "µmol/L",
    "mol/L",
    "mm[Hg]",
    "mmHg",
    "mL",
    "ml",
    "uL",
    "μL",
    "µL",
    "kg",
    "mg",
    "μg",
    "µg",
    "ug",
    "ng",
    "g",
    "mmol",
    "umol",
    "μmol",
    "µmol",
    "mol",
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


def _normalize_measurement_text(text: str) -> str:
    text = clean_text(text)
    if not text:
        return ""

    replacements = {
        "µ": "μ",
        "㎍": "ug",
        "㎕": "uL",
        "㎖": "mL",
        "℃": "°C",
        " of protein/DU": "/DU",
        " ofprotein/DU": "/DU",
        "of protein/DU": "/DU",
        "ofprotein/DU": "/DU",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    text = re.sub(r"(u|μ)g\s*/\s*DU", lambda m: f"{m.group(1)}g/DU", text)
    text = re.sub(r"(u|μ)g\s+of\s+protein\s*/\s*DU", lambda m: f"{m.group(1)}g/DU", text, flags=re.I)
    text = re.sub(r"(u|μ)g\s*ofprotein\s*/\s*DU", lambda m: f"{m.group(1)}g/DU", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_unit_alias(unit: str) -> str:
    aliases = {
        "％": "%",
        "㎖": "mL",
        "ℓ": "L",
        "µ": "μ",
        "µg": "μg",
        "µL": "μL",
        "µmol": "μmol",
        "µg/DU": "μg/DU",
        "㎍": "ug",
        "㎕": "uL",
        "㎛": "um",
        "mmHg": "mm[Hg]",
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

    m = re.match(r"([A-Za-zμµ%/²0-9\-\.\[\]]+)", tail)
    if m:
        return _normalize_unit_alias(m.group(1))

    return ""


def parse_number_and_unit(text: str | None) -> Optional[ParsedMeasurement]:
    if not text:
        return None

    text = _normalize_measurement_text(text)
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
        canonical_value = value * FRACTION_FACTORS[unit]
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

        if num_u in AMOUNT_FACTORS and den_u in VOLUME_FACTORS:
            canonical = "mol/L"
            value_canonical = value * AMOUNT_FACTORS[num_u] / VOLUME_FACTORS[den_u]
            return ParsedMeasurement(
                value=value,
                unit_raw=unit,
                unit_canonical=canonical,
                value_canonical=value_canonical,
                pretty=f"{_pretty_number(value_canonical)} {canonical}",
            )

        if num_u in MASS_FACTORS and den_u == "DU":
            canonical = "g/DU"
            value_canonical = value * MASS_FACTORS[num_u]
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

    if unit in AMOUNT_FACTORS:
        canonical_value = value * AMOUNT_FACTORS[unit]
        return ParsedMeasurement(
            value=value,
            unit_raw=unit,
            unit_canonical="mol",
            value_canonical=canonical_value,
            pretty=f"{_pretty_number(canonical_value)} mol",
        )

    if unit in {"mm[Hg]"}:
        return ParsedMeasurement(
            value=value,
            unit_raw=unit,
            unit_canonical="mm[Hg]",
            value_canonical=value,
            pretty=f"{_pretty_number(value)} mm[Hg]",
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