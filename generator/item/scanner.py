from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..discover import discover_json
from .category import CategoryIndex
from .model import Item

ITEMS_ROOT = Path("Bellwright") / "Content" / "Mist" / "Data" / "Items"

IGNORED_ITEM_FOLDERS = frozenset(
    {
        "BrokenItems",
    }
)


def load_objects(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]

    return [raw] if isinstance(raw, dict) else []


def find_cdo(objects: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (o for o in objects if isinstance(o.get("Properties"), dict)),
        None,
    )


def load_cdo(path: Path) -> dict[str, Any]:
    return find_cdo(load_objects(path)) or {}


def load_properties(path: Path) -> dict[str, Any]:
    properties = load_cdo(path).get("Properties")

    return properties if isinstance(properties, dict) else {}


def string_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        for key in (
            "LocalizedString",
            "SourceString",
            "Value",
            "ObjectName",
            "AssetPathName",
            "ObjectPath",
        ):
            nested = value.get(key)

            if isinstance(nested, str) and nested.strip():
                return nested.strip()

    return ""


def game_path(value: Any) -> str:
    if isinstance(value, str):
        candidates = (value,)
    elif isinstance(value, dict):
        candidates = tuple(
            nested
            for key in (
                "ObjectPath",
                "AssetPathName",
                "ObjectName",
            )
            if isinstance(nested := value.get(key), str) and nested
        )
    else:
        return ""

    for candidate in candidates:
        match = re.search(r"(/Game/[^']+)", candidate)

        if match:
            return match.group(1)

        match = re.search(r"'([^']+)'", candidate)

        if match:
            return match.group(1)

        if candidate.startswith("/Game/"):
            return candidate

    return ""


def path_from_game_object(
    assets_root: Path,
    object_path: str,
) -> Path | None:
    if not object_path.startswith("/Game/"):
        return None

    relative = object_path.removeprefix("/Game/").split(".", 1)[0]

    path = assets_root / "Bellwright" / "Content" / (relative + ".json")

    return path if path.exists() else None


def template_category(
    path: Path,
    props: dict[str, Any],
    index: CategoryIndex,
    assets_root: Path,
):
    node = index.category_for_ref(props.get("Category"))

    if node:
        return node

    current = path
    seen = set()

    while current not in seen:
        seen.add(current)

        cdo = load_cdo(current)
        current_props = cdo.get("Properties")

        if not isinstance(current_props, dict):
            return None

        node = index.category_for_ref(current_props.get("Category"))

        if node:
            return node

        next_path = path_from_game_object(
            assets_root,
            game_path(cdo.get("Template")),
        )

        if not next_path:
            return None

        current = next_path

    return None


def template_name(cdo: dict[str, Any]) -> str:
    value = cdo.get("Template")

    if isinstance(value, dict):
        value = (
            value.get("ObjectName")
            or value.get("ObjectPath")
            or value.get("AssetPathName")
        )

    if not isinstance(value, str):
        return ""

    match = re.search(r"'([^']+)'", value)
    value = match.group(1) if match else value

    return (
        value.rsplit("/", 1)[-1]
        .split(".", 1)[0]
        .removeprefix("Default__")
        .removesuffix("_C")
    )


def _is_ignored_item_path(
    path: Path,
    assets_root: Path,
) -> bool:
    items_root = assets_root / ITEMS_ROOT

    try:
        relative = path.relative_to(items_root)
    except ValueError:
        return False

    return bool(relative.parts) and relative.parts[0] in IGNORED_ITEM_FOLDERS


def discover_items(
    assets_root: Path,
    index: CategoryIndex,
) -> Iterator[Item]:
    categories_root = assets_root / ITEMS_ROOT / "Categories"

    for path in discover_json(assets_root):
        if _is_ignored_item_path(path, assets_root):
            continue

        try:
            path.relative_to(categories_root)
            continue
        except ValueError:
            pass

        cdo = load_cdo(path)
        props = cdo.get("Properties")

        if not isinstance(props, dict):
            continue

        name = string_value(props.get("Name"))

        if not name:
            continue

        node = template_category(
            path,
            props,
            index,
            assets_root,
        )

        if node is None or node.is_group:
            continue

        group = index.group_for(node)

        yield Item(
            path=path,
            template=template_name(cdo),
            category_key=node.key,
            category=node.title,
            category_group_key=group.key if group else None,
            category_group=group.title if group else None,
            name=name,
            properties=props,
        )


def reference_name(value: Any) -> str:
    reference = game_path(value)

    if reference:
        return reference.rsplit("/", 1)[-1].split(".", 1)[0].removesuffix("_C")

    return ""


def load_broken_relationships(
    assets_root: Path,
) -> dict[str, tuple[str, str]]:
    result = {}

    items_root = assets_root / ITEMS_ROOT

    for path in discover_json(assets_root):
        try:
            relative = path.relative_to(items_root)
        except ValueError:
            continue

        if not relative.parts:
            continue

        if relative.parts[0] != "BrokenItems":
            continue

        props = load_properties(path)

        damaged = reference_name(props.get("DamagedItem"))

        parent = reference_name(props.get("UnbrokenParentItem"))

        if damaged or parent:
            result[path.stem] = (
                damaged,
                parent,
            )

    return result
