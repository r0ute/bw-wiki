from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from pkgutil import iter_modules
from typing import Any

CATEGORY_SCHEMA_OVERRIDES = {
    "Decorations": "minimal",
    "Equipment": "minimal",
    "Knowledge Books": "minimal",
    "Medicine": "minimal",
    "Liquids": "minimal",
    "Other": "minimal",
    "Resources": "minimal",
    "Quest Item": "minimal",
    "Seeds": "minimal",
}

_SCHEMA_PACKAGE = "generator.item.schema"
_SCHEMA_EXCLUDED = frozenset({"common", "default", "mapping"})
_DEFAULT_SCHEMA = f"{_SCHEMA_PACKAGE}.default"

_WARNED_DEFAULTS: set[str] = set()


def _normalize(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _schema_names() -> tuple[str, ...]:
    spec = find_spec(_SCHEMA_PACKAGE)

    if spec is None or not spec.submodule_search_locations:
        return ()

    names = {
        module.name
        for module in iter_modules(spec.submodule_search_locations)
        if module.name not in _SCHEMA_EXCLUDED
    }

    return tuple(
        sorted(
            names,
            key=lambda name: (-len(_normalize(name)), name),
        )
    )


_SCHEMA_NAMES = _schema_names()


def _category_names(index: Any, category_node: Any) -> tuple[str, ...]:
    names = [
        str(getattr(category_node, "class_name", "") or ""),
        str(getattr(category_node, "title", "") or ""),
    ]

    for group_key in getattr(category_node, "group_ancestors", ()):
        group = getattr(index, "nodes", {}).get(group_key)

        if group is None:
            continue

        names.extend(
            (
                str(getattr(group, "class_name", "") or ""),
                str(getattr(group, "title", "") or ""),
            )
        )

    return tuple(_normalize(name) for name in names if name)


def _autodiscovered_schema(
    index: Any,
    category_node: Any,
) -> str | None:
    names = _category_names(index, category_node)

    for schema_name in _SCHEMA_NAMES:
        normalized_schema = _normalize(schema_name)

        if any(normalized_schema in name for name in names):
            return schema_name

    return None


def _schema_exists(module_name: str) -> bool:
    return find_spec(module_name) is not None


def _warn_default(category_node: Any) -> None:
    category = (
        str(getattr(category_node, "title", "") or "")
        or str(getattr(category_node, "class_name", "") or "")
        or "<unknown>"
    )

    if category in _WARNED_DEFAULTS:
        return

    _WARNED_DEFAULTS.add(category)
    print(f"\tWARNING: using default item schema for category '{category}'")


def schema_module(
    index: Any,
    category_node: Any,
    template: str,
):
    module_name = _autodiscovered_schema(
        index,
        category_node,
    )

    if module_name is None:
        class_name = str(getattr(category_node, "class_name", "") or "")
        module_name = CATEGORY_SCHEMA_OVERRIDES.get(class_name)

    if module_name:
        module_path = f"{_SCHEMA_PACKAGE}.{module_name}"

        if _schema_exists(module_path):
            return import_module(module_path)

    _warn_default(category_node)
    return import_module(_DEFAULT_SCHEMA)
