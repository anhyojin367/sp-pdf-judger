from __future__ import annotations

from collections import defaultdict

from .config import FAIL_LABEL, PASS_LABEL
from .schemas import Evaluation, TreeNode
from .utils import clean_text, slugify


def aggregate_status(children: list[TreeNode]) -> str | None:
    statuses = [c.status for c in children if c.status]
    if not statuses:
        return None
    if FAIL_LABEL in statuses:
        return FAIL_LABEL
    return PASS_LABEL


def _section_sort_key(section_number: str) -> tuple:
    parts: list[tuple[int, int | str]] = []
    for token in clean_text(section_number).split("."):
        try:
            parts.append((0, int(token)))
        except ValueError:
            parts.append((1, token))
    return tuple(parts)


def _evaluation_sort_key(ev: Evaluation) -> tuple:
    return (ev.page_start or 999999, ev.page_end or 999999, clean_text(ev.test_name))


def _child_sort_key(node: TreeNode) -> tuple:
    if node.node_type == "section":
        return (0, _section_sort_key(node.section_number or "9999"))
    return (1, node.page_start or 999999, clean_text(node.title))


def build_document_tree(evaluations: list[Evaluation]) -> list[TreeNode]:
    section_nodes: dict[str, TreeNode] = {}
    section_items: dict[str, list[Evaluation]] = defaultdict(list)
    no_section_items: list[Evaluation] = []

    for ev in evaluations:
        section_number = clean_text(ev.section_number)
        if not section_number:
            no_section_items.append(ev)
            continue

        section_items[section_number].append(ev)

        if section_number not in section_nodes:
            section_nodes[section_number] = TreeNode(
                key=f"section-{section_number}",
                title=f"{section_number} {clean_text(ev.section_title)}".strip(),
                level=len(section_number.split(".")),
                section_number=section_number,
                section_title=clean_text(ev.section_title) or None,
                node_type="section",
                page_start=ev.page_start,
                page_end=ev.page_end,
            )
        else:
            node = section_nodes[section_number]
            if node.page_start is None or ev.page_start < node.page_start:
                node.page_start = ev.page_start
            if node.page_end is None or ev.page_end > node.page_end:
                node.page_end = ev.page_end

    roots: list[TreeNode] = []

    for section_number in sorted(section_nodes.keys(), key=_section_sort_key):
        node = section_nodes[section_number]
        parent = None
        parts = section_number.split(".")

        for i in range(len(parts) - 1, 0, -1):
            prefix = ".".join(parts[:i])
            if prefix in section_nodes:
                parent = section_nodes[prefix]
                break

        if parent is None:
            roots.append(node)
        else:
            parent.children.append(node)

    for section_number, items in section_items.items():
        parent = section_nodes[section_number]
        for idx, ev in enumerate(sorted(items, key=_evaluation_sort_key), start=1):
            parent.children.append(
                TreeNode(
                    key=f"{section_number}-{slugify(ev.test_name)}-{idx}",
                    title=ev.test_name,
                    level=parent.level + 1,
                    section_number=ev.section_number,
                    section_title=ev.section_title,
                    node_type="test",
                    status=ev.final_status,
                    page_start=ev.page_start,
                    page_end=ev.page_end,
                    evaluation=ev,
                )
            )

    if no_section_items:
        misc = TreeNode(
            key="section-etc",
            title="기타",
            level=1,
            node_type="section",
        )
        for idx, ev in enumerate(sorted(no_section_items, key=_evaluation_sort_key), start=1):
            misc.children.append(
                TreeNode(
                    key=f"etc-{slugify(ev.test_name)}-{idx}",
                    title=ev.test_name,
                    level=2,
                    node_type="test",
                    status=ev.final_status,
                    page_start=ev.page_start,
                    page_end=ev.page_end,
                    evaluation=ev,
                )
            )
        roots.append(misc)

    def finalize(node: TreeNode) -> None:
        for child in node.children:
            finalize(child)
        node.children.sort(key=_child_sort_key)
        if node.node_type == "section":
            node.status = aggregate_status(node.children)

    for root in roots:
        finalize(root)

    roots.sort(key=_child_sort_key)
    return roots