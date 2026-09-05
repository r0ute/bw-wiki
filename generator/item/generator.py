from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

from .. import icon
from . import category, markdown, scanner
from .cache import AssetCache
from .model import Item
from .schema.common import FieldExtractor
from .schema.mapping import schema_module

TITLE = "Items"


def _fields_for(
    item: Item,
    index: category.CategoryIndex,
) -> dict[str, FieldExtractor]:
    module = schema_module(
        index,
        index.nodes[item.category_key],
        item.template,
    )

    return dict(getattr(module, "FIELDS", {}))


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
        context = {
            "path": item.path,
            "template": item.template,
            "category": item.category,
            "category_group": item.category_group or "",
            "icon": "",
            "damaged_item": item.damaged_item,
            "unbroken_parent": item.unbroken_parent,
        }

        icon_path = icon.find_icon(
            item.properties,
            icon_index,
        )

        if icon_path:
            destination = icon.copy_icon(
                icon_path,
                icon_out,
            )

            context["icon"] = (
                f'<img src="{icon_prefix}'
                f'assets/icons/{destination.name}" '
                f'alt="{item.stem}" width="48">'
            )

        rows.append(
            {
                name: extractor(
                    item.properties,
                    context,
                )
                for name, extractor in fields.items()
            }
        )

    rows.sort(key=lambda row: str(row.get("Name", "")).lower())

    return headers, rows


def _group_ancestors(
    index: category.CategoryIndex,
    node: category.CategoryNode,
) -> list[category.CategoryNode]:
    return [index.nodes[key] for key in node.group_ancestors]


def _categories_under(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    by_category,
) -> list[category.CategoryNode]:
    if not node.is_group:
        return [node] if by_category.get(node.key) else []

    return [
        index.nodes[key] for key in node.descendant_categories if by_category.get(key)
    ]


def _is_single_category_group(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    by_category,
) -> bool:
    return (
        node.is_group
        and len(
            _categories_under(
                index,
                node,
                by_category,
            )
        )
        == 1
    )


def _category_path(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    by_category,
) -> str:
    ancestors = _group_ancestors(
        index,
        node,
    )

    parts = [index.slug(group.title) for group in ancestors]

    singleton_group = None

    for group in reversed(ancestors):
        if _is_single_category_group(
            index,
            group,
            by_category,
        ):
            singleton_group = group
            break

    if singleton_group is not None:
        singleton_index = ancestors.index(singleton_group)

        parts = [index.slug(group.title) for group in ancestors[: singleton_index + 1]]

        return (
            "/".join(
                [
                    "items",
                    *parts,
                ]
            )
            + ".md"
        )

    parts.append(index.slug(node.title) + ".md")

    return "/".join(
        [
            "items",
            *parts,
        ]
    )


def _group_path(
    index: category.CategoryIndex,
    node: category.CategoryNode,
) -> str:
    ancestors = _group_ancestors(
        index,
        node,
    )

    parts = [index.slug(group.title) for group in ancestors]

    parts.append(index.slug(node.title) + ".md")

    return "/".join(
        [
            "items",
            *parts,
        ]
    )


def _relative_link(
    source: Path,
    target: Path,
) -> str:
    link = Path(
        os.path.relpath(
            target,
            source.parent,
        )
    ).as_posix()

    return link.removesuffix(".md")


def _category_link(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    docs: Path,
    source: Path,
    by_category,
) -> str:
    target = docs / _category_path(
        index,
        node,
        by_category,
    )

    return _relative_link(
        source,
        target,
    )


def _has_items(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    by_category,
) -> bool:
    if not node.is_group:
        return bool(by_category.get(node.key))

    return bool(
        _categories_under(
            index,
            node,
            by_category,
        )
    )


def _group_page_needed(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    by_category,
) -> bool:
    return not _is_single_category_group(
        index,
        node,
        by_category,
    )


def _group_tree(
    index: category.CategoryIndex,
    node: category.CategoryNode,
    by_category,
    docs: Path,
    source: Path,
    indent: int = 0,
) -> list[str]:
    lines: list[str] = []

    children = sorted(
        (
            child
            for child in index.children(
                node,
                categories_only=False,
            )
            if _has_items(
                index,
                child,
                by_category,
            )
        ),
        key=lambda child: child.title.casefold(),
    )

    prefix = "  " * indent

    for child in children:
        if child.is_group:
            categories = _categories_under(
                index,
                child,
                by_category,
            )

            if not categories:
                continue

            if _is_single_category_group(
                index,
                child,
                by_category,
            ):
                link = _category_link(
                    index,
                    categories[0],
                    docs,
                    source,
                    by_category,
                )

                lines.append(f"{prefix}- [{child.title}]({link})")
            else:
                lines.append(f"{prefix}- {child.title}")

                lines.extend(
                    _group_tree(
                        index,
                        child,
                        by_category,
                        docs,
                        source,
                        indent + 1,
                    )
                )

            continue

        link = _category_link(
            index,
            child,
            docs,
            source,
            by_category,
        )

        lines.append(f"{prefix}- [{child.title}]({link})")

    return lines


def _write_category_pages(
    index: category.CategoryIndex,
    by_category,
    docs: Path,
    icon_index,
    icon_out: Path,
) -> list[dict]:
    pages: list[dict] = []

    root_groups = {node.key: node for node in index.roots() if node.is_group}

    for node in sorted(
        (
            node
            for node in index.nodes.values()
            if (not node.is_group and by_category.get(node.key))
        ),
        key=lambda node: node.title.casefold(),
    ):
        items = by_category[node.key]

        output = docs / _category_path(
            index,
            node,
            by_category,
        )

        ancestors = _group_ancestors(
            index,
            node,
        )

        parent = None
        parent_path = None

        if ancestors:
            root_group = ancestors[0]

            if root_group.key in root_groups and _group_page_needed(
                index,
                root_group,
                by_category,
            ):
                parent = root_group.title
                parent_path = _group_path(
                    index,
                    root_group,
                )

        relative_depth = len(output.relative_to(docs).parts) - 1

        headers, rows = _rows(
            items,
            index,
            icon_index,
            icon_out,
            "../" * relative_depth,
        )

        markdown.write_page(
            output,
            node.title,
            rows=rows,
            headers=headers,
            parent=parent,
            parent_path=parent_path,
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
            for node in index.roots()
            if (
                node.is_group
                and _has_items(
                    index,
                    node,
                    by_category,
                )
                and _group_page_needed(
                    index,
                    node,
                    by_category,
                )
            )
        ),
        key=lambda node: node.title.casefold(),
    )

    for node in groups:
        output = docs / _group_path(
            index,
            node,
        )

        tree = _group_tree(
            index,
            node,
            by_category,
            docs,
            output,
        )

        markdown.write_tree_page(
            output,
            node.title,
            tree,
        )

        relative = output.relative_to(docs).as_posix()

        print(
            f"\tGENERATED {relative} "
            f"({len(_categories_under(index, node, by_category))} categories)"
        )

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
    asset_cache = AssetCache(assets)

    index = category.CategoryIndex.from_assets(asset_cache)

    items = list(
        scanner.discover_items(
            asset_cache,
            index,
        )
    )

    relationships = scanner.load_broken_relationships(asset_cache)

    by_parent: dict[str, str] = {}
    by_broken: dict[str, str] = {}

    for broken, (
        damaged,
        parent,
    ) in relationships.items():
        damaged = damaged or broken

        if parent:
            by_parent[parent] = damaged

        by_broken[damaged] = parent

    for item in items:
        item.damaged_item = by_parent.get(
            item.stem,
            "",
        )
        item.unbroken_parent = by_broken.get(
            item.stem,
            "",
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
        if not _has_items(
            index,
            node,
            by_category,
        ):
            continue

        if node.is_group:
            if _group_page_needed(
                index,
                node,
                by_category,
            ):
                page = group_by_node.get(node.key)
            else:
                categories = _categories_under(
                    index,
                    node,
                    by_category,
                )

                if len(categories) == 1:
                    category_node = categories[0]

                    page = {
                        "title": node.title,
                        "slug": _category_path(
                            index,
                            category_node,
                            by_category,
                        ).removesuffix(".md"),
                    }
                else:
                    page = None
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
