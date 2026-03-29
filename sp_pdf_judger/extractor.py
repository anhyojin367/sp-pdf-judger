from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List

from .schemas import ExtractedRecord


def _record_from_dict(d: dict) -> ExtractedRecord:
    return ExtractedRecord(
        section_number=d.get("section_number"),
        section_title=d.get("section_title"),
        test_name=d.get("test_name"),
        criteria=d.get("criteria"),
        result=d.get("result"),
        method=d.get("method"),
        remarks=d.get("remarks"),
        page_start=d.get("page_start"),
        page_end=d.get("page_end"),
        source_types=d.get("source_types", []),
        raw_text=d.get("raw_text"),
    )


def extract_records(pdf_path: Path, output_dir: Path) -> List[ExtractedRecord]:
    """
    원본 json추출.py를 수정하지 않고 그대로 실행해서
    output_dir/05_records.json 을 생성한 뒤 다시 읽어서 반환한다.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    project_root = Path(__file__).resolve().parent.parent
    extractor_script = project_root / "json추출.py"

    if not extractor_script.exists():
        raise FileNotFoundError(f"추출기 파일을 찾을 수 없습니다: {extractor_script}")

    cmd = [
        sys.executable,
        str(extractor_script),
        "--pdf",
        str(pdf_path),
        "--out",
        str(output_dir),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if result.returncode != 0:
        raise RuntimeError(
            "json추출.py 실행 실패\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    records_json_path = output_dir / "05_records.json"
    if not records_json_path.exists():
        raise FileNotFoundError(f"05_records.json이 생성되지 않았습니다: {records_json_path}")

    with open(records_json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    return [_record_from_dict(x) for x in loaded]