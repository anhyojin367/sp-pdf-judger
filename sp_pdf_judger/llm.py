from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, Field

from .config import DEFAULT_GEMINI_MODEL, GEMINI_API_KEY, FAIL_LABEL, PASS_LABEL
from .utils import clean_text

try:
    from google import genai
except Exception:
    genai = None


class JudgeResponse(BaseModel):
    status: str = Field(description="적합 또는 부적합")
    reason: str = Field(description="검수합격 또는 검수불합격이라는 표현을 포함한 한글 1문장")
    normalized_criteria: str | None = None
    normalized_result: str | None = None


class GeminiJudgeClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or DEFAULT_GEMINI_MODEL
        self.enabled = bool(self.api_key and genai is not None)
        self.client = None
        if self.enabled:
            self.client = genai.Client(api_key=self.api_key)

    def explain(
        self,
        *,
        test_name: str,
        criteria: str | None,
        result: str | None,
        rag_contexts: list[str],
        forced_status: str | None = None,
        deterministic_reason: str | None = None,
    ) -> JudgeResponse | None:
        if not self.enabled or self.client is None:
            return None

        rag_text = "\n".join(f"- {clean_text(x)}" for x in rag_contexts if clean_text(x)) or "- 없음"

        if forced_status:
            task = (
                f"이미 최종 판정은 '{forced_status}'로 확정되었다. "
                f"status는 반드시 '{forced_status}'를 유지하고, 그에 맞는 이유만 작성하라."
            )
        else:
            task = f"기준과 결과를 비교하여 반드시 '{PASS_LABEL}' 또는 '{FAIL_LABEL}' 중 하나를 판단하라."

        prompt = f"""
당신은 백신 시험성적서 판정 보조 모델이다.
{task}

판정 원칙:
- 숫자와 실제 단위를 우선 비교한다.
- 숫자 뒤에 붙은 설명어(예: 백색도성상, 용출률확인, 삼투압, 성상, 확인, 시험명 일부)는 비교 단위가 아니라 부가 설명일 수 있다.
- 따라서 "100.0%용출률확인"은 "100.0%"와 같은 값으로 볼 수 있다.
- "280mOsm/kg삼투압"은 "280 mOsm/kg"와 같은 값으로 볼 수 있다.
- 실제 단위가 다를 때만 단위 불일치라고 판단한다.
- 비교 가능하면 단위 불일치라고 쓰지 말고 숫자 비교 결과를 써라.
- 범위 기준이면 시험결과가 범위 안에 포함되는지 판단한다.
- 이상/이하/미만/초과 표현을 정확히 해석한다.
- 시험방법, 시험기간, 시험일자 같은 정보는 이유에 넣지 않는다.

출력 조건:
- 응답은 JSON만 출력
- status는 적합 또는 부적합
- reason은 반드시 한 문장
- reason에는 반드시 "검수합격" 또는 "검수불합격"이라는 표현을 쓴다
- "부적합이 아닌 검수불합격" 같은 표현은 절대 쓰지 않는다
- 비교가 가능하면 reason은 아래 형태를 따른다
  - 시험결과가 시험기준과 같아 검수합격으로 판단했습니다.
  - 시험결과가 시험기준 범위 안에 포함되어 검수합격으로 판단했습니다.
  - 시험결과가 시험기준을 초과해 검수불합격으로 판단했습니다.
  - 시험결과와 시험기준의 단위가 일치하지 않아 검수불합격으로 판단했습니다.
- normalized_criteria, normalized_result는 비교에 사용한 정규화 표현만 적는다

시험명: {clean_text(test_name)}
시험기준: {clean_text(criteria)}
시험결과: {clean_text(result)}

결정적 판정 근거:
{clean_text(deterministic_reason)}

RAG 단위 참고:
{rag_text}
""".strip()

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": JudgeResponse,
                },
            )
            parsed = getattr(response, "parsed", None)
            if parsed:
                if isinstance(parsed, JudgeResponse):
                    return parsed
                if isinstance(parsed, dict):
                    return JudgeResponse(**parsed)

            text = clean_text(getattr(response, "text", ""))
            if text:
                return JudgeResponse(**json.loads(text))
        except Exception:
            return None

        return None