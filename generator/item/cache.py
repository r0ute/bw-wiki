from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..discover import discover_json

ITEMS_ROOT = Path("Bellwright") / "Content" / "Mist" / "Data" / "Items"

IGNORED_ITEM_FOLDERS = frozenset({"BrokenItems"})


class AssetCache:
    """Discover JSON assets once and cache parsed asset data."""

    def __init__(self, assets_root: Path):
        self.assets_root = assets_root
        self.items_root = assets_root / ITEMS_ROOT
        self.categories_root = self.items_root / "Categories"
        self.paths = tuple(discover_json(assets_root))

        self._objects: dict[Path, list[dict[str, Any]]] = {}
        self._template_paths: dict[Path, Path | None] = {}

    def objects(self, path: Path) -> list[dict[str, Any]]:
        if path not in self._objects:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                objects: list[dict[str, Any]] = []
            else:
                if isinstance(raw, list):
                    objects = [value for value in raw if isinstance(value, dict)]
                elif isinstance(raw, dict):
                    objects = [raw]
                else:
                    objects = []

            self._objects[path] = objects

        return self._objects[path]

    def cdo(self, path: Path) -> dict[str, Any]:
        return next(
            (
                obj
                for obj in self.objects(path)
                if isinstance(obj.get("Properties"), dict)
            ),
            {},
        )

    def properties(self, path: Path) -> dict[str, Any]:
        properties = self.cdo(path).get("Properties")

        return properties if isinstance(properties, dict) else {}

    def game_object(self, object_path: str) -> Path | None:
        if not object_path.startswith("/Game/"):
            return None

        relative = object_path.removeprefix("/Game/").split(".", 1)[0]

        path = self.assets_root / "Bellwright" / "Content" / (relative + ".json")

        return path if path.exists() else None

    def template_path(self, path: Path) -> Path | None:
        if path in self._template_paths:
            return self._template_paths[path]

        template = self.cdo(path).get("Template")
        object_path = game_path(template)

        result = self.game_object(object_path) if object_path else None

        self._template_paths[path] = result

        return result

    def item_paths(self):
        for path in self.paths:
            try:
                relative = path.relative_to(self.items_root)
            except ValueError:
                continue

            if not relative.parts or relative.parts[0] in IGNORED_ITEM_FOLDERS:
                continue

            try:
                path.relative_to(self.categories_root)
            except ValueError:
                yield path

    def broken_item_paths(self):
        for path in self.paths:
            try:
                relative = path.relative_to(self.items_root)
            except ValueError:
                continue

            if relative.parts and relative.parts[0] == "BrokenItems":
                yield path


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
            if isinstance(
                nested := value.get(key),
                str,
            )
            and nested
        )
    else:
        return ""

    for candidate in candidates:
        match = re.search(
            r"(/Game/[^']+)",
            candidate,
        )

        if match:
            return match.group(1)

        match = re.search(
            r"'([^']+)'",
            candidate,
        )

        if match:
            return match.group(1)

        if candidate.startswith("/Game/"):
            return candidate

    return ""


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


def reference_name(value: Any) -> str:
    reference = game_path(value)

    if reference:
        return reference.rsplit("/", 1)[-1].split(".", 1)[0].removesuffix("_C")

    return ""
