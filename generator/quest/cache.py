"""Cached quest asset discovery and JSON parsing."""

from pathlib import Path

from .parser import ObjectIndex
from .reader import read_objects

QUEST_ROOT = Path("Bellwright/Content/Mist/Data/Quests")


class QuestCache:
    """Discover and cache quest JSON objects."""

    def __init__(self, assets: Path) -> None:
        self.assets = assets
        self.root = assets / QUEST_ROOT
        self._objects: dict[Path, list[dict]] = {}
        self._paths: tuple[Path, ...] | None = None
        self._directory_indexes: dict[Path, ObjectIndex] | None = None

    def paths(self) -> tuple[Path, ...]:
        """Return all quest JSON paths."""
        if self._paths is None:
            if not self.root.is_dir():
                self._paths = ()
            else:
                self._paths = tuple(
                    path for path in self.root.rglob("*.json") if path.is_file()
                )

        return self._paths

    def objects(self, path: Path) -> list[dict]:
        """Return parsed objects for a quest JSON file."""
        objects = self._objects.get(path)

        if objects is None:
            objects = read_objects(path)
            self._objects[path] = objects

        return objects

    def directory_indexes(self) -> dict[Path, ObjectIndex]:
        """Build directory object indexes from cached JSON objects."""
        if self._directory_indexes is not None:
            return self._directory_indexes

        indexes: dict[Path, ObjectIndex] = {}

        for path in self.paths():
            objects = self.objects(path)

            for obj in objects:
                value = obj.get("Name")

                if not isinstance(value, str):
                    continue

                name = value.strip()

                if not name or name.startswith("Default__"):
                    continue

                if name.endswith("_C"):
                    name = name[:-2]

                name = name.strip()

                if not name:
                    continue

                indexes.setdefault(path.parent, {})[name] = (
                    path,
                    objects,
                )
                break

        self._directory_indexes = indexes

        return indexes
