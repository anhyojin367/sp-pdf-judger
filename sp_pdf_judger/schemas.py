from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, List


@dataclass
class ExtractedRecord:
    record_type: str = "test"

    # json추출.py에서는 order_index로 나오고,
    # 기존 코드에서는 order_idx를 쓰고 있으므로 내부에서는 order_idx로 통일
    order_idx: int = 0

    section_number: Optional[str] = None
    section_title: Optional[str] = None

    test_name: Optional[str] = None
    content_label: Optional[str] = None
    content: Optional[str] = None

    criteria: Optional[str] = None
    result: Optional[str] = None
    method: Optional[str] = None
    test_date: Optional[str] = None
    test_period: Optional[str] = None
    remarks: Optional[str] = None

    page_start: int = 0
    page_end: int = 0

    source_types: List[str] = field(default_factory=list)
    raw_text: Optional[str] = None

    # 핵심 추가
    # json추출.py가 이미 만들어준 정확한 계층 경로
    section_path: list[dict[str, str]] = field(default_factory=list)

    # 필요 시 추후 사용 가능
    diagram_data: Any = None
    result_table: Any = None
    tables: list[Any] = field(default_factory=list)
    controls: list[Any] = field(default_factory=list)
    ocr_suspect: bool = False


@dataclass
class Evaluation:
    order_idx: int = 0
    record_type: str = "test"

    section_number: Optional[str] = None
    section_title: Optional[str] = None

    test_name: str = ""
    content_label: Optional[str] = None
    content: Optional[str] = None

    criteria: Optional[str] = None
    result: Optional[str] = None
    method: Optional[str] = None
    test_date: Optional[str] = None
    test_period: Optional[str] = None
    remarks: Optional[str] = None

    final_status: Optional[str] = None
    reason: Optional[str] = None

    page_start: int = 0
    page_end: int = 0

    normalized_criteria: Optional[str] = None
    normalized_result: Optional[str] = None
    comparator: Optional[str] = None

    confidence: str = "normal"
    source: str = "rule"
    raw_text: str = ""
    comparison_completed: bool = False

    # 로트별/항목별 표 판정용
    lot_judgements: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TreeNode:
    key: str
    title: str
    level: int

    section_number: Optional[str] = None
    section_title: Optional[str] = None

    node_type: str = "section"
    status: Optional[str] = None

    page_start: Optional[int] = None
    page_end: Optional[int] = None

    info_lines: list[str] = field(default_factory=list)
    evaluation: Optional[Evaluation] = None
    source_record: Optional[ExtractedRecord] = None

    children: list["TreeNode"] = field(default_factory=list)
    order_idx: int = 0


@dataclass
class Summary:
    passed: int
    failed: int
    total: int

    comparable_total: int = 0
    held: int = 0


@dataclass
class ProcessingResult:
    pdf_path: Path
    preview_image_path: Path

    extracted_records: list[ExtractedRecord]
    evaluations: list[Evaluation]
    tree: list[TreeNode]
    summary: Summary

    metadata: dict[str, Any] = field(default_factory=dict)

    # 제조요약도 관련 필드가 없어도 기존 코드가 깨지지 않게 기본값 제공
    manufacturing_summary_image_paths: list[Path] = field(default_factory=list)
    manufacturing_summary_status: Optional[str] = None
    manufacturing_summary_reason: Optional[str] = None
    manufacturing_summary_page_numbers: list[int] = field(default_factory=list)