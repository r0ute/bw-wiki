from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from .cache import (
    AssetCache,
    reference_name,
    string_value,
)
from .category import CategoryIndex
from .model import Item


def template_name(
    cdo: dict[str, Any],
) -> str:
    value = cdo.get("Template")

    if isinstance(value, dict):
        value = (
            value.get("ObjectName")
            or value.get("ObjectPath")
            or value.get("AssetPathName")
        )

    if not isinstance(value, str):
        return ""

    match = re.search(
        r"'([^']+)'",
        value,
    )

    value = match.group(1) if match else value

    return (
        value.rsplit("/", 1)[-1]
        .split(".", 1)[0]
        .removeprefix("Default__")
        .removesuffix("_C")
    )


def discover_items(
    assets: AssetCache,
    index: CategoryIndex,
) -> Iterator[Item]:
    for path in assets.item_paths():
        cdo = assets.cdo(path)
        props = cdo.get("Properties")

        if not isinstance(props, dict):
            continue

        name = string_value(props.get("Name"))

        if not name:
            continue

        node = index.resolve_ref(props.get("Category"))

        if node is None:
            current = path
            seen: set = set()

            while current not in seen:
                seen.add(current)

                current_cdo = assets.cdo(current)
                current_props = current_cdo.get("Properties")

                if not isinstance(
                    current_props,
                    dict,
                ):
                    break

                node = index.resolve_ref(current_props.get("Category"))

                if node:
                    break

                current = assets.template_path(current)

                if current is None:
                    break

        if node is None or node.is_group:
            continue

        group = index.group_for(node)

        yield Item(
            path=path,
            template=template_name(cdo),
            category_key=node.key,
            category=node.title,
            category_group_key=(group.key if group else None),
            category_group=(group.title if group else None),
            name=name,
            properties=props,
        )


def load_broken_relationships(
    assets: AssetCache,
) -> dict[str, tuple[str, str]]:
    result: dict[
        str,
        tuple[str, str],
    ] = {}

    for path in assets.broken_item_paths():
        props = assets.properties(path)

        damaged = reference_name(props.get("DamagedItem"))
        parent = reference_name(props.get("UnbrokenParentItem"))

        if damaged or parent:
            result[path.stem] = (
                damaged,
                parent,
            )

    return result
