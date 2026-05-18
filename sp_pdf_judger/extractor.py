from __future__ import annotations

import json
import locale
import subprocess
import sys
from pathlib import Path
from typing import List

from .schemas import ExtractedRecord


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _infer_record_type(d: dict) -> str:
    record_type = d.get("record_type")

    if record_type:
        return str(record_type)

    if d.get("criteria") or d.get("result") or d.get("test_name"):
        return "test"

    if d.get("content") or d.get("content_label"):
        return "content"

    return "content"


def _record_from_dict(d: dict, fallback_order: int) -> ExtractedRecord:
    order_idx = (
        d.get("order_idx")
        if d.get("order_idx") is not None
        else d.get("order_index")
    )

    return ExtractedRecord(
        record_type=_infer_record_type(d),
        order_idx=_safe_int(order_idx, fallback_order),

        section_number=d.get("section_number"),
        section_title=d.get("section_title"),

        test_name=d.get("test_name"),
        content_label=d.get("content_label"),
        content=d.get("content"),

        criteria=d.get("criteria"),
        result=d.get("result"),
        method=d.get("method"),
        test_date=d.get("test_date"),
        test_period=d.get("test_period"),
        remarks=d.get("remarks"),

        page_start=_safe_int(d.get("page_start"), 0),
        page_end=_safe_int(d.get("page_end") or d.get("page_start"), 0),

        source_types=d.get("source_types") or [],
        raw_text=d.get("raw_text"),

        section_path=d.get("section_path") or [],

        diagram_data=d.get("diagram_data"),
        result_table=d.get("result_table"),
        tables=d.get("tables") or [],
        controls=d.get("controls") or [],
        ocr_suspect=bool(d.get("ocr_suspect", False)),
    )


def extract_records(pdf_path: Path, output_dir: Path) -> List[ExtractedRecord]:
    """
    json추출.py를 실행해서 output_dir/05_records.json을 만든 뒤,
    JSON의 section_path/order_index/record_type/content 정보를 보존해서 반환한다.
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
        encoding=locale.getpreferredencoding(False),
        errors="replace",
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

    records = [
        _record_from_dict(row, fallback_order=idx)
        for idx, row in enumerate(loaded, start=1)
    ]

    records.sort(key=lambda r: r.order_idx)

    return records