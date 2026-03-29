from __future__ import annotations

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


def _status_dot(status: str | None, show: bool = True) -> str:
    if not show:
        return ""

    if status == PASS_LABEL:
        color = STATUS_COLORS[PASS_LABEL]
    elif status == FAIL_LABEL:
        color = STATUS_COLORS[FAIL_LABEL]
    else:
        color = "#9ca3af"

    return f'<span style="width:12px;height:12px;border-radius:50%;display:inline-block;background:{color};margin-right:10px;flex:0 0 auto;"></span>'


def _kv_line(label: str, value: str | None) -> str:
    if not value:
        return ""
    return f"""
    <div style="display:flex;align-items:flex-end;gap:16px;margin-top:12px;">
      <div style="min-width:110px;font-weight:800;color:#111827;white-space:nowrap;">
        {html_escape(label)}
      </div>
      <div style="flex:1;border-bottom:1px solid #9ca3af;padding:0 4px 6px 4px;color:#111827;white-space:pre-wrap;line-height:1.6;">
        {html_escape(value)}
      </div>
    </div>
    """


def _render_normalized_block(node: TreeNode) -> str:
    ev = node.evaluation
    if ev is None:
        return ""

    lines: list[str] = []
    if ev.normalized_criteria:
        lines.append(f'<div style="margin-top:4px;">정규화 시험기준: {html_escape(ev.normalized_criteria)}</div>')
    if ev.normalized_result:
        lines.append(f'<div style="margin-top:4px;">정규화 시험결과: {html_escape(ev.normalized_result)}</div>')

    if not lines:
        return ""

    return f"""
    <div style="margin-top:12px;padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px;background:#f8fafc;color:#4b5563;line-height:1.65;font-size:14px;">
      {''.join(lines)}
    </div>
    """


def _render_test_leaf(node: TreeNode, depth_px: int) -> str:
    ev = node.evaluation
    if ev is None:
        return ""

    body = f"""
    <div style="padding:10px 2px 8px 6px;">
      {_kv_line("시험기준", ev.criteria)}
      {_kv_line("시험결과", ev.result)}
      <div style="margin-top:14px;color:#111827;line-height:1.75;">
        <span style="font-weight:800;">판정 이유</span>
        <span style="margin-left:10px;">{html_escape(ev.reason)}</span>
      </div>
      {_render_normalized_block(node)}
    </div>
    """

    return f"""
    <details style="margin-left:{depth_px}px;border:1px solid #e5e7eb;border-radius:12px;padding:10px 14px;background:#fff;margin-top:10px;">
      <summary style="list-style:none;cursor:pointer;font-size:17px;font-weight:700;display:flex;align-items:center;">
        {_status_dot(node.status, show=True)}{html_escape(node.title)}
      </summary>
      {body}
    </details>
    """


def _render_section(node: TreeNode, depth_px: int = 0) -> str:
    summary_html = f"""
    <summary style="list-style:none;cursor:pointer;font-size:18px;font-weight:800;display:flex;align-items:center;">
      {html_escape(node.title)}
    </summary>
    """

    inner = ""
    for child in node.children:
        if child.node_type == "test":
            inner += _render_test_leaf(child, depth_px=18)
        else:
            inner += _render_section(child, depth_px=18)

    return f"""
    <details open style="margin-left:{depth_px}px;border:1px solid #dbe3ea;border-radius:14px;padding:12px 16px;background:#fafcff;margin-top:12px;">
      {summary_html}
      <div style="padding-top:6px;">
        {inner}
      </div>
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