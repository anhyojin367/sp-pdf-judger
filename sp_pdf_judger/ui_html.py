from __future__ import annotations

import re

from .config import FAIL_LABEL, PASS_LABEL, STATUS_COLORS
from .schemas import ProcessingResult, Summary, TreeNode
from .utils import html_escape


def render_summary_card(summary: Summary) -> str:
    return f"""
    <div style="border:1px solid #e5e7eb;border-radius:18px;padding:20px;background:#ffffff;box-shadow:0 6px 20px rgba(0,0,0,0.03);">
      <div style="font-size:24px;font-weight:800;margin-bottom:18px;">요약</div>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;font-size:18px;">
        <span style="width:14px;height:14px;border-radius:50%;display:inline-block;background:{STATUS_COLORS[PASS_LABEL]};"></span>
        <span>검수합격: <b>{summary.passed}</b>건</span>
      </div>
      <div style="display:flex;align-items:center;gap:10px;font-size:18px;">
        <span style="width:14px;height:14px;border-radius:50%;display:inline-block;background:{STATUS_COLORS[FAIL_LABEL]};"></span>
        <span>검수불합격: <b>{summary.failed}</b>건</span>
      </div>
      <div style="margin-top:12px;color:#6b7280;">전체 {summary.total}건</div>
    </div>
    """


def _normalize_display_value(value: str | None) -> str:
    if not value:
        return ""
    value = value.replace("\\r\\n", "\n").replace("\\n", "\n")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return value.strip()


def _format_criteria_display(value: str | None) -> str | None:
    text = _normalize_display_value(value)
    if not text:
        return None

    compact = re.sub(r"\s+", " ", text).strip()
    compact = compact.replace("（", "(").replace("）", ")")
    compact = re.sub(r"기준\s*\(([^)]+)\)\s*(이상|이하|미만|초과)", r"\1 \2", compact)
    compact = re.sub(r"^(이상|이하|미만|초과)\s+(.+)$", r"\2 \1", compact)
    compact = re.sub(r"\(([0-9]+(?:\.[0-9]+)?)\)\s*(이상|이하|미만|초과)", r"\1 \2", compact)
    return compact


def _status_light(status: str | None) -> str:
    if status == PASS_LABEL:
        color = STATUS_COLORS[PASS_LABEL]
    elif status == FAIL_LABEL:
        color = STATUS_COLORS[FAIL_LABEL]
    else:
        color = "#d1d5db"

    return f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};"></span>'


def _kv_line(label: str, value: str | None, status: str | None = None) -> str:
    display_value = _format_criteria_display(value) if label == "시험기준" else _normalize_display_value(value)
    if not display_value:
        return ""

    status_html = _status_light(status) if status else ""
    grid_cols = "126px 1fr 24px" if status_html else "126px 1fr"

    return f"""
    <div style="display:grid;grid-template-columns:{grid_cols};column-gap:12px;align-items:end;margin-top:8px;">
      <div style="font-weight:800;color:#111827;line-height:1.15;">{html_escape(label)}</div>
      <div style="color:#111827;white-space:pre-wrap;line-height:1.55;padding:0 1px 6px 1px;border-bottom:1px solid #9ca3af;">{html_escape(display_value)}</div>
      {f'<div style="display:flex;align-items:center;justify-content:flex-end;padding-bottom:6px;">{status_html}</div>' if status_html else ''}
    </div>
    """


def _render_lot_table(ev) -> str:
    rows = getattr(ev, "lot_judgements", None) or []
    if not rows:
        return ""

    header = "".join([
        '<th style="border:1px solid #dbe3ea;padding:8px 10px;text-align:left;background:#f8fafc;">로트번호</th>',
        '<th style="border:1px solid #dbe3ea;padding:8px 10px;text-align:left;background:#f8fafc;">시험기간</th>',
        '<th style="border:1px solid #dbe3ea;padding:8px 10px;text-align:left;background:#f8fafc;">시험결과</th>',
        '<th style="border:1px solid #dbe3ea;padding:8px 10px;text-align:center;background:#f8fafc;">판정</th>',
    ])

    body_rows = []
    for row in rows:
        body_rows.append(
            "<tr>"
            f'<td style="border:1px solid #dbe3ea;padding:8px 10px;">{html_escape(row.get("lot_no", ""))}</td>'
            f'<td style="border:1px solid #dbe3ea;padding:8px 10px;">{html_escape(row.get("test_date", ""))}</td>'
            f'<td style="border:1px solid #dbe3ea;padding:8px 10px;">{html_escape(row.get("result", ""))}</td>'
            f'<td style="border:1px solid #dbe3ea;padding:8px 10px;text-align:center;">{_status_light(row.get("status"))}</td>'
            "</tr>"
        )

    return f"""
    <div style="display:grid;grid-template-columns:126px 1fr;column-gap:12px;align-items:start;margin-top:8px;">
      <div style="font-weight:800;color:#111827;line-height:1.15;padding-top:8px;">시험결과</div>
      <div style="padding:0 0 6px 0;border-bottom:1px solid #9ca3af;overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;background:#ffffff;">
          <thead><tr>{header}</tr></thead>
          <tbody>{''.join(body_rows)}</tbody>
        </table>
      </div>
    </div>
    """


def _render_reason_box(ev) -> str:
    if not getattr(ev, "comparison_completed", False):
        return ""

    rows = getattr(ev, "lot_judgements", None) or []
    if rows:
        reason_html = "".join(
            f'<div style="margin-top:6px;"><b>{html_escape(row.get("lot_no", ""))}</b>: {html_escape(row.get("reason", ""))}</div>'
            for row in rows
            if row.get("lot_no") and row.get("reason")
        )
    else:
        if not getattr(ev, "reason", ""):
            return ""
        reason_html = html_escape(ev.reason)

    normalized = ""
    if ev.normalized_criteria or ev.normalized_result:
        normalized = f"""
        <div style="margin-top:8px;color:#4b5563;line-height:1.55;font-size:14px;">
          {f'<div>정규화 시험기준: {html_escape(ev.normalized_criteria)}</div>' if ev.normalized_criteria else ''}
          {f'<div>정규화 시험결과: {html_escape(ev.normalized_result)}</div>' if ev.normalized_result else ''}
        </div>
        """

    return f"""
    <div style="margin-top:16px;padding:14px 16px;border-radius:14px;background:linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);border:1px solid #dbe3ea;border-left:5px solid #111827;">
      <div style="font-weight:800;color:#111827;margin-bottom:6px;">판정 이유</div>
      <div style="color:#111827;line-height:1.75;">{reason_html}</div>
      {normalized}
    </div>
    """


def _render_test_leaf(node: TreeNode, depth_px: int) -> str:
    ev = node.evaluation
    if ev is None:
        return ""

    result_block = (
        _render_lot_table(ev)
        if getattr(ev, "lot_judgements", None)
        else _kv_line(
            "시험결과",
            getattr(ev, "result", None),
            status=getattr(ev, "final_status", None) if getattr(ev, "comparison_completed", False) else None,
        )
    )

    body = "".join([
        _kv_line("시험방법", getattr(ev, "method", None)),
        _kv_line("시험기준", getattr(ev, "criteria", None)),
        _kv_line("시험일자", getattr(ev, "test_date", None)),
        _kv_line("시험기간", getattr(ev, "test_period", None)),
        result_block,
        _render_reason_box(ev),
        _kv_line("비고", getattr(ev, "remarks", None)),
    ])

    return f"""
    <div style="margin-left:{depth_px}px;border:1px solid #e5e7eb;border-radius:14px;background:#ffffff;margin-top:10px;overflow:hidden;">
      <div style="padding:14px 16px 8px 16px;font-size:17px;font-weight:800;color:#111827;">
        <span>{html_escape(node.title)}</span>
      </div>
      <div style="padding:4px 16px 16px 16px;">{body}</div>
    </div>
    """


def _render_content_leaf(node: TreeNode, depth_px: int) -> str:
    content = "\n\n".join([x for x in node.info_lines if _normalize_display_value(x)])
    if not content:
        return ""

    return f"""
    <div style="margin-left:{depth_px}px;border:1px solid #e5e7eb;border-radius:14px;background:#ffffff;margin-top:10px;overflow:hidden;">
      <div style="padding:14px 16px 8px 16px;font-size:17px;font-weight:800;color:#111827;">
        <span>{html_escape(node.title)}</span>
      </div>
      <div style="padding:8px 16px 16px 16px;">
        <div style="white-space:pre-wrap;line-height:1.8;color:#111827;">{html_escape(content)}</div>
      </div>
    </div>
    """


def _render_section(node: TreeNode, depth_px: int = 0) -> str:
    summary_html = f"""
    <summary style="list-style:none;cursor:pointer;font-size:18px;font-weight:800;display:flex;align-items:center;color:#111827;">
      {html_escape(node.title)}
    </summary>
    """

    inner = ""
    for child in node.children:
        if child.node_type == "test":
            inner += _render_test_leaf(child, depth_px=18)
        elif child.node_type == "content":
            inner += _render_content_leaf(child, depth_px=18)
        else:
            inner += _render_section(child, depth_px=18)

    return f"""
    <details open style="margin-left:{depth_px}px;border:1px solid #dbe3ea;border-radius:14px;padding:12px 16px;background:#fafcff;margin-top:12px;">
      {summary_html}
      <div style="padding-top:6px;">{inner}</div>
    </details>
    """


def render_result_html(result: ProcessingResult) -> str:
    styles = """
    <style>
      details > summary::-webkit-details-marker { display:none; }
      details > summary::before {
        content: "▸";
        font-size: 16px;
        color: #4b5563;
        margin-right: 10px;
        display: inline-block;
        transform: rotate(0deg);
        transition: transform 0.15s ease-in-out;
      }
      details[open] > summary::before {
        transform: rotate(90deg);
      }
    </style>
    """

    if not result.tree:
        body = """
        <div style="border:1px solid #e5e7eb;border-radius:14px;padding:18px;background:#ffffff;color:#6b7280;">
          표시할 시험 항목이 없습니다.
        </div>
        """
    else:
        body = "".join(_render_section(node, depth_px=0) for node in result.tree)

    return styles + body