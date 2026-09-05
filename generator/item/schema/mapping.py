from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from pkgutil import iter_modules
from typing import Any

CATEGORY_SCHEMAS = {
    "Weapons": "weapons",
    "OneHanded": "weapons",
    "Two-handed": "weapons",
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


def _category_schema(category_node: Any) -> str | None:
    names = (
        str(getattr(category_node, "class_name", "") or ""),
        str(getattr(category_node, "title", "") or ""),
    )

    normalized_names = tuple(_normalize(name) for name in names if name)

    for schema_name in _SCHEMA_NAMES:
        normalized_schema = _normalize(schema_name)

        if any(normalized_schema in name for name in normalized_names):
            return schema_name

    class_name = str(getattr(category_node, "class_name", "") or "")
    return CATEGORY_SCHEMAS.get(class_name)


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
    print(f"\t\tWARNING: using default item schema for category '{category}'")


def schema_module(
    index: Any,
    category_node: Any,
    template: str,
):
    module_name = _category_schema(category_node)

    if module_name:
        module_path = f"{_SCHEMA_PACKAGE}.{module_name}"

        if _schema_exists(module_path):
            return import_module(module_path)

    _warn_default(category_node)
    return import_module(_DEFAULT_SCHEMA)
