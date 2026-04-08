from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "SP 시험결과 자동판별 시스템"

BASE_DIR = Path(__file__).resolve().parent.parent
PACKAGE_DIR = Path(__file__).resolve().parent

DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

OCR_LANG = "kor+eng"
OCR_TEXT_THRESHOLD = 80

UCUM_JSON_CANDIDATES = [
    BASE_DIR / "ucum_rag_docs.json",
    Path("/mnt/data/ucum_rag_docs.json"),
]

UCUM_JSONL_CANDIDATES = [
    BASE_DIR / "ucum_rag_image_units_ui_micro.jsonl",
    Path("/mnt/data/ucum_rag_image_units_ui_micro.jsonl"),
    BASE_DIR / "ucum_rag_image_units_enriched.jsonl",
    Path("/mnt/data/ucum_rag_image_units_enriched.jsonl"),
]

UCUM_XLSX_CANDIDATES = [
    BASE_DIR / "TableOfExampleUcumCodesForElectronicMessaging.xlsx",
    Path("/mnt/data/TableOfExampleUcumCodesForElectronicMessaging.xlsx"),
]

LEGACY_EXTRACTOR_OUTDIR_NAME = "legacy_extract"

PASS_LABEL = "적합"
FAIL_LABEL = "부적합"

STATUS_COLORS = {
    PASS_LABEL: "#21c55d",
    FAIL_LABEL: "#ef4444",
}

SECTION_NUMBER_RE = r"^(\d+(?:\.\d+)*)\.?\s+(.+)$"