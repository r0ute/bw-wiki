from __future__ import annotations

import json
from pathlib import Path

from ..navigation import breadcrumb_include, navigation_metadata


def markdown_value(value):
    if value is None:
        return ""

    return str(value).replace("|", r"\|").replace("\n", " ")


def render_table(
    rows,
    headers,
):
    if not headers:
        return []

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    lines += [
        "| "
        + " | ".join(
            markdown_value(
                row.get(
                    header,
                    "",
                )
            )
            for header in headers
        )
        + " |"
        for row in rows
    ]

    return lines


def _front_matter(
    title: str,
    *,
    parent: str | None = None,
    parent_path: str | None = None,
    grand_parent: str | None = None,
    grand_parent_path: str | None = None,
) -> list[str]:
    return [
        "---",
        "layout: default",
        f"title: {json.dumps(title)}",
        *navigation_metadata(
            parent=parent,
            parent_path=parent_path,
            grand_parent=grand_parent,
            grand_parent_path=grand_parent_path,
        ),
        "---",
        "",
        *breadcrumb_include(),
    ]


def render_page(
    title,
    *,
    rows=None,
    headers=None,
    links=None,
    parent=None,
    parent_path=None,
    grand_parent=None,
    grand_parent_path=None,
):
    lines = [
        *_front_matter(
            title,
            parent=parent,
            parent_path=parent_path,
            grand_parent=grand_parent,
            grand_parent_path=grand_parent_path,
        ),
        f"# {title}",
        "",
    ]

    if links:
        lines.extend(f"- [{title}]({url})" for title, url in links)

        lines.append("")

    if rows is not None and headers:
        lines.extend(
            render_table(
                rows,
                headers,
            )
        )

        lines.append("")

    return "\n".join(lines)


def write_page(
    output: Path,
    title: str,
    *,
    rows=None,
    headers=None,
    links=None,
    parent=None,
    parent_path=None,
    grand_parent=None,
    grand_parent_path=None,
):
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        render_page(
            title,
            rows=rows,
            headers=headers,
            links=links,
            parent=parent,
            parent_path=parent_path,
            grand_parent=grand_parent,
            grand_parent_path=grand_parent_path,
        ),
        encoding="utf-8",
    )


def render_tree_page(
    title: str,
    tree: list[str],
) -> str:
    lines = [
        *_front_matter(title),
        f"# {title}",
        "",
        *tree,
        "",
    ]

    return "\n".join(lines)


def write_tree_page(
    output: Path,
    title: str,
    tree: list[str],
):
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        render_tree_page(
            title,
            tree,
        ),
        encoding="utf-8",
    )
