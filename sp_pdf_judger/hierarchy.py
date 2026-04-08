from __future__ import annotations

from .schemas import Evaluation, ExtractedRecord, TreeNode
from .utils import clean_text, slugify


def _section_sort_key(section_number: str) -> tuple:
    parts: list[tuple[int, int | str]] = []
    for token in clean_text(section_number).split("."):
        try:
            parts.append((0, int(token)))
        except ValueError:
            parts.append((1, token))
    return tuple(parts)


def _child_sort_key(node: TreeNode) -> tuple:
    if node.node_type == "section":
        return (0, _section_sort_key(node.section_number or "9999"))
    return (1, node.page_start or 999999, clean_text(node.title))


def _ensure_section_node(
    section_nodes: dict[str, TreeNode],
    section_number: str,
    title: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
) -> TreeNode:
    cleaned_title = clean_text(title)

    if section_number not in section_nodes:
        section_nodes[section_number] = TreeNode(
            key=f"section-{section_number}",
            title=f"{section_number} {cleaned_title}".strip() if cleaned_title else section_number,
            level=len(section_number.split(".")),
            section_number=section_number,
            section_title=cleaned_title or None,
            node_type="section",
            page_start=page_start,
            page_end=page_end,
        )
    else:
        node = section_nodes[section_number]
        if cleaned_title and not node.section_title:
            node.section_title = cleaned_title
            node.title = f"{section_number} {cleaned_title}".strip()

        if page_start is not None and (node.page_start is None or page_start < node.page_start):
            node.page_start = page_start
        if page_end is not None and (node.page_end is None or page_end > node.page_end):
            node.page_end = page_end

    return section_nodes[section_number]


def build_document_tree(
    records: list[ExtractedRecord],
    evaluations: list[Evaluation],
    section_title_map: dict[str, str] | None = None,
) -> list[TreeNode]:
    section_title_map = section_title_map or {}
    section_nodes: dict[str, TreeNode] = {}

    for section_number, title in section_title_map.items():
        cleaned_number = clean_text(section_number)
        if not cleaned_number:
            continue
        _ensure_section_node(section_nodes, cleaned_number, title=title)

    for record in records:
        section_number = clean_text(record.section_number)
        if not section_number:
            continue

        parts = section_number.split(".")
        for i in range(1, len(parts) + 1):
            prefix = ".".join(parts[:i])
            prefix_title = section_title_map.get(prefix)
            if i == len(parts) and not prefix_title:
                prefix_title = record.section_title

            _ensure_section_node(
                section_nodes,
                prefix,
                title=prefix_title,
                page_start=record.page_start,
                page_end=record.page_end,
            )

    roots: list[TreeNode] = []

    for section_number in sorted(section_nodes.keys(), key=_section_sort_key):
        node = section_nodes[section_number]
        parts = section_number.split(".")
        parent = section_nodes.get(".".join(parts[:-1])) if len(parts) > 1 else None

        if parent is None:
            roots.append(node)
        else:
            parent.children.append(node)

    eval_iter = iter(evaluations)

    for idx, record in enumerate(records, start=1):
        section_number = clean_text(record.section_number)
        parent = section_nodes.get(section_number) if section_number else None
        if parent is None:
            continue

        if record.record_type == "content":
            leaf_title = clean_text(record.content_label) or clean_text(record.section_title) or "세부정보"
            if leaf_title == clean_text(record.section_title):
                leaf_title = "세부정보"

            parent.children.append(
                TreeNode(
                    key=f"content-{section_number}-{idx}",
                    title=leaf_title,
                    level=parent.level + 1,
                    section_number=record.section_number,
                    section_title=record.section_title,
                    node_type="content",
                    page_start=record.page_start,
                    page_end=record.page_end,
                    info_lines=[clean_text(record.content or "")],
                )
            )

        elif record.record_type == "test":
            ev = next(eval_iter, None)
            if ev is None:
                continue

            parent.children.append(
                TreeNode(
                    key=f"{section_number}-{slugify(ev.test_name)}-{idx}",
                    title=ev.test_name,
                    level=parent.level + 1,
                    section_number=ev.section_number,
                    section_title=ev.section_title,
                    node_type="test",
                    status=ev.final_status if ev.comparison_completed else None,
                    page_start=ev.page_start,
                    page_end=ev.page_end,
                    evaluation=ev,
                )
            )

    def finalize(node: TreeNode) -> None:
        for child in node.children:
            finalize(child)
        node.children.sort(key=_child_sort_key)
        if node.node_type == "section":
            node.status = None

    for root in roots:
        finalize(root)

    roots.sort(key=_child_sort_key)
    return roots