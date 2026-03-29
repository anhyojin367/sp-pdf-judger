# SP PDF 판정 시스템

PDF를 직접 LLM에 넣지 않고,

1. PDF 업로드
2. OCR/텍스트 추출
3. JSON 레코드 추출
4. UCUM RAG 보강
5. LLM + 규칙 기반 판정
6. Streamlit UI 렌더링

순서로 처리하는 프로젝트입니다.

## 특징

- **왼쪽 사이드바에는 PDF 업로드만 존재**
- 업로드 즉시 **PDF 첫 페이지 미리보기**
- **합격/불합격 요약 카드**
- PDF 구조를 따라가는 **중첩 토글 트리 UI**
- UI에는 **시험방법/시험기간을 숨기고**
  - 시험기준
  - 시험결과
  - 판정 이유
  만 표시
- 기존에 주신 `json추출.py`를 **1차 구조 추출기**로 사용
- 텍스트가 거의 없는 PDF는 **OCR fallback** 수행
- `ucum_rag_docs.json`을 내부 RAG 문서로 사용

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

## 환경 변수

- `GEMINI_API_KEY`
- `GEMINI_MODEL`

LLM 키가 없으면 규칙 기반 이유만 표시됩니다.

## OCR 메모

기본은 텍스트 추출 우선입니다.
페이지 텍스트가 너무 적으면 OCR fallback이 동작합니다.

`pytesseract`를 쓰므로 시스템에 Tesseract가 필요합니다.

- macOS: `brew install tesseract tesseract-lang`
- Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-kor`
