from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cache import AssetCache

CATEGORY_CLASSES = frozenset(
    {
        "MistItemCategory",
        "MistItemCategory_C",
    }
)

CATEGORY_GROUP_CLASSES = frozenset(
    {
        "MistItemCategoryGroup",
        "MistItemCategoryGroup_C",
    }
)

CATEGORIES_GAME_PATH = "/Game/Mist/Data/Items/Categories/"


@dataclass(slots=True)
class CategoryNode:
    key: str
    class_name: str
    title: str
    path: Path
    parent_key: str | None
    is_group: bool
    children: list[str] = field(default_factory=list)
    descendant_categories: tuple[str, ...] = ()
    group_ancestors: tuple[str, ...] = ()


class CategoryIndex:
    def __init__(self, nodes: dict[str, CategoryNode]):
        self.nodes = nodes
        self.by_class: dict[str, list[str]] = {}
        self._roots: tuple[str, ...] = ()

        for key, node in nodes.items():
            self.by_class.setdefault(
                normalize_key(node.class_name),
                [],
            ).append(key)

        self._prepare_hierarchy()

    @classmethod
    def from_assets(
        cls,
        assets: AssetCache,
    ) -> "CategoryIndex":
        pending: list[
            tuple[
                Path,
                str,
                str,
                str | None,
                bool,
                str,
            ]
        ] = []

        for path in assets.paths:
            try:
                path.relative_to(assets.categories_root)
            except ValueError:
                continue

            objects = assets.objects(path)

            class_obj = next(
                (
                    obj
                    for obj in objects
                    if superstruct(obj) in (CATEGORY_CLASSES | CATEGORY_GROUP_CLASSES)
                ),
                None,
            )

            if class_obj is None:
                continue

            cdo = next(
                (
                    obj
                    for obj in objects
                    if isinstance(
                        obj.get("Properties"),
                        dict,
                    )
                ),
                None,
            )

            asset_path = asset_path_for(class_obj) or asset_path_for(cdo or {})

            title = name_for(cdo or {})

            if not asset_path or not title:
                continue

            class_name = str(class_obj.get("Name") or "").removesuffix("_C")

            parent_path = parent_for(cdo or {})
            is_group = superstruct(class_obj) in CATEGORY_GROUP_CLASSES

            pending.append(
                (
                    path,
                    asset_path,
                    class_name,
                    parent_path,
                    is_group,
                    title,
                )
            )

        keys = {asset_path for _, asset_path, _, _, _, _ in pending}

        nodes = {
            key: CategoryNode(
                key=key,
                class_name=class_name,
                title=title,
                path=path,
                parent_key=(parent_path if parent_path in keys else None),
                is_group=is_group,
            )
            for (
                path,
                key,
                class_name,
                parent_path,
                is_group,
                title,
            ) in pending
        }

        for node in nodes.values():
            if node.parent_key in nodes:
                nodes[node.parent_key].children.append(node.key)

        return cls(nodes)

    def _prepare_hierarchy(self) -> None:
        self._roots = tuple(
            sorted(
                (node.key for node in self.nodes.values() if node.parent_key is None),
                key=lambda key: self.nodes[key].title.casefold(),
            )
        )

        depth: dict[str, int] = {}

        for node in self.nodes.values():
            current = node
            seen: set[str] = set()
            value = 0

            while current.parent_key and current.key not in seen:
                seen.add(current.key)
                value += 1

                current = self.nodes.get(current.parent_key)

                if current is None:
                    break

            depth[node.key] = value

        # Build descendant category lists bottom-up.
        #
        # Every category includes itself, and also inherits
        # descendant categories from child nodes. Groups only
        # inherit their children's categories.
        for node in sorted(
            self.nodes.values(),
            key=lambda value: depth[value.key],
            reverse=True,
        ):
            descendants: list[str] = []

            if not node.is_group:
                descendants.append(node.key)

            for child_key in node.children:
                descendants.extend(self.nodes[child_key].descendant_categories)

            node.descendant_categories = tuple(descendants)

        for node in self.nodes.values():
            ancestors: list[str] = []
            current = self.nodes.get(node.parent_key) if node.parent_key else None
            seen: set[str] = set()

            while current and current.key not in seen:
                seen.add(current.key)

                if current.is_group:
                    ancestors.append(current.key)

                current = (
                    self.nodes.get(current.parent_key) if current.parent_key else None
                )

            ancestors.reverse()
            node.group_ancestors = tuple(ancestors)

    def resolve_ref(
        self,
        value: Any,
    ) -> CategoryNode | None:
        ref = reference(value)

        if not ref:
            return None

        if ref.startswith(CATEGORIES_GAME_PATH):
            node = self.nodes.get(ref)

            if node:
                return node

        matches = self.by_class.get(
            normalize_key(ref.rsplit("/", 1)[-1]),
            [],
        )

        return self.nodes[matches[0]] if len(matches) == 1 else None

    def group_for(
        self,
        node: CategoryNode | None,
    ) -> CategoryNode | None:
        if not node:
            return None

        for key in reversed(node.group_ancestors):
            return self.nodes[key]

        return node if node.is_group else None

    def children(
        self,
        node: CategoryNode,
        categories_only: bool = True,
    ) -> list[CategoryNode]:
        children = sorted(
            (self.nodes[key] for key in node.children),
            key=lambda child: child.title.casefold(),
        )

        return [
            child for child in children if (not categories_only or not child.is_group)
        ]

    def roots(self) -> list[CategoryNode]:
        return [self.nodes[key] for key in self._roots]

    @staticmethod
    def slug(title: str) -> str:
        return (
            re.sub(
                r"[^a-z0-9]+",
                "-",
                title.lower(),
            ).strip("-")
            or "category"
        )


def reference(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None

    for key in (
        "ObjectPath",
        "AssetPathName",
        "ObjectName",
    ):
        raw = value.get(key)

        if not isinstance(raw, str) or not raw:
            continue

        if raw.startswith("/Game/"):
            return raw.split(".", 1)[0]

        match = re.search(
            r"'([^']+)'",
            raw,
        )

        if match:
            return match.group(1)

    return None


def superstruct(
    obj: dict[str, Any],
) -> str:
    ref = reference(obj.get("SuperStruct"))

    return ref.rsplit("/", 1)[-1] if ref else ""


def name_for(
    obj: dict[str, Any],
) -> str | None:
    properties = obj.get("Properties")

    if not isinstance(properties, dict):
        return None

    value = properties.get("Name")

    if isinstance(value, dict):
        value = value.get("LocalizedString") or value.get("SourceString")

    return value.strip() if isinstance(value, str) and value.strip() else None


def parent_for(
    obj: dict[str, Any],
) -> str | None:
    properties = obj.get("Properties")

    return reference(properties.get("Parent")) if isinstance(properties, dict) else None


def asset_path_for(
    obj: dict[str, Any],
) -> str | None:
    package = obj.get("Package")

    if isinstance(package, str) and package.startswith("/Game/"):
        return package

    class_default_object = obj.get("ClassDefaultObject")

    return (
        reference(class_default_object)
        if isinstance(
            class_default_object,
            dict,
        )
        else None
    )


def normalize_key(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]",
        "",
        value.lower().removesuffix("_c"),
    )
