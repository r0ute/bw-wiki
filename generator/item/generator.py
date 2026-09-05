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


def _group_path(
    index: category.CategoryIndex,
    node: category.CategoryNode,
) -> str:
    ancestors = _group_ancestors(index, node)

    parts = [category.CategoryIndex.slug(group.title) for group in ancestors]

    parts.append(category.CategoryIndex.slug(node.title) + ".md")

    return "/".join(["items", *parts])


def _category_link(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    docs: Path,
    source: Path,
) -> str:
    target = docs / _category_path(index, node)

    return _relative_link(source, target)


def _group_link(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    docs: Path,
    source: Path,
) -> str:
    target = docs / _group_path(index, node)

    return _relative_link(source, target)


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


def _has_items(
    node: category.CategoryNode,
    by_category,
    index: category.CategoryIndex,
) -> bool:
    if not node.is_group:
        return bool(by_category.get(node.key))

    return any(
        _has_items(child, by_category, index)
        for child in index.children(node, categories_only=False)
    )


def _group_tree(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    by_category,
    docs: Path,
    source: Path,
) -> list[str]:
    lines: list[str] = []

    children = sorted(
        (
            child
            for child in index.children(
                node,
                categories_only=False,
            )
            if _has_items(child, by_category, index)
        ),
        key=lambda child: child.title.casefold(),
    )

    for child in children:
        if child.is_group:
            link = _group_link(
                index,
                child,
                docs,
                source,
            )

            lines.append(f"- [{child.title}]({link})")
            continue

        link = _category_link(
            index,
            child,
            docs,
            source,
        )

        lines.append(f"- [{child.title}]({link})")

    return lines


def _write_category_pages(
    index: category.CategoryIndex,
    by_category,
    docs: Path,
    icon_index,
    icon_out: Path,
) -> list[dict]:
    pages: list[dict] = []

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

        relative = output.relative_to(docs).as_posix()

        print(f"\tGENERATED {relative} ({len(items)} items)")

        pages.append(
            {
                "title": node.title,
                "slug": relative.removesuffix(".md"),
                "node": node,
            }
        )

    return pages


def _write_group_pages(
    index: category.CategoryIndex,
    by_category,
    docs: Path,
) -> list[dict]:
    pages: list[dict] = []

    groups = sorted(
        (
            node
            for node in index.nodes.values()
            if node.is_group and _has_items(node, by_category, index)
        ),
        key=lambda node: node.title.casefold(),
    )

    for node in groups:
        output = docs / _group_path(index, node)

        source = output

        links = []

        for child in sorted(
            (
                child
                for child in index.children(
                    node,
                    categories_only=False,
                )
                if _has_items(child, by_category, index)
            ),
            key=lambda child: child.title.casefold(),
        ):
            if child.is_group:
                target = docs / _group_path(index, child)
            else:
                target = docs / _category_path(index, child)

            links.append(
                (
                    child.title,
                    _relative_link(
                        source,
                        target,
                    ),
                )
            )

        markdown.write_page(
            output,
            node.title,
            links=links,
        )

        relative = output.relative_to(docs).as_posix()

        print(f"\tGENERATED {relative} ({len(links)} categories)")

        pages.append(
            {
                "title": node.title,
                "slug": relative.removesuffix(".md"),
                "node": node,
            }
        )

    return pages


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

    category_pages = _write_category_pages(
        index,
        by_category,
        docs,
        icon_index,
        icon_out,
    )

    group_pages = _write_group_pages(
        index,
        by_category,
        docs,
    )

    category_by_node = {page["node"].key: page for page in category_pages}

    group_by_node = {page["node"].key: page for page in group_pages}

    pages: list[dict] = []

    for node in index.roots():
        if not _has_items(node, by_category, index):
            continue

        if node.is_group:
            page = group_by_node.get(node.key)
        else:
            page = category_by_node.get(node.key)

        if not page:
            continue

        pages.append(
            {
                "title": page["title"],
                "slug": page["slug"],
            }
        )

    print(f"Item definitions discovered: {len(items)}")

    return {
        "title": TITLE,
        "pages": pages,
    }
