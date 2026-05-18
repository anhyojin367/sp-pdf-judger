from __future__ import annotations
from .permit_rules import apply_permit_rule
import re

from .config import FAIL_LABEL, HOLD_LABEL, PASS_LABEL
from .criteria_parser import parse_criteria_text
from .llm import GeminiJudgeClient
from .rag import UcumRagStore
from .schemas import Evaluation, ExtractedRecord
from .unit_normalizer import ParsedMeasurement, parse_number_and_unit
from .utils import clean_text


PASS_REASON_WORD = "검수합격"
FAIL_REASON_WORD = "검수불합격"
HOLD_REASON_WORD = "검수보류"


def _same_or_convertible(a: ParsedMeasurement, b: ParsedMeasurement) -> bool:
    if a.unit_canonical == b.unit_canonical:
        return True
    if "scalar" in {a.unit_canonical, b.unit_canonical}:
        return True
    return False


def _compare(a: float, op: str, b: float) -> bool:
    if op == "<=":
        return a <= b
    if op == "<":
        return a < b
    if op == ">=":
        return a >= b
    if op == ">":
        return a > b
    if op == "==":
        return a == b
    raise ValueError(f"unknown op: {op}")


def _unit_mismatch_reason() -> str:
    return f"시험결과와 시험기준의 단위가 일치하지 않아 {FAIL_REASON_WORD}으로 판단했습니다."


def _compare_reason(op: str, ok: bool) -> str:
    if op == "<":
        return (
            f"시험결과가 시험기준보다 낮아 {PASS_REASON_WORD}으로 판단했습니다."
            if ok
            else f"시험결과가 시험기준보다 낮지 않아 {FAIL_REASON_WORD}으로 판단했습니다."
        )
    if op == "<=":
        return (
            f"시험결과가 시험기준 이하라 {PASS_REASON_WORD}으로 판단했습니다."
            if ok
            else f"시험결과가 시험기준을 초과해 {FAIL_REASON_WORD}으로 판단했습니다."
        )
    if op == ">":
        return (
            f"시험결과가 시험기준보다 높아 {PASS_REASON_WORD}으로 판단했습니다."
            if ok
            else f"시험결과가 시험기준보다 높지 않아 {FAIL_REASON_WORD}으로 판단했습니다."
        )
    if op == ">=":
        return (
            f"시험결과가 시험기준 이상이라 {PASS_REASON_WORD}으로 판단했습니다."
            if ok
            else f"시험결과가 시험기준보다 낮아 {FAIL_REASON_WORD}으로 판단했습니다."
        )
    if op == "==":
        return (
            f"시험결과가 시험기준과 같아 {PASS_REASON_WORD}으로 판단했습니다."
            if ok
            else f"시험결과가 시험기준과 달라 {FAIL_REASON_WORD}으로 판단했습니다."
        )
    return "시험결과와 시험기준을 비교해 판단했습니다."


def _normalize_table_text(text: str | None) -> str:
    text = clean_text(text)
    if not text:
        return ""

    text = text.replace("\\r\\n", "\n").replace("\\n", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def _status_from_text_result(result_text: str | None) -> tuple[str | None, str | None]:
    text = clean_text(result_text)
    if not text:
        return None, None

    compact = text.replace(" ", "")

    if "부적합" in compact or "불합격" in compact:
        return FAIL_LABEL, f"시험결과가 '{text}'로 기재되어 {FAIL_REASON_WORD}으로 판단했습니다."

    if "적합" in compact or "합격" in compact:
        return PASS_LABEL, f"시험결과가 '{text}'로 기재되어 {PASS_REASON_WORD}으로 판단했습니다."

    return None, None


def _normalize_inline_pipe_table(text: str) -> str:
    text = _normalize_table_text(text)

    for header in ["시험결과", "실험결과", "측정결과"]:
        text = re.sub(
            rf"({header})\s+([^|\n]+?)\s*\|",
            r"\1 | \2 |",
            text,
        )

    text = re.sub(
        r"(적합|부적합|합격|불합격)\s+([^|\n]+?)\s*\|",
        r"\1 | \2 |",
        text,
    )

    return text


def _split_pipe_cells(line: str) -> list[str]:
    return [clean_text(x) for x in line.split("|") if clean_text(x)]


def _parse_horizontal_result_table(result: str | None) -> list[dict[str, str]]:
    text = _normalize_table_text(result)
    if not text or "|" not in text:
        return []

    lines = [clean_text(x) for x in text.splitlines() if clean_text(x) and "|" in x]
    if not lines:
        return []

    first_cells = [_split_pipe_cells(line)[0] for line in lines if _split_pipe_cells(line)]
    if not first_cells:
        return []

    has_lot = any("로트" in x for x in first_cells)
    has_result = any("시험결과" in x or "실험결과" in x or "측정결과" in x for x in first_cells)

    if not (has_lot and has_result):
        return []

    row_map: dict[str, list[str]] = {}
    row_order: list[str] = []

    for line in lines:
        parts = _split_pipe_cells(line)
        if len(parts) < 2:
            continue

        label = parts[0]
        values = parts[1:]

        if label not in row_map:
            row_map[label] = []
            row_order.append(label)

        row_map[label].extend(values)

    lot_row_key = next((k for k in row_order if "로트" in k), None)
    result_row_key = next((k for k in row_order if "시험결과" in k or "실험결과" in k or "측정결과" in k), None)

    if not lot_row_key or not result_row_key:
        return []

    date_row_key = next((k for k in row_order if "시험기간" in k or "시험일자" in k or "시험일" in k), None)

    lot_numbers = row_map.get(lot_row_key, [])
    results = row_map.get(result_row_key, [])
    dates = row_map.get(date_row_key, []) if date_row_key else []

    out: list[dict[str, str]] = []
    for idx, lot in enumerate(lot_numbers):
        lot_clean = clean_text(lot)
        if not lot_clean:
            continue

        date_value = clean_text(dates[idx]) if idx < len(dates) else ""
        if date_value == "페이지":
            date_value = ""

        out.append(
            {
                "item_label": "로트번호",
                "item_value": lot_clean,
                "lot_no": lot_clean,
                "test_date": date_value,
                "result": clean_text(results[idx]) if idx < len(results) else "",
            }
        )

    return out


def _parse_vertical_column_table(result: str | None) -> list[dict[str, str]]:
    text = _normalize_inline_pipe_table(result)
    if not text or "|" not in text:
        return []

    lines = [clean_text(x) for x in text.splitlines() if clean_text(x)]

    header_cells: list[str] = []
    data_cells: list[str] = []

    if len(lines) >= 2 and "|" in lines[0]:
        first_line_cells = _split_pipe_cells(lines[0])
        if any("시험결과" in c or "실험결과" in c or "측정결과" in c for c in first_line_cells):
            header_cells = first_line_cells
            for line in lines[1:]:
                data_cells.extend(_split_pipe_cells(line))

    if not header_cells:
        cells = _split_pipe_cells(text)
        result_header_idx = next(
            (
                idx
                for idx, cell in enumerate(cells)
                if "시험결과" in cell or "실험결과" in cell or "측정결과" in cell
            ),
            None,
        )

        if result_header_idx is None:
            return []

        header_cells = cells[: result_header_idx + 1]
        data_cells = cells[result_header_idx + 1 :]

    if len(header_cells) < 2 or not data_cells:
        return []

    col_count = len(header_cells)

    implicit_item_column = False
    if len(header_cells) == 2 and len(data_cells) % 3 == 0:
        implicit_item_column = True
        header_cells = ["항목"] + header_cells
        col_count = 3

    item_idx = 0
    date_idx = next(
        (
            idx
            for idx, header in enumerate(header_cells)
            if "시험기간" in header or "시험일자" in header or "시험일" in header
        ),
        None,
    )
    result_idx = next(
        (
            idx
            for idx, header in enumerate(header_cells)
            if "시험결과" in header or "실험결과" in header or "측정결과" in header
        ),
        None,
    )

    if result_idx is None:
        return []

    item_label = "항목" if implicit_item_column else (header_cells[item_idx] or "항목")

    out: list[dict[str, str]] = []
    for start in range(0, len(data_cells), col_count):
        row_cells = data_cells[start : start + col_count]
        if len(row_cells) < col_count:
            continue

        item_value = clean_text(row_cells[item_idx])
        result_value = clean_text(row_cells[result_idx])
        date_value = clean_text(row_cells[date_idx]) if date_idx is not None and date_idx < len(row_cells) else ""

        if not item_value and not result_value:
            continue

        out.append(
            {
                "item_label": item_label,
                "item_value": item_value,
                "lot_no": item_value,
                "test_date": date_value,
                "result": result_value,
            }
        )

    return out


def _parse_whitespace_table(result: str | None) -> list[dict[str, str]]:
    text = _normalize_table_text(result)
    if not text or "|" in text:
        return []

    lines = [clean_text(x) for x in text.splitlines() if clean_text(x)]
    if len(lines) < 2:
        return []

    header_idx = None
    for idx, line in enumerate(lines):
        if ("시험기간" in line or "시험일자" in line) and ("시험결과" in line or "실험결과" in line):
            header_idx = idx
            break

    if header_idx is None:
        return []

    header = lines[header_idx]
    item_label = header
    item_label = item_label.replace("시험기간", "").replace("시험일자", "").replace("시험결과", "").replace("실험결과", "")
    item_label = clean_text(item_label) or "항목"

    out: list[dict[str, str]] = []
    for line in lines[header_idx + 1:]:
        m = re.match(r"(.+?)\s+(20\d{2}[.\-/]\d{1,2})\s+(.+)$", line)
        if not m:
            continue

        out.append(
            {
                "item_label": item_label,
                "item_value": clean_text(m.group(1)),
                "lot_no": clean_text(m.group(1)),
                "test_date": clean_text(m.group(2)),
                "result": clean_text(m.group(3)),
            }
        )

    return out


def _parse_result_table(result: str | None) -> list[dict[str, str]]:
    horizontal = _parse_horizontal_result_table(result)
    if horizontal:
        return horizontal

    vertical = _parse_vertical_column_table(result)
    if vertical:
        return vertical

    whitespace = _parse_whitespace_table(result)
    if whitespace:
        return whitespace

    return []


def _looks_like_unparsed_table(result: str | None) -> bool:
    text = _normalize_table_text(result)
    if not text:
        return False

    table_markers = ["|", "시험기간", "시험일자", "시험결과", "실험결과", "로트번호", "세포", "바이러스"]
    hit = sum(1 for marker in table_markers if marker in text)

    return hit >= 2


def _extract_bp_values(text: str | None) -> list[int]:
    text = clean_text(text)
    if not text:
        return []

    values: list[int] = []

    for m in re.finditer(r"([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\s*bp", text, flags=re.I):
        value = int(m.group(1).replace(",", ""))
        values.append(value)

    return values


def _judge_bp_band_pattern(
    criteria: str | None,
    result: str | None,
    tolerance: float = 0.10,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    criteria_values = _extract_bp_values(criteria)
    result_values = _extract_bp_values(result)

    if len(criteria_values) < 1 or len(result_values) < 1:
        return None, None, None, None, None

    mismatches: list[str] = []

    for c in criteria_values:
        nearest = min(result_values, key=lambda r: abs(r - c))
        diff_ratio = abs(nearest - c) / c if c else 1.0

        if diff_ratio > tolerance:
            mismatches.append(
                f"기준 {c} bp에 대응하는 결과 {nearest} bp가 허용오차 {int(tolerance * 100)}%를 초과"
            )

    if mismatches:
        return (
            FAIL_LABEL,
            "제한효소지도분석시험의 밴드 위치가 기준과 일치하지 않아 검수불합격으로 판단했습니다. "
            + " ".join(mismatches),
            "bp_pattern",
            ", ".join(f"{x} bp" for x in criteria_values),
            ", ".join(f"{x} bp" for x in result_values),
        )

    return (
        PASS_LABEL,
        "제한효소지도분석시험의 결과 밴드 위치가 기준 밴드 위치 허용범위 내에 있어 검수합격으로 판단했습니다.",
        "bp_pattern",
        ", ".join(f"{x} bp" for x in criteria_values),
        ", ".join(f"{x} bp" for x in result_values),
    )


def _judge_loq_text(
    criteria: str | None,
    result: str | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    c = clean_text(criteria)
    r = clean_text(result)

    if not c or not r:
        return None, None, None, None, None

    c_compact = re.sub(r"\s+", "", c)
    r_compact = re.sub(r"\s+", "", r)

    if "정량한계" not in c_compact and "LOQ" not in c_compact.upper():
        return None, None, None, None, None

    if "미만" not in c_compact and "이하" not in c_compact:
        return None, None, None, None, None

    result_satisfies = (
        "정량한계미만" in r_compact
        or "LOQ미만" in r_compact.upper()
        or "불검출" in r_compact
        or "검출되지" in r_compact
    )

    if result_satisfies:
        return (
            PASS_LABEL,
            "시험결과가 정량한계 미만으로 기재되어 시험기준을 만족하므로 검수합격으로 판단했습니다.",
            "loq_text",
            c,
            r,
        )

    if "정량한계이상" in r_compact or "LOQ이상" in r_compact.upper():
        return (
            FAIL_LABEL,
            "시험결과가 정량한계 이상으로 기재되어 시험기준을 만족하지 못하므로 검수불합격으로 판단했습니다.",
            "loq_text",
            c,
            r,
        )

    return None, None, None, None, None


def _judge_qualitative_text(
    criteria: str | None,
    result: str | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    c = clean_text(criteria)
    r = clean_text(result)

    if not c or not r:
        return None, None, None, None, None

    c_compact = re.sub(r"\s+", "", c)
    r_compact = re.sub(r"\s+", "", r)

    has_qualitative_marker = any(
        marker in c_compact
        for marker in ["확인되어야", "확인되어야함", "오염이없어야", "없어야함", "검출되지않아야"]
    )

    if not has_qualitative_marker:
        return None, None, None, None, None

    checks: list[tuple[str, bool]] = []

    if "확인" in c_compact:
        checks.append(("확인", "확인" in r_compact))

    if "오염" in c_compact and ("없" in c_compact or "무" in c_compact):
        checks.append(
            (
                "오염 없음",
                "오염없" in r_compact
                or "오염이없" in r_compact
                or "오염없음" in r_compact
                or "오염이없음" in r_compact
            )
        )

    if "검출" in c_compact and ("않아야" in c_compact or "없어야" in c_compact):
        checks.append(
            (
                "불검출",
                "불검출" in r_compact
                or "검출되지" in r_compact
                or "검출안" in r_compact
            )
        )

    if checks and all(ok for _, ok in checks):
        return (
            PASS_LABEL,
            "시험결과가 정성 시험기준의 필수 조건을 만족하여 검수합격으로 판단했습니다.",
            "qualitative_text",
            c,
            r,
        )

    if checks and any(not ok for _, ok in checks):
        failed = [name for name, ok in checks if not ok]
        return (
            FAIL_LABEL,
            f"시험결과에서 정성 시험기준의 필수 조건이 확인되지 않아 검수불합격으로 판단했습니다. 미충족 항목: {', '.join(failed)}",
            "qualitative_text",
            c,
            r,
        )

    return None, None, None, None, None


def _judge_special_rule(
    criteria: str | None,
    result: str | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    for judge_func in [
        _judge_bp_band_pattern,
        _judge_loq_text,
        _judge_qualitative_text,
    ]:
        status, reason, comparator, norm_criteria, norm_result = judge_func(criteria, result)

        if status is not None:
            return status, reason, comparator, norm_criteria, norm_result

    return None, None, None, None, None


def deterministic_judge(
    criteria: str | None,
    result: str | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    parsed_criteria = parse_criteria_text(criteria)
    parsed_result = parse_number_and_unit(result)

    if parsed_result is None:
        return None, None, None, None, None

    if parsed_criteria.kind == "compare" and parsed_criteria.threshold is not None:
        th = parsed_criteria.threshold
        op = parsed_criteria.comparator or "=="

        if not _same_or_convertible(th, parsed_result):
            return FAIL_LABEL, _unit_mismatch_reason(), op, th.pretty, parsed_result.pretty

        ok = _compare(parsed_result.value_canonical, op, th.value_canonical)
        status = PASS_LABEL if ok else FAIL_LABEL
        reason = _compare_reason(op, ok)
        return status, reason, op, th.pretty, parsed_result.pretty

    if parsed_criteria.kind == "range" and parsed_criteria.lower and parsed_criteria.upper:
        lo = parsed_criteria.lower
        hi = parsed_criteria.upper

        if not (_same_or_convertible(lo, parsed_result) and _same_or_convertible(hi, parsed_result)):
            return FAIL_LABEL, _unit_mismatch_reason(), "between", f"{lo.pretty} ~ {hi.pretty}", parsed_result.pretty

        ok = lo.value_canonical <= parsed_result.value_canonical <= hi.value_canonical
        status = PASS_LABEL if ok else FAIL_LABEL

        if ok:
            reason = f"시험결과가 시험기준 범위 안에 포함되어 {PASS_REASON_WORD}으로 판단했습니다."
        else:
            reason = f"시험결과가 시험기준 범위를 벗어나 {FAIL_REASON_WORD}으로 판단했습니다."

        return status, reason, "between", f"{lo.pretty} ~ {hi.pretty}", parsed_result.pretty

    if parsed_criteria.kind == "exact" and parsed_criteria.threshold is not None:
        th = parsed_criteria.threshold

        if not _same_or_convertible(th, parsed_result):
            return FAIL_LABEL, _unit_mismatch_reason(), "==", th.pretty, parsed_result.pretty

        ok = parsed_result.value_canonical == th.value_canonical
        status = PASS_LABEL if ok else FAIL_LABEL
        reason = _compare_reason("==", ok)
        return status, reason, "==", th.pretty, parsed_result.pretty

    return None, None, None, None, parsed_result.pretty


def _extract_numeric_requirements(criteria: str | None) -> list[str]:
    text = clean_text(criteria)
    if not text:
        return []

    text = text.replace("×", "x")
    text = text.replace("％", "%")
    text = text.replace("µ", "μ")
    text = text.replace("≥", ">=")
    text = text.replace("≤", "<=")

    requirements: list[tuple[int, str]] = []

    number = r"[+-]?\d[\d,]*(?:\.\d+)?(?:\s*[xX]\s*10\s*(?:\^\s*)?[+\-]?\d+|[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)?"
    unit = r"[A-Za-zμ%/²0-9\-\.·]+(?:\s+of\s+protein)?"

    range_pattern = re.compile(
        rf"(?P<lo>{number})\s*~\s*(?P<hi>{number})\s*(?P<unit>{unit})?"
    )

    consumed_spans: list[tuple[int, int]] = []

    for m in range_pattern.finditer(text):
        unit_text = clean_text(m.group("unit") or "")
        req = f"{m.group('lo')} ~ {m.group('hi')} {unit_text}".strip()
        requirements.append((m.start(), req))
        consumed_spans.append((m.start(), m.end()))

    def is_consumed(start: int, end: int) -> bool:
        return any(not (end <= s or start >= e) for s, e in consumed_spans)

    symbol_pattern = re.compile(
        rf"(?P<op>>=|<=|>|<)\s*(?P<value>{number})\s*(?P<unit>{unit})?"
    )

    for m in symbol_pattern.finditer(text):
        if is_consumed(m.start(), m.end()):
            continue

        value = clean_text(m.group("value"))
        unit_text = clean_text(m.group("unit") or "")
        req = f"{m.group('op')} {value} {unit_text}".strip()
        requirements.append((m.start(), req))

    korean_pattern = re.compile(
        rf"(?P<value>{number})\s*(?P<unit>{unit})?\s*(?P<op>이상|이하|초과|미만)"
    )

    for m in korean_pattern.finditer(text):
        if is_consumed(m.start(), m.end()):
            continue

        value = clean_text(m.group("value"))
        unit_text = clean_text(m.group("unit") or "")
        op = clean_text(m.group("op"))
        req = f"{value} {unit_text} {op}".strip()
        requirements.append((m.start(), req))

    requirements.sort(key=lambda x: x[0])

    out: list[str] = []
    seen: set[str] = set()

    for _, req in requirements:
        normalized = re.sub(r"\s+", " ", req).strip()
        if normalized and normalized not in seen:
            out.append(normalized)
            seen.add(normalized)

    return out


def _extract_numeric_results(result: str | None) -> list[str]:
    text = clean_text(result)
    if not text:
        return []

    text = text.replace("×", "x")
    text = text.replace("％", "%")
    text = text.replace("µ", "μ")

    number = r"[+-]?\d[\d,]*(?:\.\d+)?(?:\s*[xX]\s*10\s*(?:\^\s*)?[+\-]?\d+|[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)?"
    unit = r"[A-Za-zμ%/²0-9\-\.·]+(?:\s+of\s+protein)?"

    pattern = re.compile(rf"(?P<value>{number})\s*(?P<unit>{unit})?")

    out: list[str] = []

    for m in pattern.finditer(text):
        value = clean_text(m.group("value"))
        unit_text = clean_text(m.group("unit") or "")

        if re.fullmatch(r"20\d{2}[.\-/]\d{1,2}(?:[.\-/]\d{1,2})?", value):
            continue

        item = f"{value} {unit_text}".strip()
        if item:
            out.append(item)

    return out


def _judge_multiple_numeric_requirements(
    criteria: str | None,
    result: str | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    requirements = _extract_numeric_requirements(criteria)
    results = _extract_numeric_results(result)

    if len(requirements) < 2:
        return None, None, None, None, None

    if not results and ("적합" in clean_text(result) or "합격" in clean_text(result)):
        return None, None, None, None, None

    if len(results) < len(requirements):
        missing_count = len(requirements) - len(results)

        reason = (
            f"시험기준은 {len(requirements)}개이나 시험결과는 {len(results)}개만 확인되어 "
            f"{missing_count}개 결과가 누락된 것으로 판단했습니다. "
            f"누락 가능 기준: {', '.join(requirements[len(results):])}. "
            f"따라서 {FAIL_REASON_WORD}으로 판단했습니다."
        )

        return (
            FAIL_LABEL,
            reason,
            "multiple_requirements",
            " / ".join(requirements),
            " / ".join(results) if results else "",
        )

    row_statuses: list[str] = []
    row_reasons: list[str] = []
    norm_criteria_list: list[str] = []
    norm_result_list: list[str] = []

    for req, res in zip(requirements, results):
        status, reason, comparator, norm_criteria, norm_result = deterministic_judge(req, res)

        if status is None:
            return (
                HOLD_LABEL,
                f"복수 기준 중 '{req}'와 결과 '{res}'를 자동 비교하기 어려워 사람의 확인이 필요합니다.",
                "multiple_requirements",
                " / ".join(requirements),
                " / ".join(results),
            )

        row_statuses.append(status)
        row_reasons.append(f"{req} ↔ {res}: {reason}")
        norm_criteria_list.append(norm_criteria or req)
        norm_result_list.append(norm_result or res)

    final_status = FAIL_LABEL if FAIL_LABEL in row_statuses else PASS_LABEL

    return (
        final_status,
        " ".join(row_reasons),
        "multiple_requirements",
        " / ".join(norm_criteria_list),
        " / ".join(norm_result_list),
    )


class JudgeEngine:
    def __init__(self, rag_store: UcumRagStore, llm_client: GeminiJudgeClient | None = None) -> None:
        self.rag_store = rag_store
        self.llm_client = llm_client

    def judge_record(self, record: ExtractedRecord) -> Evaluation:
        title = (
            clean_text(record.test_name)
            or clean_text(record.section_title)
            or (clean_text(record.raw_text).split("\n")[0] if clean_text(record.raw_text) else "")
            or "항목"
        )

        lot_judgements: list[dict[str, str]] = []
        table_rows = _parse_result_table(record.result)

        if table_rows:
            for row in table_rows:
                row_result = row.get("result")

                # 표 내부에서도 적합/부적합은 최우선
                status, reason = _status_from_text_result(row_result)
                comparator = None
                norm_criteria = None
                norm_result = row_result or ""

                if status is None:
                    status, reason, comparator, norm_criteria, norm_result = deterministic_judge(
                        record.criteria,
                        row_result,
                    )

                if status is None:
                    status = HOLD_LABEL
                    reason = "표 형태의 시험결과를 자동 비교하기 어려워 사람의 확인이 필요합니다."

                lot_judgements.append(
                    {
                        "item_label": row.get("item_label", "항목"),
                        "item_value": row.get("item_value", ""),
                        "lot_no": row.get("lot_no", ""),
                        "test_date": row.get("test_date", ""),
                        "result": row_result or "",
                        "status": status or "",
                        "reason": reason or "",
                        "normalized_criteria": norm_criteria or "",
                        "normalized_result": norm_result or "",
                        "comparator": comparator or "",
                    }
                )

        final_status = None
        final_reason = ""
        comparator = None
        norm_criteria = None
        norm_result = None
        comparison_completed = False
        source = "rule"

        if lot_judgements:
            comparison_completed = True

            if any(x.get("status") == FAIL_LABEL for x in lot_judgements):
                final_status = FAIL_LABEL
            elif any(x.get("status") == HOLD_LABEL for x in lot_judgements):
                final_status = HOLD_LABEL
            else:
                final_status = PASS_LABEL

            final_reason = " ".join(
                f"{x.get('item_value') or x.get('lot_no')}는 {x.get('reason')}"
                for x in lot_judgements
                if (x.get("item_value") or x.get("lot_no")) and x.get("reason")
            )

            norm_criteria = next(
                (x.get("normalized_criteria") for x in lot_judgements if x.get("normalized_criteria")),
                None,
            )

        elif _looks_like_unparsed_table(record.result):
            comparison_completed = True
            final_status = HOLD_LABEL
            final_reason = "시험결과가 표 형태로 보이나 자동으로 행과 열을 확정하기 어려워 사람의 확인이 필요합니다."

        elif record.criteria and record.result:
            # 1순위: 결과에 적합/부적합이 직접 있으면 무조건 우선
            status, rule_reason = _status_from_text_result(record.result)

            if status is not None:
                comparison_completed = True
                final_status = status
                final_reason = rule_reason or ""
                comparator = "text_result"
                norm_criteria = clean_text(record.criteria)
                norm_result = clean_text(record.result)

            else:
                # 2순위: 허가서 YAML 기반 판정
                permit_decision = apply_permit_rule(record)

                if permit_decision is not None and permit_decision.status is not None:
                    comparison_completed = True
                    final_status = permit_decision.status
                    final_reason = permit_decision.reason or ""
                    comparator = permit_decision.comparator
                    norm_criteria = permit_decision.normalized_criteria
                    norm_result = permit_decision.normalized_result
                    source = "permit"

                else:
                    # 3순위: 특수 규칙
                    status, rule_reason, comparator, norm_criteria, norm_result = _judge_special_rule(
                        record.criteria,
                        record.result,
                    )

                    if status is None:
                        status, rule_reason, comparator, norm_criteria, norm_result = _judge_multiple_numeric_requirements(
                            record.criteria,
                            record.result,
                        )

                    if status is None:
                        status, rule_reason, comparator, norm_criteria, norm_result = deterministic_judge(
                            record.criteria,
                            record.result,
                        )

                    if status is not None:
                        comparison_completed = True
                        final_status = status
                        final_reason = rule_reason or ""

                    elif self.llm_client is not None:
                        query = " ".join(
                            filter(
                                None,
                                [
                                    record.test_name,
                                    record.criteria,
                                    record.result,
                                    record.method,
                                    record.test_date,
                                    record.test_period,
                                    record.remarks,
                                    record.raw_text,
                                ],
                            )
                        )
                        rag_docs = self.rag_store.search(query, top_k=7)
                        rag_contexts = [d.text for d in rag_docs]

                        llm_resp = self.llm_client.explain(
                            test_name=title,
                            criteria=record.criteria,
                            result=record.result,
                            rag_contexts=rag_contexts,
                            forced_status=None,
                            deterministic_reason=rule_reason,
                        )

                        if llm_resp is not None and llm_resp.status:
                            comparison_completed = True
                            source = "llm"

                            if llm_resp.status == PASS_LABEL:
                                final_status = PASS_LABEL
                            elif llm_resp.status == FAIL_LABEL:
                                final_status = FAIL_LABEL
                            else:
                                final_status = HOLD_LABEL

                            final_reason = llm_resp.reason
                            norm_criteria = llm_resp.normalized_criteria or norm_criteria
                            norm_result = llm_resp.normalized_result or norm_result

                    if final_status is None:
                        comparison_completed = True
                        final_status = HOLD_LABEL
                        final_reason = "시험기준과 시험결과가 존재하지만 자동 비교가 어려운 형식이어서 사람의 판단이 필요합니다."

        elif record.result:
            # 결과만 있어도 적합/부적합은 우선 처리
            status, text_reason = _status_from_text_result(record.result)

            if status is not None:
                comparison_completed = True
                final_status = status
                final_reason = text_reason or ""
                comparator = "text_result"
                norm_result = clean_text(record.result)
            else:
                comparison_completed = True
                final_status = HOLD_LABEL
                final_reason = "시험결과는 존재하지만 자동 판정하기 어려운 형식이어서 사람의 확인이 필요합니다."

        elif record.criteria or record.result:
            comparison_completed = True
            final_status = HOLD_LABEL
            final_reason = "시험기준 또는 시험결과가 존재하지만 자동 비교가 어려운 형식이어서 사람의 판단이 필요합니다."

        return Evaluation(
            order_idx=record.order_idx,
            record_type=record.record_type,

            section_number=record.section_number,
            section_title=record.section_title,

            test_name=title,
            content_label=record.content_label,
            content=record.content,

            criteria=record.criteria,
            result=record.result,
            method=record.method,
            test_date=record.test_date,
            test_period=record.test_period,
            remarks=record.remarks,

            final_status=final_status,
            reason=final_reason,

            page_start=record.page_start,
            page_end=record.page_end,

            normalized_criteria=norm_criteria,
            normalized_result=norm_result,
            comparator=comparator,

            source=source,
            raw_text=record.raw_text or "",
            comparison_completed=comparison_completed,
            lot_judgements=lot_judgements,
        )