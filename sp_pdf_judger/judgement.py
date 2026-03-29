from __future__ import annotations

from typing import Optional

from .config import FAIL_LABEL, PASS_LABEL
from .criteria_parser import parse_criteria_text
from .llm import GeminiJudgeClient
from .rag import UcumRagStore
from .schemas import Evaluation, ExtractedRecord
from .unit_normalizer import ParsedMeasurement, parse_number_and_unit


PASS_REASON_WORD = "검수합격"
FAIL_REASON_WORD = "검수불합격"


def _same_or_convertible(a: ParsedMeasurement, b: ParsedMeasurement) -> bool:
    return a.unit_canonical == b.unit_canonical


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


def deterministic_judge(
    criteria: str | None,
    result: str | None,
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
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
            return (
                FAIL_LABEL,
                _unit_mismatch_reason(),
                "between",
                f"{lo.pretty} ~ {hi.pretty}",
                parsed_result.pretty,
            )

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
        status, rule_reason, comparator, norm_criteria, norm_result = deterministic_judge(
            record.criteria,
            record.result,
        )

        source = "rule"
        final_reason = rule_reason
        final_norm_criteria = norm_criteria
        final_norm_result = norm_result

        # 규칙 기반 비교가 안 되는 경우에만 LLM 사용
        if status is None and self.llm_client is not None:
            query = " ".join(filter(None, [record.test_name, record.criteria, record.result]))
            rag_docs = self.rag_store.search(query, top_k=5)
            rag_contexts = [d.text for d in rag_docs]

            llm_resp = self.llm_client.explain(
                test_name=record.test_name or "이름없음",
                criteria=record.criteria,
                result=record.result,
                rag_contexts=rag_contexts,
                forced_status=None,
                deterministic_reason=None,
            )
            if llm_resp is not None:
                source = "llm"
                status = PASS_LABEL if llm_resp.status == PASS_LABEL else FAIL_LABEL
                final_reason = llm_resp.reason
                final_norm_criteria = llm_resp.normalized_criteria or final_norm_criteria
                final_norm_result = llm_resp.normalized_result or final_norm_result

        if status is None:
            status = FAIL_LABEL
            final_reason = f"시험기준과 시험결과를 자동으로 비교하기 어려운 형식이어서 {FAIL_REASON_WORD}으로 판단했습니다."

        return Evaluation(
            section_number=record.section_number,
            section_title=record.section_title,
            test_name=record.test_name or "이름없음",
            criteria=record.criteria,
            result=record.result,
            final_status=status,
            reason=final_reason,
            page_start=record.page_start,
            page_end=record.page_end,
            normalized_criteria=final_norm_criteria,
            normalized_result=final_norm_result,
            comparator=comparator,
            source=source,
            raw_text=record.raw_text or "",
        )