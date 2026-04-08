from __future__ import annotations

import json
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
from .utils import clean_text, ensure_dir


def _load_section_title_map(records_json_path: Path) -> dict[str, str]:
    if not records_json_path.exists():
        return {}

    with open(records_json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    out: dict[str, str] = {}
    for row in loaded:
        section_number = clean_text(row.get("section_number"))
        section_title = clean_text(row.get("section_title"))
        if section_number and section_title and section_number not in out:
            out[section_number] = section_title

    return out


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

        test_records = [r for r in records if r.record_type == "test"]
        evaluations = [self.judge_engine.judge_record(r) for r in test_records]

        records_json_path = extract_dir / "05_records.json"
        section_title_map = _load_section_title_map(records_json_path)
        tree = build_document_tree(records, evaluations, section_title_map=section_title_map)

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
                "records_json_path": str(records_json_path),
                "extract_dir": str(extract_dir),
                "rag_doc_count": len(self.rag_store.docs),
                "rag_sources": self.rag_store.loaded_sources,
            },
        )