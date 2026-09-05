"""Render quest documentation to Markdown."""

import json
from pathlib import Path

from ..navigation import breadcrumb_include, navigation_metadata
from .model import Quest, QuestItem, QuestNode, QuestReward, QuestStep


def _format_items(items: tuple[QuestItem, ...]) -> str:
    values = []

    for item in items:
        if item.min_amount == item.max_amount:
            amount = str(item.min_amount)
        else:
            amount = f"{item.min_amount}-{item.max_amount}"

        values.append(f"{item.name} x {amount}")

    return "<br>".join(values)


def _format_reward(reward: QuestReward) -> str:
    value = reward.name

    if reward.min_amount is not None and reward.max_amount is not None:
        if reward.min_amount == reward.max_amount:
            amount = str(reward.min_amount)
        else:
            amount = f"{reward.min_amount}-{reward.max_amount}"

        value = f"{value} x {amount}"

    if reward.chance is not None:
        chance = f"{reward.chance * 100:g}%"

        if reward.per_roll:
            chance += "/roll"

        value = f"{value} ({chance})"

    return value


def _format_rewards(
    rewards: tuple[QuestReward, ...],
) -> tuple[list[str], list[str]]:
    guaranteed = []
    random = []

    for reward in rewards:
        value = _format_reward(reward)

        if reward.chance is None:
            guaranteed.append(value)
        else:
            random.append(value)

    return guaranteed, random


def _write_quest_info(
    lines: list[str],
    quest: Quest,
) -> None:
    if quest.summary:
        lines.extend(
            [
                quest.summary,
                "",
            ]
        )

    guaranteed = []

    if quest.village_trust_reward > 0:
        guaranteed.append(f"Village Trust x {quest.village_trust_reward}")

    if quest.money_reward > 0:
        guaranteed.append(f"Money x {quest.money_reward}")

    if quest.renown_reward > 0:
        guaranteed.append(f"Renown x {quest.renown_reward}")

    reward_guaranteed, random = _format_rewards(quest.rewards)
    guaranteed.extend(reward_guaranteed)

    if not quest.giver and not quest.npcs and not guaranteed and not random:
        return

    lines.extend(
        [
            "| Giver | NPCs | Rewards | Random Rewards |",
            "|---|---|---|---|",
            (
                f"| {quest.giver} | {'<br>'.join(quest.npcs)} | "
                f"{'<br>'.join(guaranteed)} | {'<br>'.join(random)} |"
            ),
            "",
        ]
    )


def _write_step_row(
    lines: list[str],
    number: str,
    step: QuestStep,
) -> None:
    lines.append(
        f"| {number} | {step.name} | {step.summary or ''} | "
        f"{step.npc or ''} | {_format_items(step.items)} | "
        f"{step.completion_text or ''} |"
    )


def _write_steps(
    lines: list[str],
    steps: tuple[QuestStep, ...],
) -> None:
    lines.extend(
        [
            "## Steps",
            "",
            "| # | Step | Summary | NPC | Items to bring | Completion |",
            "|---|---|---|---|---|---|",
        ]
    )

    number = 1
    index = 0

    while index < len(steps):
        step = steps[index]

        if not step.group_next:
            _write_step_row(lines, str(number), step)
            number += 1
            index += 1
            continue

        group = [step]

        while (
            index + 1 < len(steps)
            and steps[index].group_next
            and steps[index + 1].type == step.type
        ):
            index += 1
            group.append(steps[index])

        for offset, parallel_step in enumerate(group, start=1):
            _write_step_row(
                lines,
                f"{number}.{offset}",
                parallel_step,
            )

        number += 1
        index += 1

    lines.append("")


def _write_front_matter(
    lines: list[str],
    title: str,
    parent: str | None = None,
    parent_url: str | None = None,
    grand_parent: str | None = None,
    grand_parent_url: str | None = None,
) -> None:
    lines.extend(
        [
            "---",
            "layout: default",
            f"title: {json.dumps(title)}",
            *navigation_metadata(
                parent=parent,
                parent_path=parent_url,
                grand_parent=grand_parent,
                grand_parent_path=grand_parent_url,
            ),
            "---",
            "",
            *breadcrumb_include(),
        ]
    )


def _write_quest_page(
    path: Path,
    quest: Quest,
    parent: str,
    parent_url: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    _write_front_matter(
        lines,
        quest.title,
        parent=parent,
        parent_url=parent_url,
    )

    lines.extend(
        [
            f"# {quest.title}",
            "",
        ]
    )

    _write_quest_info(lines, quest)

    if quest.steps:
        _write_steps(lines, quest.steps)

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _write_page(
    path: Path,
    title: str,
    lines: list[str],
    parent: str | None = None,
    parent_url: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    content: list[str] = []

    _write_front_matter(
        content,
        title,
        parent=parent,
        parent_url=parent_url,
    )

    content.extend(
        [
            f"# {title}",
            "",
            *lines,
            "",
        ]
    )

    path.write_text(
        "\n".join(content),
        encoding="utf-8",
    )


def _write_directory(
    node: QuestNode,
    directory: Path,
    category: str,
    category_url: str,
) -> None:
    """Write quest pages while using tree nodes as directories."""
    if node.quest is not None:
        _write_quest_page(
            directory.with_suffix(".md"),
            node.quest,
            parent=category,
            parent_url=category_url,
        )

    if not node.children:
        return

    directory.mkdir(parents=True, exist_ok=True)

    for key, child in sorted(
        node.children.items(),
        key=lambda item: item[1].name.casefold(),
    ):
        _write_directory(
            child,
            directory / key,
            category,
            category_url,
        )


def _write_tree(
    lines: list[str],
    node: QuestNode,
    prefix: str = "",
    indent: int = 0,
) -> None:
    for key, child in sorted(
        node.children.items(),
        key=lambda item: item[1].name.casefold(),
    ):
        padding = "  " * indent

        if child.quest is not None:
            lines.append(f"{padding}- [{child.name}]({prefix}{key})")
            continue

        lines.append(f"{padding}- {child.name}")

        _write_tree(
            lines,
            child,
            f"{prefix}{key}/",
            indent + 1,
        )


def write_category(
    docs: Path,
    category_slug: str,
    tree: QuestNode,
) -> None:
    """Write a quest category."""
    directory = docs / category_slug
    category_url = f"/quests/{category_slug}"

    _write_directory(
        tree,
        directory,
        category=tree.name,
        category_url=category_url,
    )

    index_lines: list[str] = []

    _write_tree(
        index_lines,
        tree,
        f"{category_slug}/",
    )

    _write_page(
        docs / f"{category_slug}.md",
        tree.name,
        index_lines,
    )
