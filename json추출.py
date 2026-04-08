import re
import json
import argparse
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pdfplumber


@dataclass
class Config:
    save_intermediate: bool = True
    label_aliases: Dict[str, str] = field(default_factory=dict)
    field_map: Dict[str, str] = field(default_factory=dict)
    test_name_labels: List[str] = field(default_factory=list)
    criteria_labels: List[str] = field(default_factory=list)
    result_labels: List[str] = field(default_factory=list)
    method_labels: List[str] = field(default_factory=list)
    date_labels: List[str] = field(default_factory=list)
    period_labels: List[str] = field(default_factory=list)
    remarks_labels: List[str] = field(default_factory=list)
    heading_patterns: List[re.Pattern] = field(default_factory=list)
    heading_forbidden_patterns: List[re.Pattern] = field(default_factory=list)
    noise_patterns: List[re.Pattern] = field(default_factory=list)
    test_name_positive_patterns: List[re.Pattern] = field(default_factory=list)
    test_name_negative_patterns: List[re.Pattern] = field(default_factory=list)


def build_config() -> Config:
    label_aliases = {
        "시험 기준": "시험기준",
        "시험 결과": "시험결과",
        "시험 방법": "시험방법",
        "시험 항목": "시험항목",
        "시험 명": "시험명",
        "항 목": "항목",
        "항목 명": "항목명",
        "기 준": "기준",
        "결 과": "결과",
        "규 격": "규격",
        "비 고": "비고",
        "참 고": "참고",
        "특이 사항": "특이사항",
        "측정 결과": "측정결과",
        "실험 결과": "실험결과",
        "분석 방법": "분석방법",
        "시험 법": "시험법",
        "분석 법": "분석법",
        "품질 기준": "품질기준",
        "허용 기준": "허용기준",
        "시험 일자": "시험일자",
        "시험 날짜": "시험일자",
        "시험 기간": "시험기간",
        "시험 일": "시험일",
        "로트 번호": "로트번호",
    }

    field_map = {
        "시험명": "test_name",
        "시험항목": "test_name",
        "항목명": "test_name",
        "항목": "test_name",
        "시험": "test_name",
        "시험기준": "criteria",
        "기준": "criteria",
        "규격": "criteria",
        "품질기준": "criteria",
        "허용기준": "criteria",
        "시험결과": "result",
        "결과": "result",
        "측정결과": "result",
        "실험결과": "result",
        "시험방법": "method",
        "시험법": "method",
        "분석방법": "method",
        "분석법": "method",
        "방법": "method",
        "시험일자": "test_date",
        "시험기간": "test_period",
        "시험일": "test_date",
        "비고": "remarks",
        "특이사항": "remarks",
        "참고": "remarks",
    }

    heading_patterns = [
        re.compile(r"^(\d+(?:\.\d+)+)\s*([가-힣A-Za-z(].+)$"),
        re.compile(r"^(\d+(?:\.\d+)*)\s+[가-힣A-Za-z(].+$"),
        re.compile(r"^(\d+(?:\.\d+)*)\s*[.)]\s+(.+)$"),
    ]

    heading_forbidden_patterns = [
        re.compile(r"^(이하|이상|적합|부적합|페이지)$"),
        re.compile(r"^%"),
        re.compile(r"^[\d.\-~/\s%]+$"),
        re.compile(r"^\d+(?:\.\d+)?\s*(mL|ml|mg|g|kg|L|IU|CFU|PFU|%|ppm|ppb|μL|uL|℃|°C)\b"),
        re.compile(r"^\d+(?:\.\d+)?\s*(바이알|상자|병|개|정|캡슐|앰플)\b"),
        re.compile(r"^\d+(?:\.\d+)?\s*~\s*\d+(?:\.\d+)?"),
        re.compile(r"^\d+(?:\.\d+)?\s*pH", re.I),
        re.compile(r"^.*(바이알|상자|접종량|pH범위).*$"),
        re.compile(r"^.*\b(mL|ml|mg|kg|g|IU|CFU|PFU|%)\b.*$"),
    ]

    noise_patterns = [
        re.compile(r"^\s*한미약품\s*주식회사\s*$"),
        re.compile(r"^\s*Summary Protocol.*$", re.I),
        re.compile(r"^\s*Summary\s*Protocol\s*for\s*Production\s*and\s*Quality\s*control\s*:?\s*$", re.I),
        re.compile(r"^\s*SummaryProtocolforProductionandQualitycontrol:?\s*$", re.I),
        re.compile(r"^\s*Japanese encephalitis Vaccine.*$", re.I),
        re.compile(r"^\s*제조번호\s*[:：].*$"),
        re.compile(r"^\s*-\s*\d+\s*-\s*$"),
        re.compile(r"^\s*\d+\s*/\s*\d+\s*페이지\s*$"),
        re.compile(r"^\s*페이지\s*\d+\s*/\s*\d+\s*$"),
        re.compile(r"^\s*인덴테이션 없음\s*$"),
    ]

    test_name_positive_patterns = [
        re.compile(r".+시험$"),
        re.compile(r".+부정시험$"),
        re.compile(r".+확인시험$"),
        re.compile(r".+역가시험$"),
        re.compile(r".+측정시험$"),
        re.compile(r".+분석시험$"),
        re.compile(r".+함량시험$"),
        re.compile(r".+불활화시험$"),
        re.compile(r".+분포시험$"),
        re.compile(r".+균일성시험$"),
        re.compile(r".+이물시험$"),
        re.compile(r".+미립자시험$"),
        re.compile(r".+검사$"),
        re.compile(r".+분석$"),
        re.compile(r".+측정$"),
        re.compile(r".+안정성시험$"),
    ]

    test_name_negative_patterns = [
        re.compile(r"^시험$"),
        re.compile(r"^시험기준"),
        re.compile(r"^시험결과"),
        re.compile(r"^시험방법"),
        re.compile(r"^시험기간"),
        re.compile(r"^시험일"),
        re.compile(r"^시험일자"),
        re.compile(r"^시험자"),
        re.compile(r"^시험책임자"),
        re.compile(r"^기준$"),
        re.compile(r"^결과$"),
        re.compile(r"^방법$"),
        re.compile(r"^비고$"),
        re.compile(r"^참고$"),
        re.compile(r"^정보$"),
        re.compile(r"^제품명"),
        re.compile(r"^품목명"),
        re.compile(r"^생기수재명"),
        re.compile(r"^제조번호"),
        re.compile(r"^제조일"),
        re.compile(r"^유효기간"),
        re.compile(r"^확인/서명일"),
        re.compile(r"^\d+(?:\.\d+)*\s*시험$"),
        re.compile(r".*페이지.*"),
        re.compile(r".*한미약품.*"),
        re.compile(r".*Summary Protocol.*", re.I),
        re.compile(r".*Japanese encephalitis Vaccine.*", re.I),
        re.compile(r".*(바이알|상자|mL|ml|mg|kg| pH범위|접종량).*")
    ]

    return Config(
        save_intermediate=True,
        label_aliases=label_aliases,
        field_map=field_map,
        test_name_labels=["시험명", "시험항목", "항목명", "항목", "시험"],
        criteria_labels=["시험기준", "기준", "규격", "품질기준", "허용기준"],
        result_labels=["시험결과", "결과", "측정결과", "실험결과"],
        method_labels=["시험방법", "시험법", "분석방법", "분석법", "방법"],
        date_labels=["시험일자", "시험일"],
        period_labels=["시험기간"],
        remarks_labels=["비고", "특이사항", "참고"],
        heading_patterns=heading_patterns,
        heading_forbidden_patterns=heading_forbidden_patterns,
        noise_patterns=noise_patterns,
        test_name_positive_patterns=test_name_positive_patterns,
        test_name_negative_patterns=test_name_negative_patterns,
    )


CFG = build_config()


@dataclass
class OrderedElement:
    kind: str
    text: str
    top: float
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RawPage:
    page_num: int
    text: str
    tables: List[List[List[str]]]
    ordered_elements: List[OrderedElement] = field(default_factory=list)


@dataclass
class Item:
    idx: int
    type: str
    page: int
    text: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Section:
    number: str
    title: str
    depth: int
    page: int
    start_idx: int
    end_idx: int


@dataclass
class Block:
    section_number: Optional[str]
    section_title: Optional[str]
    page_start: int
    page_end: int
    items: List[Item]


@dataclass
class Record:
    record_type: str
    section_number: Optional[str]
    section_title: Optional[str]
    test_name: Optional[str]
    content_label: Optional[str]
    content: Optional[str]
    criteria: Optional[str]
    result: Optional[str]
    method: Optional[str]
    test_date: Optional[str]
    test_period: Optional[str]
    remarks: Optional[str]
    page_start: int
    page_end: int
    source_types: List[str]
    raw_text: str


def clean_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text).replace("\xa0", " ").replace("\u3000", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def normalize_number_spacing(text: str) -> str:
    return re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", text)


def normalize_label(text: str) -> str:
    t = clean_text(text)
    t = normalize_number_spacing(t)
    t = re.sub(r"\s*[:：]\s*$", "", t)
    return CFG.label_aliases.get(t, t)


def canonical_field(label: str) -> Optional[str]:
    return CFG.field_map.get(normalize_label(label))


def infer_depth(number: str) -> int:
    return len(number.split(".")) if "." in number else 1


def is_noise(text: str) -> bool:
    t = clean_text(text)
    if not t:
        return True
    return any(p.match(t) for p in CFG.noise_patterns)


def is_page_artifact_line(text: str) -> bool:
    t = clean_text(text)
    if not t:
        return True
    return bool(
        t in {":", "：", "-", "--"} or
        re.fullmatch(r"-?\s*\d+\s*-?", t) or
        re.fullmatch(r"\d+\s*/\s*\d+\s*페이지", t) or
        re.fullmatch(r"\d+\s*/\s*\d+", t) or
        re.fullmatch(r"\d+\.", t) or
        re.fullmatch(r"페이지", t) or
        re.fullmatch(r":\s*페이지", t)
    )


def is_leader_only_line(text: str) -> bool:
    t = clean_text(text)
    if not t:
        return True
    return bool(re.fullmatch(r"[_\-\.·\s]{3,}", t) or re.fullmatch(r"(?:[_\-\.·]{2,}\s*)+", t))


def strip_line_leaders(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    t = clean_text(text)
    if not t:
        return None
    lines = []
    for line in t.splitlines():
        s = clean_text(line)
        if not s or is_leader_only_line(s):
            continue
        s = re.sub(r"(?<=\S)\s*[_]{3,}\s*$", "", s)
        s = re.sub(r"^\s*[_]{3,}\s*(?=\S)", "", s)
        s = re.sub(r"(?<=\S)\s*[-–—\.·]{5,}\s*$", "", s)
        s = re.sub(r"^\s*[-–—\.·]{5,}\s*(?=\S)", "", s)
        s = re.sub(r"(?<=\S)\s*[_\-–—\.·]{5,}\s*$", "", s)
        s = re.sub(r"^\s*[_\-–—\.·]{5,}\s*(?=\S)", "", s)
        s = clean_text(s)
        if s:
            lines.append(s)
    out = "\n".join(lines).strip()
    return out or None


def normalize_field_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    t = strip_line_leaders(value)
    if not t:
        return None
    lines = []
    for line in t.splitlines():
        s = clean_text(line)
        if not s or is_noise(s) or is_page_artifact_line(s) or is_leader_only_line(s):
            continue
        lines.append(s)
    out = "\n".join(lines).strip()
    return out or None


def clean_result_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    t = strip_line_leaders(text)
    if not t:
        return None
    lines = []
    for line in t.splitlines():
        s = clean_text(line)
        if not s or is_leader_only_line(s):
            continue
        if re.fullmatch(r"\d+\s*/\s*\d+\s*페이지", s) or re.fullmatch(r":\s*페이지", s):
            continue
        if s in {"원액", "최종원액", "시험", "정보", "재료", "완제의약품"}:
            continue
        lines.append(s)
    out = "\n".join(lines).strip()
    return out or None


def clean_content_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    t = strip_line_leaders(text)
    if not t:
        return None
    lines = []
    for line in t.splitlines():
        s = clean_text(line)
        if not s or is_leader_only_line(s):
            continue
        if re.fullmatch(r"\d+\s*/\s*\d+\s*페이지", s):
            continue
        lines.append(s)
    out = "\n".join(lines).strip()
    return out or None


def is_heading_forbidden_title(title: str) -> bool:
    t = clean_text(title)
    if not t or is_noise(t):
        return True
    return any(p.match(t) for p in CFG.heading_forbidden_patterns)


def detect_heading(line: str) -> Optional[Tuple[str, str, int]]:
    t = normalize_number_spacing(clean_text(line))
    if not t or is_noise(t):
        return None
    if re.match(r"^\d+\s*(μg|ug|mg|g|kg|mL|ml|L|IU|CFU|PFU|%|ppm|ppb|℃|°C)\b", t):
        return None
    compact = re.sub(r"\s+", " ", t)
    for pat in CFG.heading_patterns:
        m = pat.match(compact)
        if m:
            number = clean_text(m.group(1))
            title = clean_text(m.group(2))
            if not title or title.startswith('.') or is_heading_forbidden_title(title):
                continue
            return number, title, infer_depth(number)
    return None


def next_label_fields(future_items) -> List[str]:
    labels = []
    for it in future_items[:4]:
        if it.type == "kv":
            f = canonical_field(it.meta.get("key", ""))
            if f:
                labels.append(f)
        elif it.type == "line":
            f = canonical_field(clean_text(it.text or ""))
            if f:
                labels.append(f)
    return labels


def is_labelled_block_starter(text: str, future_items=None) -> bool:
    t = normalize_test_name(text)
    if not t or canonical_field(t) or detect_heading(t) or is_noise(t):
        return False
    if is_probable_test_name(t):
        return False
    future_labels = set(next_label_fields(future_items or []))
    return bool({"method", "criteria", "result"}.intersection(future_labels)) and len(t) <= 50


def should_start_test(line: str, section_title: Optional[str], future_items=None) -> bool:
    future_labels = set(next_label_fields(future_items or []))
    in_test_section = bool(section_title and ("시험" in section_title or "품질시험결과" in section_title))
    if is_labelled_block_starter(line, future_items):
        return True
    if is_probable_test_name(line):
        if in_test_section:
            return True
        return bool({"method", "criteria", "result", "test_date", "test_period"}.intersection(future_labels))
    if is_contextual_test_name(line, future_items):
        return True
    return False


def normalize_test_name(text: str) -> str:
    t = clean_text(text)
    if not t:
        return ""
    t = re.sub(r"^시험\s+(?=.+(시험|검사)(\([^)]*\))?$)", "", t)
    t = re.sub(r"^시험(?=.+(시험|검사)(\([^)]*\))?$)", "", t)
    t = strip_line_leaders(t) or t
    return t.strip()


def is_probable_test_name(text: str) -> bool:
    t = normalize_test_name(text)
    if not t or len(t) > 150 or ":" in t or "：" in t or "|" in t or is_noise(t) or is_leader_only_line(t):
        return False
    if any(p.match(t) for p in CFG.test_name_negative_patterns):
        return False
    if any(p.match(t) for p in CFG.heading_forbidden_patterns):
        return False
    if re.fullmatch(r"[\d.\-~/\s%a-zA-Zμ℃°_]+", t):
        return False
    if any(p.match(t) for p in CFG.test_name_positive_patterns):
        return True
    return bool(re.match(r".+(시험|검사)\([^)]*\)$", t))


def is_contextual_test_name(text: str, future_items=None) -> bool:
    t = normalize_test_name(text)
    if not t:
        return False
    if is_probable_test_name(t):
        return True
    if is_noise(t) or is_page_artifact_line(t) or is_leader_only_line(t) or canonical_field(t) or detect_heading(t) or ":" in t or "：" in t or "|" in t:
        return False
    allowed_suffix = ("크로마토그래피", "분광광도법", "분광광도", "HPLC", "ELISA", "PCR", "RT-PCR")
    suffix_ok = any(t.endswith(x) for x in allowed_suffix)
    if not future_items:
        return suffix_ok
    lookahead = []
    for it in future_items[:4]:
        if it.type == "kv":
            lookahead.append(normalize_label(it.meta.get("key", "")))
        elif it.type == "line":
            line = clean_text(it.text or "")
            if canonical_field(line):
                lookahead.append(normalize_label(line))
    return suffix_ok and any(k in {"시험기준", "기준", "시험결과", "결과"} for k in lookahead)


def repair_split_test_name(curr: str, nxt: Optional[str]) -> Tuple[str, bool]:
    curr = clean_text(curr)
    nxt = clean_text(nxt or "")
    if not curr or not nxt:
        return curr, False
    m = re.search(r"\(([^)]*?)\s*\)\s*$", curr)
    if m and re.fullmatch(r"\d+\)?", nxt):
        inside = m.group(1)
        if inside.endswith(("LD", "ED", "TCID")):
            num = re.sub(r"[^\d]", "", nxt)
            repaired = re.sub(r"\(([^)]*?)\s*\)\s*$", f"({inside}{num})", curr)
            return repaired, True
    if re.search(r"\b(LD|ED|TCID)\s*$", curr) and re.fullmatch(r"\d+", nxt):
        return curr + nxt, True
    general_suffixes = {"시험", "검사", "분석", "측정", "확인시험", "부정시험", "함량시험", "측정시험", "분석시험", "정량시험", "불활화시험", "안정성시험", "검출시험", "크로마토그래피시험", "분포시험", "균일성시험", "이물시험", "미립자시험"}
    merged = curr + nxt
    if nxt in general_suffixes and is_probable_test_name(merged):
        return merged, True
    return curr, False


def render_table(table: List[List[str]]) -> str:
    rows = []
    for row in table:
        cells = [clean_text(c) for c in row if clean_text(c)]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows).strip()


def join_nonempty(parts: List[str], sep=" | ") -> str:
    return sep.join([clean_text(p) for p in parts if clean_text(p)])


class PDFReader:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def _word_in_table(self, word: Dict[str, Any], tables_with_bbox: List[Tuple[Tuple[float, float, float, float], List[List[str]]]]) -> bool:
        x0 = float(word.get("x0", 0.0))
        x1 = float(word.get("x1", 0.0))
        top = float(word.get("top", 0.0))
        bottom = float(word.get("bottom", top))
        cx = (x0 + x1) / 2.0
        cy = (top + bottom) / 2.0
        for bbox, _table in tables_with_bbox:
            bx0, btop, bx1, bbottom = bbox
            if bx0 <= cx <= bx1 and btop <= cy <= bbottom:
                return True
        return False

    def _group_words_to_lines(self, words: List[Dict[str, Any]]) -> List[Tuple[float, str]]:
        if not words:
            return []
        words = sorted(words, key=lambda w: (round(float(w.get("top", 0.0)), 1), float(w.get("x0", 0.0))))
        lines: List[List[Dict[str, Any]]] = []
        current: List[Dict[str, Any]] = []
        current_top: Optional[float] = None
        for w in words:
            top = float(w.get("top", 0.0))
            if current_top is None or abs(top - current_top) <= 3.0:
                current.append(w)
                if current_top is None:
                    current_top = top
                else:
                    current_top = min(current_top, top)
            else:
                lines.append(current)
                current = [w]
                current_top = top
        if current:
            lines.append(current)

        out: List[Tuple[float, str]] = []
        for line_words in lines:
            line_words = sorted(line_words, key=lambda w: float(w.get("x0", 0.0)))
            parts: List[str] = []
            prev_x1: Optional[float] = None
            for w in line_words:
                txt = clean_text(w.get("text", ""))
                if not txt:
                    continue
                x0 = float(w.get("x0", 0.0))
                if parts and prev_x1 is not None and x0 - prev_x1 > 6.0:
                    parts.append(" ")
                parts.append(txt)
                prev_x1 = float(w.get("x1", x0))
            line_text = clean_text("".join(parts))
            if line_text:
                out.append((min(float(w.get("top", 0.0)) for w in line_words), line_text))
        return out

    def read(self) -> List[RawPage]:
        pages = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                tables_with_bbox: List[Tuple[Tuple[float, float, float, float], List[List[str]]]] = []
                ordered_elements: List[OrderedElement] = []

                for tbl in page.find_tables():
                    raw = tbl.extract() or []
                    norm_table: List[List[str]] = []
                    for row in raw:
                        if row is None:
                            continue
                        norm_row = [clean_text(str(c)) if c is not None else "" for c in row]
                        if any(norm_row):
                            norm_table.append(norm_row)
                    if not norm_table:
                        continue
                    bbox = tuple(float(x) for x in tbl.bbox)
                    tables_with_bbox.append((bbox, norm_table))
                    table_lines = []
                    for row in norm_table:
                        row_txt = join_nonempty(row, sep=" | ")
                        if row_txt:
                            table_lines.append(row_txt)
                    table_text = "\n".join(table_lines).strip()
                    if table_text:
                        ordered_elements.append(OrderedElement("table", table_text, bbox[1], {"bbox": bbox, "table": norm_table}))

                words = page.extract_words(x_tolerance=2, y_tolerance=3, keep_blank_chars=False, use_text_flow=False) or []
                text_words = [w for w in words if not self._word_in_table(w, tables_with_bbox)]
                line_pairs = self._group_words_to_lines(text_words)
                for top, line in line_pairs:
                    ordered_elements.append(OrderedElement("text", line, top, {}))

                ordered_elements.sort(key=lambda e: (e.top, 0 if e.kind == "text" else 1))
                page_text = "\n".join(e.text for e in ordered_elements if e.kind == "text")
                page_tables = [tbl for _bbox, tbl in tables_with_bbox]
                pages.append(RawPage(i, clean_text(page_text), page_tables, ordered_elements))
        return pages


class Normalizer:
    def __init__(self):
        self._idx = 0

    def run(self, pages: List[RawPage]) -> List[Item]:
        items = []
        for page in pages:
            items.extend(self._normalize_page(page))
        return items

    def _normalize_page(self, page: RawPage):
        out = []
        if page.ordered_elements:
            pending_text_lines: List[str] = []
            def flush_text_lines():
                nonlocal out, pending_text_lines
                if not pending_text_lines:
                    return
                joined = "\n".join(pending_text_lines)
                out.extend(self._normalize_text(joined, page.page_num))
                pending_text_lines = []
            for elem in page.ordered_elements:
                if elem.kind == "text":
                    pending_text_lines.append(elem.text)
                elif elem.kind == "table":
                    flush_text_lines()
                    table_text = clean_text(elem.text)
                    if table_text:
                        out.append(self._make_item("table_block", page.page_num, table_text, {"source": "table", **elem.meta}))
            flush_text_lines()
            return out
        out.extend(self._normalize_text(page.text, page.page_num))
        out.extend(self._normalize_tables(page.tables, page.page_num))
        return out

    def _next_idx(self) -> int:
        x = self._idx
        self._idx += 1
        return x

    def _make_item(self, item_type, page, text=None, meta=None):
        return Item(self._next_idx(), item_type, page, text, meta or {})

    def _normalize_text(self, text, page_num):
        out = []
        if not text:
            return out
        lines = [normalize_number_spacing(clean_text(x)) for x in text.split("\n")]
        lines = [x for x in lines if x and not is_noise(x)]
        repaired = []
        skip = False
        for i, line in enumerate(lines):
            if skip:
                skip = False
                continue
            nxt = lines[i + 1] if i + 1 < len(lines) else None
            merged, used = repair_split_test_name(line, nxt)
            repaired.append(merged)
            if used:
                skip = True
        for line in repaired:
            line = clean_text(line)
            if not line:
                continue
            heading = detect_heading(line)
            if heading:
                n, t, d = heading
                out.append(self._make_item("heading", page_num, line, {"number": n, "title": t, "depth": d}))
                continue
            kv = self._split_kv(line)
            if kv:
                key, value = kv
                out.append(self._make_item("kv", page_num, meta={"key": key, "value": value, "source": "text"}))
            elif line not in {":", "："}:
                out.append(self._make_item("line", page_num, line, {"source": "text"}))
        return out

    def _split_kv(self, line):
        m = re.match(r"^\s*([^:：]{1,40})\s*[:：]\s*(.+?)\s*$", line)
        if m:
            key = normalize_label(m.group(1))
            value = clean_text(m.group(2))
            if key == "시험" and not is_probable_test_name(value):
                return None
            if key and value:
                return key, value
        labels = CFG.test_name_labels + CFG.criteria_labels + CFG.result_labels + CFG.method_labels + CFG.date_labels + CFG.period_labels + CFG.remarks_labels
        normalized_line = clean_text(line)
        for label in sorted(set(labels), key=len, reverse=True):
            if normalized_line.startswith(label + " "):
                value = clean_text(normalized_line[len(label):])
                if label == "시험" and not is_probable_test_name(value):
                    continue
                if value:
                    return normalize_label(label), value
        return None

    def _normalize_tables(self, tables, page_num):
        out = []
        for table_idx, table in enumerate(tables):
            table_text = render_table(table)
            if table_text:
                out.append(self._make_item("table_block", page_num, table_text, {"table_idx": table_idx}))
        return out


class SectionBuilder:
    def run(self, items):
        heading_positions = []
        for i, item in enumerate(items):
            if item.type != "heading":
                continue
            title = clean_text(item.meta.get("title", ""))
            if is_heading_forbidden_title(title):
                continue
            heading_positions.append(i)
        if not heading_positions:
            return []
        sections = []
        for idx, pos in enumerate(heading_positions):
            item = items[pos]
            end_idx = heading_positions[idx + 1] - 1 if idx < len(heading_positions) - 1 else len(items) - 1
            sections.append(Section(item.meta["number"], item.meta["title"], item.meta["depth"], item.page, pos, end_idx))
        return sections


class BlockBuilder:
    def run(self, items, sections):
        if not items:
            return []
        if not sections:
            return [Block(None, None, items[0].page, items[-1].page, items)]
        blocks = []
        if sections[0].start_idx > 0:
            prefix_items = items[:sections[0].start_idx]
            if prefix_items:
                blocks.append(Block(None, None, prefix_items[0].page, prefix_items[-1].page, prefix_items))
        for sec in sections:
            block_items = items[sec.start_idx: sec.end_idx + 1]
            blocks.append(Block(sec.number, sec.title, block_items[0].page, block_items[-1].page, block_items))
        return blocks


class GenericAccumulator:
    def __init__(self, section_number, section_title, page):
        self.section_number = section_number
        self.section_title = section_title
        self.page_start = page
        self.page_end = page
        self.lines: List[str] = []
        self.source_types = set()

    def add(self, text: str, item_type: str, page: int):
        t = clean_text(text)
        if not t or is_noise(t):
            return
        self.page_end = page
        self.lines.append(t)
        self.source_types.add(item_type)

    def has_payload(self) -> bool:
        return bool(clean_content_text("\n".join(self.lines)))

    def to_record(self) -> Record:
        raw = "\n".join(self.lines).strip()
        return Record(
            record_type="content",
            section_number=self.section_number,
            section_title=self.section_title,
            test_name=None,
            content_label=self.section_title,
            content=clean_content_text(raw),
            criteria=None,
            result=None,
            method=None,
            test_date=None,
            test_period=None,
            remarks=None,
            page_start=self.page_start,
            page_end=self.page_end,
            source_types=sorted(self.source_types),
            raw_text=raw,
        )


class TestAccumulator:
    def __init__(self, section_number, section_title, page):
        self.section_number = section_number
        self.section_title = section_title
        self.page_start = page
        self.page_end = page
        self.test_name: Optional[str] = None
        self.criteria: List[str] = []
        self.result: List[str] = []
        self.method: List[str] = []
        self.test_date: List[str] = []
        self.test_period: List[str] = []
        self.remarks: List[str] = []
        self.raw: List[str] = []
        self.source_types = set()
        self.result_tables: List[str] = []

    def set_page(self, page):
        self.page_end = page

    def add_raw(self, text):
        t = clean_text(text)
        if t and not is_noise(t) and t not in {":", "："}:
            self.raw.append(t)

    def add_table(self, text: str, page: int):
        t = clean_content_text(text)
        if not t:
            return
        self.page_end = page
        self.result_tables.append(t)
        self.raw.append(t)
        self.source_types.add("table_block")

    def add_field(self, field_name, value):
        v = clean_text(value)
        if not v or is_noise(v) or v in {":", "："}:
            return
        if field_name == "result":
            v = clean_result_text(v) or v
        else:
            v = normalize_field_value(v) or v
        if field_name == "test_name":
            normalized = normalize_test_name(v)
            if normalized and not self.test_name:
                self.test_name = normalized
        elif field_name == "criteria" and v not in self.criteria:
            self.criteria.append(v)
        elif field_name == "result" and v not in self.result:
            self.result.append(v)
        elif field_name == "method" and v not in self.method:
            self.method.append(v)
        elif field_name == "test_date" and v not in self.test_date:
            self.test_date.append(v)
        elif field_name == "test_period" and v not in self.test_period:
            self.test_period.append(v)
        elif field_name == "remarks" and v not in self.remarks:
            self.remarks.append(v)

    def has_payload(self):
        return bool(self.test_name or self.criteria or self.result or self.method or self.test_date or self.test_period or self.remarks or self.result_tables)

    def to_record(self):
        result_parts = []
        if self.result:
            result_parts.extend(self.result)
        if self.result_tables:
            result_parts.extend(self.result_tables)
        return Record(
            record_type="test",
            section_number=self.section_number,
            section_title=self.section_title,
            test_name=self.test_name,
            content_label=None,
            content=None,
            criteria="\n".join(self.criteria) if self.criteria else None,
            result="\n".join(result_parts) if result_parts else None,
            method="\n".join(self.method) if self.method else None,
            test_date="\n".join(self.test_date) if self.test_date else None,
            test_period="\n".join(self.test_period) if self.test_period else None,
            remarks="\n".join(self.remarks) if self.remarks else None,
            page_start=self.page_start,
            page_end=self.page_end,
            source_types=sorted(self.source_types),
            raw_text="\n".join(self.raw).strip(),
        )


class RecordExtractor:
    def run(self, blocks):
        records = []
        for block in blocks:
            records.extend(self._extract_block(block))
        return self._postprocess(records)

    def _flush_generic(self, generic: GenericAccumulator, out: List[Record]):
        if generic and generic.has_payload():
            out.append(generic.to_record())

    def _flush_test(self, current: Optional[TestAccumulator], out: List[Record]):
        if current and current.has_payload():
            out.append(current.to_record())

    def _make_heading_record(self, block: Block) -> Optional[Record]:
        if not block.section_number and not block.section_title:
            return None
        title = join_nonempty([block.section_number, block.section_title], sep=" ")
        return Record(
            record_type="heading",
            section_number=block.section_number,
            section_title=block.section_title,
            test_name=None,
            content_label=block.section_title,
            content=title,
            criteria=None,
            result=None,
            method=None,
            test_date=None,
            test_period=None,
            remarks=None,
            page_start=block.page_start,
            page_end=block.page_start,
            source_types=["heading"],
            raw_text=title,
        )

    def _looks_like_labelled_test_block(self, text: str) -> bool:
        t = clean_text(text)
        return bool(t and not canonical_field(t) and not detect_heading(t) and re.search(r"(시험방법|시험기준|시험결과|시험일자|시험기간)", t))

    def _extract_block(self, block):
        out: List[Record] = []
        heading_record = self._make_heading_record(block)
        if heading_record is not None:
            out.append(heading_record)
        current_test: Optional[TestAccumulator] = None
        current_generic = GenericAccumulator(block.section_number, block.section_title, block.page_start)
        pending_label: Optional[str] = None

        items = block.items
        for pos, item in enumerate(items):
            future_items = items[pos + 1: pos + 5]

            if item.type == "heading":
                continue

            if item.type == "table_block":
                if current_test is not None:
                    current_test.add_table(item.text or "", item.page)
                else:
                    current_generic.add(item.text or "", item.type, item.page)
                continue

            if item.type == "kv":
                key = item.meta.get("key", "")
                value = item.meta.get("value", "")
                field_name = canonical_field(key)
                pending_label = None

                if field_name == "test_name" and is_probable_test_name(value):
                    self._flush_generic(current_generic, out)
                    current_generic = GenericAccumulator(block.section_number, block.section_title, item.page)
                    self._flush_test(current_test, out)
                    current_test = TestAccumulator(block.section_number, block.section_title, item.page)
                    current_test.add_field("test_name", value)
                    current_test.source_types.add("kv_test_name")
                    current_test.add_raw(f"{key}: {value}")
                    continue

                if current_test is None:
                    current_generic.add(f"{key}: {value}", "kv", item.page)
                    continue

                current_test.set_page(item.page)
                current_test.source_types.add("kv")
                current_test.add_raw(f"{key}: {value}")

                if field_name in {"criteria", "result", "method", "test_date", "test_period", "remarks"}:
                    current_test.add_field(field_name, value)
                    pending_label = field_name
                continue

            if item.type == "line":
                line = clean_text(item.text or "")
                if not line or is_noise(line) or line in {":", "："} or is_page_artifact_line(line) or is_leader_only_line(line):
                    continue

                if current_test is not None and pending_label and not canonical_field(line) and not detect_heading(line) and not is_page_artifact_line(line) and not is_leader_only_line(line) and not (pending_label not in {"method", "test_date", "test_period"} and is_probable_test_name(line)) and not (pending_label not in {"method", "test_date", "test_period"} and is_contextual_test_name(line, future_items)):
                    current_test.set_page(item.page)
                    current_test.source_types.add("label_promoted_value")
                    current_test.add_raw(line)
                    current_test.add_field(pending_label, line)
                    pending_label = None
                    continue
                pending_label = None

                field_name = canonical_field(line)
                if current_test is not None and field_name in {"criteria", "result", "method", "test_date", "test_period", "remarks"}:
                    current_test.set_page(item.page)
                    current_test.source_types.add("label_promoted_value")
                    current_test.add_raw(line)
                    pending_label = field_name
                    continue

                inline = self._parse_inline_field(line)
                if inline and inline[0] == "test_name" and should_start_test(inline[1], block.section_title, future_items):
                    self._flush_generic(current_generic, out)
                    current_generic = GenericAccumulator(block.section_number, block.section_title, item.page)
                    self._flush_test(current_test, out)
                    current_test = TestAccumulator(block.section_number, block.section_title, item.page)
                    current_test.add_field("test_name", inline[1])
                    current_test.source_types.add("line_test_name")
                    current_test.add_raw(line)
                    continue

                if should_start_test(line, block.section_title, future_items):
                    self._flush_generic(current_generic, out)
                    current_generic = GenericAccumulator(block.section_number, block.section_title, item.page)
                    self._flush_test(current_test, out)
                    current_test = TestAccumulator(block.section_number, block.section_title, item.page)
                    current_test.add_field("test_name", line)
                    current_test.source_types.add("line_test_name")
                    current_test.add_raw(line)
                    continue

                if current_test is not None:
                    current_test.set_page(item.page)
                    current_test.source_types.add("line")
                    current_test.add_raw(line)
                    if inline and inline[0] in {"criteria", "result", "method", "test_date", "test_period", "remarks"}:
                        current_test.add_field(inline[0], inline[1])
                else:
                    current_generic.add(line, "line", item.page)

        self._flush_generic(current_generic, out)
        self._flush_test(current_test, out)
        return out

    def _parse_inline_field(self, line):
        m = re.match(r"^\s*([^:：]{1,40})\s*[:：]\s*(.+?)\s*$", line)
        if m:
            field_name = canonical_field(m.group(1))
            if field_name:
                return field_name, clean_text(m.group(2))
        labels = CFG.test_name_labels + CFG.criteria_labels + CFG.result_labels + CFG.method_labels + CFG.date_labels + CFG.period_labels + CFG.remarks_labels
        for label in sorted(set(labels), key=len, reverse=True):
            if line.startswith(label + " "):
                value = clean_text(line[len(label):])
                field_name = canonical_field(label)
                if field_name and value:
                    return field_name, value
        return None

    def _postprocess(self, records: List[Record]) -> List[Record]:
        cleaned: List[Record] = []
        for rec in records:
            rec.raw_text = clean_content_text(rec.raw_text) or ""
            if rec.record_type == "heading":
                rec.content = clean_content_text(rec.content) if rec.content else None
                if not rec.content:
                    continue
            elif rec.record_type == "test":
                rec.test_name = normalize_test_name(rec.test_name or "")
                if not rec.test_name:
                    continue
                rec.criteria = normalize_field_value(rec.criteria) if rec.criteria else None
                rec.result = clean_result_text(rec.result) if rec.result else None
                rec.method = normalize_field_value(rec.method) if rec.method else None
                rec.test_date = normalize_field_value(rec.test_date) if rec.test_date else None
                rec.test_period = normalize_field_value(rec.test_period) if rec.test_period else None
                rec.remarks = normalize_field_value(rec.remarks) if rec.remarks else None
            else:
                rec.content = clean_content_text(rec.content) if rec.content else None
                if not rec.content:
                    continue
            cleaned.append(rec)
        return cleaned


class Pipeline:
    def run(self, pdf_path, output_dir):
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        pages = PDFReader(pdf_path).read()
        items = Normalizer().run(pages)
        sections = SectionBuilder().run(items)
        blocks = BlockBuilder().run(items, sections)
        records = RecordExtractor().run(blocks)
        self._save_json([asdict(x) for x in pages], out_dir / "01_raw_pages.json")
        self._save_json([asdict(x) for x in items], out_dir / "02_normalized_items.json")
        self._save_json([asdict(x) for x in sections], out_dir / "03_sections.json")
        self._save_json([self._block_to_dict(x) for x in blocks], out_dir / "04_blocks.json")
        self._save_json([asdict(x) for x in records], out_dir / "05_records.json")
        summary = {
            "pdf_path": str(pdf_path),
            "total_pages": len(pages),
            "total_items": len(items),
            "total_sections": len(sections),
            "total_blocks": len(blocks),
            "total_records": len(records),
            "output_dir": str(out_dir),
        }
        self._save_json(summary, out_dir / "summary.json")
        return summary

    def _save_json(self, obj, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

    def _block_to_dict(self, block):
        return {
            "section_number": block.section_number,
            "section_title": block.section_title,
            "page_start": block.page_start,
            "page_end": block.page_end,
            "items": [asdict(x) for x in block.items],
        }


def main():
    parser = argparse.ArgumentParser(description="PDF content and test extractor")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    summary = Pipeline().run(args.pdf, args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
