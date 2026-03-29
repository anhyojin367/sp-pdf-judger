from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from typing import Any, Optional, List


@dataclass
class ExtractedRecord:
    section_number: Optional[str]
    section_title: Optional[str]
    test_name: Optional[str]
    criteria: Optional[str]
    result: Optional[str]
    method: Optional[str]
    remarks: Optional[str]
    page_start: int
    page_end: int
    source_types: List[str]
    raw_text: Optional[str]


@dataclass
class Evaluation:
    section_number: Optional[str]
    section_title: Optional[str]
    test_name: str
    criteria: Optional[str]
    result: Optional[str]
    final_status: str
    reason: str
    page_start: int
    page_end: int
    normalized_criteria: Optional[str] = None
    normalized_result: Optional[str] = None
    comparator: Optional[str] = None
    confidence: str = "normal"
    source: str = "rule"
    raw_text: str = ""


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
    children: list["TreeNode"] = field(default_factory=list)


@dataclass
class Summary:
    passed: int
    failed: int
    total: int


@dataclass
class ProcessingResult:
    pdf_path: Path
    preview_image_path: Path
    extracted_records: list[ExtractedRecord]
    evaluations: list[Evaluation]
    tree: list[TreeNode]
    summary: Summary
    metadata: dict[str, Any] = field(default_factory=dict)
