from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Item:
    path: Path
    template: str
    category_key: str
    category: str
    category_group_key: str | None
    category_group: str | None
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    damaged_item: str = ""
    unbroken_parent: str = ""

    @property
    def stem(self) -> str:
        return self.path.stem
