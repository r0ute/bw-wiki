from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .. import icon
from . import category, markdown, scanner
from .model import Item
from .schema.common import FieldExtractor
from .schema.mapping import schema_module

TITLE = "Items"


def _fields_for(item: Item, index: category.CategoryIndex) -> dict[str, FieldExtractor]:
    node = index.nodes[item.category_key]
    module = schema_module(index, node, item.template)
    return dict(getattr(module, "FIELDS", {}))


def _item_context(item: Item, icon_index, icon_out: Path, icon_prefix: str):
    context = {
        "path": item.path,
        "source_family": item.source_family,
        "template": item.template,
        "category": item.category,
        "category_group": item.category_group or "",
        "icon": "",
        "damaged_item": item.damaged_item,
        "unbroken_parent": item.unbroken_parent,
    }

    icon_path = icon.find_icon(item.properties, icon_index)

    if icon_path:
        destination = icon.copy_icon(icon_path, icon_out)
        context["icon"] = (
            f'<img src="{icon_prefix}assets/icons/{destination.name}" '
            f'alt="{item.stem}" width="48">'
        )

    return context


def _rows(
    items,
    index,
    icon_index,
    icon_out,
    icon_prefix,
):
    if not items:
        return [], []

    field_sets = [_fields_for(item, index) for item in items]

    headers: list[str] = []

    for fields in field_sets:
        for name in fields:
            if name not in headers:
                headers.append(name)

    rows = []

    for item, fields in zip(items, field_sets):
        context = _item_context(
            item,
            icon_index,
            icon_out,
            icon_prefix,
        )

        rows.append(
            {
                name: extractor(item.properties, context)
                for name, extractor in fields.items()
            }
        )

    rows.sort(
        key=lambda row: str(row.get("Name", "")).lower(),
    )

    return headers, rows


def _relationship_maps(assets):
    by_parent: dict[str, str] = {}
    by_broken: dict[str, str] = {}

    for broken, (damaged, parent) in scanner.load_broken_relationships(assets).items():
        damaged = damaged or broken

        if parent:
            by_parent[parent] = damaged

        by_broken[damaged] = parent

    return by_parent, by_broken


def _apply_relationships(items, assets):
    by_parent, by_broken = _relationship_maps(assets)

    for item in items:
        item.damaged_item = by_parent.get(item.stem, "")
        item.unbroken_parent = by_broken.get(item.stem, "")


def _group_ancestors(
    index: category.CategoryIndex,
    node: category.CategoryNode,
) -> list[category.CategoryNode]:
    ancestors = []

    current = index.nodes.get(node.parent_key) if node.parent_key else None

    while current:
        if current.is_group:
            ancestors.append(current)

        current = index.nodes.get(current.parent_key) if current.parent_key else None

    ancestors.reverse()

    return ancestors


def _category_path(
    index: category.CategoryIndex,
    node: category.CategoryNode,
) -> str:
    parts = [
        category.CategoryIndex.slug(group.title)
        for group in _group_ancestors(index, node)
    ]

    parts.append(category.CategoryIndex.slug(node.title) + ".md")

    return "/".join(["items", *parts])


def _relative_link(source: Path, target: Path) -> str:
    import os

    link = Path(
        os.path.relpath(
            target,
            source.parent,
        )
    ).as_posix()

    if link.endswith(".md"):
        link = link[:-3]

    return link


def _tree_lines(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    docs: Path,
    source: Path,
    indent: int = 0,
) -> list[str]:
    """
    Render the complete category hierarchy.

    Groups are rendered as plain tree nodes.
    Actual item categories are rendered as links.
    """

    lines: list[str] = []

    children = sorted(
        index.children(
            node,
            categories_only=False,
        ),
        key=lambda child: child.title.casefold(),
    )

    for child in children:
        padding = "  " * indent

        if child.is_group:
            lines.append(f"{padding}- {child.title}")

            lines.extend(
                _tree_lines(
                    index,
                    child,
                    docs,
                    source,
                    indent + 1,
                )
            )

            continue

        target = docs / _category_path(
            index,
            child,
        )

        link = _relative_link(
            source,
            target,
        )

        lines.append(f"{padding}- [{child.title}]({link})")

    return lines


def _tree_lines(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    docs: Path,
    source: Path,
    by_category,
    indent: int = 0,
) -> list[str]:
    """
    Render the complete category hierarchy.

    Groups are rendered as plain tree nodes.
    Actual item categories are rendered as links.
    """

    lines: list[str] = []

    children = sorted(
        index.children(
            node,
            categories_only=False,
        ),
        key=lambda child: child.title.casefold(),
    )

    for child in children:
        padding = "  " * indent

        if child.is_group:
            lines.append(f"{padding}- {child.title}")

            lines.extend(
                _tree_lines(
                    index,
                    child,
                    docs,
                    source,
                    by_category,
                    indent + 1,
                )
            )

            continue

        if not by_category.get(child.key):
            continue

        target = docs / _category_path(
            index,
            child,
        )

        link = _relative_link(
            source,
            target,
        )

        lines.append(f"{padding}- [{child.title}]({link})")

    return lines


def _root_tree(
    index: category.CategoryIndex,
    docs: Path,
    source: Path,
    by_category,
) -> list[str]:
    lines: list[str] = []

    for node in index.roots():
        if node.is_group:
            lines.append(f"- {node.title}")

            lines.extend(
                _tree_lines(
                    index,
                    node,
                    docs,
                    source,
                    by_category,
                    indent=1,
                )
            )
        else:
            if not by_category.get(node.key):
                continue

            target = docs / _category_path(
                index,
                node,
            )

            link = _relative_link(
                source,
                target,
            )

            lines.append(f"- [{node.title}]({link})")

    return lines


def _write_category_pages(
    index: category.CategoryIndex,
    by_category,
    docs: Path,
    icon_index,
    icon_out: Path,
) -> list[str]:
    generated: list[str] = []

    for node in sorted(
        (n for n in index.nodes.values() if not n.is_group),
        key=lambda n: n.title.casefold(),
    ):
        items = by_category.get(node.key, [])

        if not items:
            continue

        ancestors = _group_ancestors(
            index,
            node,
        )

        output = docs / "items"

        for group in ancestors:
            output /= category.CategoryIndex.slug(group.title)

        output /= category.CategoryIndex.slug(node.title) + ".md"

        relative_depth = len(ancestors) + 1
        icon_prefix = "../" * relative_depth

        headers, rows = _rows(
            items,
            index,
            icon_index,
            icon_out,
            icon_prefix,
        )

        markdown.write_page(
            output,
            node.title,
            rows=rows,
            headers=headers,
        )

        generated.append(str(output.relative_to(docs)).replace("\\", "/"))

        print(f"\tGENERATED {output.relative_to(docs).as_posix()} ({len(items)} items)")

    return generated


def generate(
    assets: Path,
    docs: Path,
    icon_out: Path,
    icon_index: dict[str, Path],
) -> dict:
    index = category.build_category_index(assets)

    items = list(
        scanner.discover_items(
            assets,
            index,
        )
    )

    _apply_relationships(
        items,
        assets,
    )

    by_category = defaultdict(list)

    for item in items:
        by_category[item.category_key].append(item)

    generated = _write_category_pages(
        index,
        by_category,
        docs,
        icon_index,
        icon_out,
    )

    item_root = docs / "items"
    item_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    item_index = item_root / "items.md"

    tree = _root_tree(
        index,
        docs,
        item_index,
        by_category,
    )

    markdown.write_tree_page(
        item_index,
        TITLE,
        tree,
    )

    generated.append("items/items.md")

    print(f"Item definitions discovered: {len(items)}")

    return {
        "title": TITLE,
        "pages": [
            {
                "title": TITLE,
                "slug": "items/items",
            }
        ],
    }
