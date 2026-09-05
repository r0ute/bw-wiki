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

    for item, fields in zip(
        items,
        field_sets,
    ):
        context = {
            "path": item.path,
            "template": item.template,
            "category": item.category,
            "category_group": (item.category_group or ""),
            "icon": "",
            "damaged_item": item.damaged_item,
            "unbroken_parent": (item.unbroken_parent),
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


def _category_path(
    index,
    node,
    populated,
):
    ancestors = [index.nodes[key] for key in node.group_ancestors]

    parts = [index.slug(group.title) for group in ancestors]

    for group in reversed(ancestors):
        if len(populated.get(group.key, ())) == 1:
            return (
                "/".join(
                    [
                        "items",
                        *parts[: ancestors.index(group) + 1],
                    ]
                )
                + ".md"
            )

    parts.append(index.slug(node.title) + ".md")

    return "/".join(["items", *parts])


def _group_path(index, node):
    ancestors = [index.nodes[key] for key in node.group_ancestors]

    parts = [index.slug(group.title) for group in ancestors]

    parts.append(index.slug(node.title) + ".md")

    return "/".join(["items", *parts])


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
    index,
    node,
    docs,
    source,
    populated,
):
    return _relative_link(
        docs
        / _category_path(
            index,
            node,
            populated,
        ),
        docs / source,
    )


def _group_tree(
    index,
    node,
    populated,
    docs,
    source,
    indent=0,
):
    lines: list[str] = []

    children = sorted(
        (
            child
            for child in index.children(
                node,
                categories_only=False,
            )
            if populated.get(
                child.key,
                (child.key,) if not child.is_group else (),
            )
        ),
        key=lambda child: child.title.casefold(),
    )

    prefix = "  " * indent

    for child in children:
        if child.is_group:
            categories = populated.get(
                child.key,
                (),
            )

            if not categories:
                continue

            if len(categories) == 1:
                category_node = index.nodes[categories[0]]

                link = _category_link(
                    index,
                    category_node,
                    docs,
                    source,
                    populated,
                )

                lines.append(f"{prefix}- [{child.title}]({link})")
            else:
                lines.append(f"{prefix}- {child.title}")

                lines.extend(
                    _group_tree(
                        index,
                        child,
                        populated,
                        docs,
                        source,
                        indent + 1,
                    )
                )
        else:
            link = _category_link(
                index,
                child,
                docs,
                source,
                populated,
            )

            lines.append(f"{prefix}- [{child.title}]({link})")

    return lines


def _write_category_pages(
    index,
    by_category,
    populated,
    docs,
    icon_index,
    icon_out,
):
    pages: list[dict] = []

    roots = {node.key: node for node in index.roots() if node.is_group}

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
            populated,
        )

        ancestors = [index.nodes[key] for key in node.group_ancestors]

        parent = None
        parent_path = None

        if ancestors:
            root_group = ancestors[0]

            if (
                root_group.key in roots
                and len(
                    populated.get(
                        root_group.key,
                        (),
                    )
                )
                != 1
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
    index,
    populated,
    docs,
):
    pages: list[dict] = []

    groups = sorted(
        (
            node
            for node in index.roots()
            if (
                node.is_group
                and len(
                    populated.get(
                        node.key,
                        (),
                    )
                )
                > 1
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
            populated,
            docs,
            output,
        )

        markdown.write_tree_page(
            output,
            node.title,
            tree,
        )

        relative = output.relative_to(docs).as_posix()

        print(f"\tGENERATED {relative} ({len(populated[node.key])} categories)")

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

    populated = {
        node.key: tuple(
            key for key in node.descendant_categories if by_category.get(key)
        )
        for node in index.nodes.values()
        if node.is_group
    }

    category_pages = _write_category_pages(
        index,
        by_category,
        populated,
        docs,
        icon_index,
        icon_out,
    )

    group_pages = _write_group_pages(
        index,
        populated,
        docs,
    )

    category_by_node = {page["node"].key: page for page in category_pages}

    group_by_node = {page["node"].key: page for page in group_pages}

    pages: list[dict] = []

    for node in index.roots():
        if node.is_group:
            populated_categories = populated.get(
                node.key,
                (),
            )

            if not populated_categories:
                continue

            if len(populated_categories) > 1:
                page = group_by_node.get(node.key)
            else:
                category_node = index.nodes[populated_categories[0]]

                page = {
                    "title": node.title,
                    "slug": _category_path(
                        index,
                        category_node,
                        populated,
                    ).removesuffix(".md"),
                }
        else:
            page = category_by_node.get(node.key)

        if page:
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
