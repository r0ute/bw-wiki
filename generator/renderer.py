from pathlib import Path

from generator.icon import copy_icon


def _render_group(group: dict) -> list[str]:
    """Render one generator group."""
    lines = [
        '<div class="data-group" markdown="1">',
        "",
        f"## {group['title']}",
        "",
    ]

    lines.extend(
        f"- [{page['title']}]({page['slug']})"
        for page in sorted(
            group["pages"],
            key=lambda page: page["title"].lower(),
        )
    )

    lines.extend(
        [
            "",
            "</div>",
            "",
        ]
    )

    return lines


def _render_data(page_groups: list[dict]) -> list[str]:
    """Render generator groups in a CSS grid."""
    lines = [
        '<div class="data-groups">',
        "",
    ]

    for group in page_groups:
        lines.extend(_render_group(group))

    lines.extend(
        [
            "</div>",
            "",
        ]
    )

    return lines


def write_index_page(
    output: Path,
    page_groups: list[dict],
    logo: Path,
) -> None:
    """Write the root documentation index."""
    output.parent.mkdir(parents=True, exist_ok=True)

    copy_icon(
        logo,
        output.parent / "assets",
    )

    version = (
        (output.parent.parent / "assets" / "version")
        .read_text(encoding="utf-8")
        .strip()
    )

    lines = [
        "---",
        "layout: default",
        "title: Bellwright Wiki & Guide",
        "---",
        '<div class="logo"></div>',
        "",
        "# Bellwright Wiki & Guide",
        "",
        "A searchable **Bellwright wiki and database** with quests, items, "
        "NPCs, rewards, recipes, resources, crafting, locations, guides, "
        "and other game data.",
        "",
        f"![Game Version](https://img.shields.io/badge/Game%20Version-{version}-black?logo=unrealengine)",
        "[![GitHub](https://img.shields.io/badge/Source%20Code-GitHub-black?logo=github)](https://github.com/r0ute/bw-wiki)",
        *_render_data(page_groups),
    ]

    output.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
