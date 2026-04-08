from __future__ import annotations

from .config import FAIL_LABEL, PASS_LABEL
from .criteria_parser import parse_criteria_text
from .llm import GeminiJudgeClient
from .rag import UcumRagStore
from .schemas import Evaluation, ExtractedRecord
from .unit_normalizer import ParsedMeasurement, parse_number_and_unit
from .utils import clean_text

PASS_REASON_WORD = "검수합격"
FAIL_REASON_WORD = "검수불합격"


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
    return text.replace("\\n", "\n")


def _parse_result_table(result: str | None) -> list[dict[str, str]]:
    text = _normalize_table_text(result)
    if not text or "|" not in text or "\n" not in text:
        return []

    row_map: dict[str, list[str]] = {}
    row_order: list[str] = []

    for raw_line in text.splitlines():
        line = clean_text(raw_line)
        if not line or "|" not in line:
            continue

        parts = [clean_text(p) for p in line.split("|")]
        if len(parts) < 2:
            continue

        label = parts[0]
        values = parts[1:]

        if label not in row_map:
            row_map[label] = []
            row_order.append(label)

        row_map[label].extend(values)

    lot_row_key = next((k for k in row_order if "로트" in k), None)
    result_row_key = next(
        (k for k in row_order if "시험결과" in k or "실험결과" in k or "측정결과" in k),
        None,
    )

    if not lot_row_key or not result_row_key:
        return []

    lot_numbers = row_map.get(lot_row_key, [])
    results = row_map.get(result_row_key, [])

    date_row_key = next(
        (k for k in row_order if "시험기간" in k or "시험일자" in k or "시험일" in k),
        None,
    )
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
                "lot_no": lot_clean,
                "test_date": date_value,
                "result": clean_text(results[idx]) if idx < len(results) else "",
            }
        )

    return out


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
                status, reason, comparator, norm_criteria, norm_result = deterministic_judge(
                    record.criteria,
                    row.get("result"),
                )

                if status is None:
                    status, reason = _status_from_text_result(row.get("result"))

                comparator = comparator or None
                norm_criteria = norm_criteria or None
                norm_result = norm_result or row.get("result") or ""

                lot_judgements.append(
                    {
                        "lot_no": row.get("lot_no", ""),
                        "test_date": row.get("test_date", ""),
                        "result": row.get("result", ""),
                        "status": status or "",
                        "reason": reason or "비교가 어려워 판정하지 못했습니다.",
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
            judged_rows = [x for x in lot_judgements if x.get("status")]
            if judged_rows:
                comparison_completed = True
                final_status = FAIL_LABEL if any(x["status"] == FAIL_LABEL for x in judged_rows) else PASS_LABEL
                final_reason = " ".join(
                    f"{x['lot_no']}는 {x['reason']}"
                    for x in judged_rows
                    if x.get("lot_no") and x.get("reason")
                )
                norm_criteria = judged_rows[0].get("normalized_criteria") or None

        elif record.criteria and record.result:
            status, rule_reason, comparator, norm_criteria, norm_result = deterministic_judge(
                record.criteria,
                record.result,
            )

            if status is None:
                status, rule_reason = _status_from_text_result(record.result)

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
                    final_status = PASS_LABEL if llm_resp.status == PASS_LABEL else FAIL_LABEL
                    final_reason = llm_resp.reason
                    norm_criteria = llm_resp.normalized_criteria or norm_criteria
                    norm_result = llm_resp.normalized_result or norm_result

        elif record.result:
            status, text_reason = _status_from_text_result(record.result)
            if status is not None:
                comparison_completed = True
                final_status = status
                final_reason = text_reason or ""

        return Evaluation(
            section_number=record.section_number,
            section_title=record.section_title,
            test_name=title,
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