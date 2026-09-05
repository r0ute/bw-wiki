from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..discover import discover_json

CATEGORY_CLASSES = frozenset({"MistItemCategory", "MistItemCategory_C"})
CATEGORY_GROUP_CLASSES = frozenset({"MistItemCategoryGroup", "MistItemCategoryGroup_C"})

CATEGORIES_GAME_PATH = "/Game/Mist/Data/Items/Categories/"


def _objects(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if isinstance(raw, list):
        return [value for value in raw if isinstance(value, dict)]

    return [raw] if isinstance(raw, dict) else []


def _reference(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None

    for key in ("ObjectPath", "AssetPathName", "ObjectName"):
        raw = value.get(key)
        if not isinstance(raw, str) or not raw:
            continue

        if raw.startswith("/Game/"):
            return raw.split(".", 1)[0]

        match = re.search(r"'([^']+)'", raw)
        if match:
            return match.group(1)

    return None


def _superstruct(obj: dict[str, Any]) -> str:
    ref = _reference(obj.get("SuperStruct"))
    if not ref:
        return ""

    return ref.rsplit("/", 1)[-1]


def _name(obj: dict[str, Any]) -> str | None:
    properties = obj.get("Properties")
    if not isinstance(properties, dict):
        return None

    value = properties.get("Name")

    if isinstance(value, dict):
        value = value.get("LocalizedString") or value.get("SourceString")

    return value.strip() if isinstance(value, str) and value.strip() else None


def _package_path(obj: dict[str, Any]) -> str | None:
    value = obj.get("Package")
    return value if isinstance(value, str) and value.startswith("/Game/") else None


def _parent(obj: dict[str, Any]) -> str | None:
    properties = obj.get("Properties")
    if not isinstance(properties, dict):
        return None

    return _reference(properties.get("Parent"))


def _asset_path(obj: dict[str, Any]) -> str | None:
    package = _package_path(obj)
    if package:
        return package

    class_default_object = obj.get("ClassDefaultObject")
    if isinstance(class_default_object, dict):
        return _reference(class_default_object)

    return None


def _game_path(path: Path, assets_root: Path) -> str | None:
    try:
        relative = path.relative_to(assets_root)
    except ValueError:
        return None

    parts = relative.parts

    if len(parts) < 3 or parts[0] != "Bellwright" or parts[1] != "Content":
        return None

    return "/Game/" + "/".join(parts[2:]).rsplit(".", 1)[0]


def _category_asset(path: Path, assets_root: Path) -> bool:
    game_path = _game_path(path, assets_root)
    return bool(game_path and game_path.startswith(CATEGORIES_GAME_PATH))


@dataclass(slots=True)
class CategoryNode:
    key: str
    class_name: str
    title: str
    path: Path
    parent_key: str | None
    is_group: bool
    children: list[str] = field(default_factory=list)


class CategoryIndex:
    def __init__(self, nodes: dict[str, CategoryNode]):
        self.nodes = nodes
        self.by_class: dict[str, list[str]] = {}

        for key, node in nodes.items():
            normalized = normalize_key(node.class_name)
            self.by_class.setdefault(normalized, []).append(key)

    @classmethod
    def from_assets(cls, assets_root: Path) -> "CategoryIndex":
        nodes: dict[str, CategoryNode] = {}
        pending: list[tuple[Path, str, str, str | None, bool]] = []

        for path in discover_json(assets_root):
            if not _category_asset(path, assets_root):
                continue

            objects = _objects(path)

            class_obj = next(
                (
                    obj
                    for obj in objects
                    if _superstruct(obj) in CATEGORY_CLASSES | CATEGORY_GROUP_CLASSES
                ),
                None,
            )

            if class_obj is None:
                continue

            superstruct = _superstruct(class_obj)
            is_group = superstruct in CATEGORY_GROUP_CLASSES

            cdo = next(
                (obj for obj in objects if isinstance(obj.get("Properties"), dict)),
                None,
            )

            asset_path = _asset_path(class_obj)
            if not asset_path:
                asset_path = _asset_path(cdo or {})

            if not asset_path:
                continue

            title = _name(cdo or {})
            if not title:
                continue

            class_name = str(class_obj.get("Name") or "").removesuffix("_C")
            parent_path = _parent(cdo or {})

            pending.append(
                (
                    path,
                    asset_path,
                    class_name,
                    parent_path,
                    is_group,
                )
            )

        path_to_key = {asset_path: asset_path for _, asset_path, _, _, _ in pending}

        for path, key, class_name, parent_path, is_group in pending:
            objects = _objects(path)

            cdo = next(
                (obj for obj in objects if isinstance(obj.get("Properties"), dict)),
                {},
            )

            parent_key = path_to_key.get(parent_path)

            nodes[key] = CategoryNode(
                key=key,
                class_name=class_name,
                title=_name(cdo) or "",
                path=path,
                parent_key=parent_key,
                is_group=is_group,
            )

        for node in nodes.values():
            if node.parent_key in nodes:
                nodes[node.parent_key].children.append(node.key)

        return cls(nodes)

    def resolve_ref(self, value: Any) -> CategoryNode | None:
        ref = _reference(value)
        if not ref:
            return None

        if ref.startswith(CATEGORIES_GAME_PATH):
            node = self.nodes.get(ref)
            if node:
                return node

        key = ref.rsplit("/", 1)[-1]
        matches = self.by_class.get(normalize_key(key), [])

        if len(matches) == 1:
            return self.nodes[matches[0]]

        return None

    def category_for_ref(self, value: Any) -> CategoryNode | None:
        return self.resolve_ref(value)

    def group_for(self, node: CategoryNode | None) -> CategoryNode | None:
        seen: set[str] = set()

        while node and node.key not in seen:
            seen.add(node.key)

            if node.is_group:
                return node

            node = self.nodes.get(node.parent_key) if node.parent_key else None

        return None

    def children(
        self,
        node: CategoryNode,
        categories_only: bool = True,
    ) -> list[CategoryNode]:
        result = []

        for key in sorted(
            node.children,
            key=lambda value: self.nodes[value].title.lower(),
        ):
            child = self.nodes[key]

            if not categories_only or not child.is_group:
                result.append(child)

        return result

    def roots(self) -> list[CategoryNode]:
        return sorted(
            (node for node in self.nodes.values() if node.parent_key is None),
            key=lambda node: node.title.lower(),
        )

    @staticmethod
    def slug(title: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "category"


def build_category_index(assets_root: Path) -> CategoryIndex:
    return CategoryIndex.from_assets(assets_root)


def category_slug(value: str) -> str:
    return CategoryIndex.slug(value)


def normalize_key(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]",
        "",
        value.lower().removesuffix("_c"),
    )


def normalize_category_key(value: str) -> str:
    return normalize_key(value)
