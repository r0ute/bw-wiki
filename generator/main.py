from pathlib import Path

from . import icon, renderer
from .item import generator as item_generator
from .quest import generator as quest_generator

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ASSETS = ROOT / "assets"
ICON_OUT = DOCS / "assets" / "icons"


def clean_output() -> None:
    """Remove generated documentation and assets."""
    DOCS.mkdir(parents=True, exist_ok=True)

    for path in DOCS.rglob("*.md"):
        path.unlink()

    if ICON_OUT.exists():
        for path in ICON_OUT.iterdir():
            if path.is_file():
                path.unlink()


def main() -> None:
    clean_output()
    icon_index = icon.build_icon_index(ASSETS)

    icon.copy_icon(
        ASSETS / "favicon.ico",
        ICON_OUT,
    )

    generators = (
        item_generator.generate,
        quest_generator.generate,
    )

    page_groups = [
        generator(ASSETS, DOCS, ICON_OUT, icon_index) for generator in generators
    ]

    renderer.write_index_page(
        DOCS / "index.md",
        page_groups,
        ASSETS / "T_Logo.webp",
    )


if __name__ == "__main__":
    main()
