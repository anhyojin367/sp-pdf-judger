from __future__ import annotations

import tempfile
from pathlib import Path

from .config import FAIL_LABEL, PASS_LABEL
from .extractor import extract_records
from .hierarchy import build_document_tree
from .judgement import JudgeEngine
from .llm import GeminiJudgeClient
from .preview import render_first_page
from .rag import UcumRagStore
from .schemas import ProcessingResult, Summary
from .utils import ensure_dir


class DocumentJudgePipeline:
    def __init__(self) -> None:
        self.rag_store = UcumRagStore()
        self.llm_client = GeminiJudgeClient()
        self.judge_engine = JudgeEngine(self.rag_store, self.llm_client)

    def run(self, pdf_path: Path) -> ProcessingResult:
        work_dir = ensure_dir(Path(tempfile.gettempdir()) / "sp_pdf_judger_preview")

        preview_path = work_dir / f"{pdf_path.stem}_page1.png"
        render_first_page(pdf_path, preview_path)

        extract_dir = ensure_dir(work_dir / f"{pdf_path.stem}_extract")

        records = extract_records(pdf_path, extract_dir)
        evaluations = [self.judge_engine.judge_record(r) for r in records]
        tree = build_document_tree(evaluations)

        summary = Summary(
            passed=sum(1 for x in evaluations if x.final_status == PASS_LABEL),
            failed=sum(1 for x in evaluations if x.final_status == FAIL_LABEL),
            total=len(evaluations),
        )

        return ProcessingResult(
            pdf_path=pdf_path,
            preview_image_path=preview_path,
            extracted_records=records,
            evaluations=evaluations,
            tree=tree,
            summary=summary,
            metadata={
                "llm_enabled": self.llm_client.enabled,
                "record_count": len(records),
                "records_json_path": str(extract_dir / "05_records.json"),
                "extract_dir": str(extract_dir),
            },
        )