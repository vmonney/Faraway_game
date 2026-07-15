"""Endgame scoring for Faraway tableaux."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from faraway.domain.cards import Catalog, RegionCard, SanctuaryCard

TOTAL_KEYS = (
    "stone",
    "chimera",
    "thistle",
    "clue",
    "red",
    "green",
    "blue",
    "yellow",
    "colorless",
    "night",
    "wonderSet",
    "colorSet",
)


@dataclass(slots=True)
class Totals:
    values: dict[str, int]

    @classmethod
    def empty(cls) -> Totals:
        return cls(values={key: 0 for key in TOTAL_KEYS})

    def add_card(self, card: RegionCard | SanctuaryCard) -> None:
        if card.wonders:
            for wonder, count in card.wonders.items():
                self.values[wonder] += count
        if card.clue:
            self.values["clue"] += 1
        self.values[card.biome] += 1
        if card.night:
            self.values["night"] += 1
        self.refresh_sets()

    def refresh_sets(self) -> None:
        self.values["wonderSet"] = min(
            self.values["stone"],
            self.values["chimera"],
            self.values["thistle"],
        )
        self.values["colorSet"] = min(
            self.values["red"],
            self.values["green"],
            self.values["blue"],
            self.values["yellow"],
        )


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    region_scores: list[int]
    sanctuary_score: int
    total: int
    duration_sum: int


def check_quest(totals: Totals, quest: dict[str, int] | None) -> bool:
    if not quest:
        return True
    return all(totals.values.get(key, 0) >= needed for key, needed in quest.items())


def fame_points(fame: int | dict[str, Any] | None, totals: Totals) -> int:
    if fame is None:
        return 0
    if isinstance(fame, int):
        return fame
    per = fame["per"]
    score = int(fame["score"])
    if isinstance(per, str):
        return totals.values[per] * score
    if isinstance(per, dict):
        # Biome combo: points per matching region of either color (not per pair).
        return sum(totals.values[per[key]] * score for key in ("region1", "region2"))
    raise ValueError(f"Unsupported fame: {fame}")


def score_tableau(
    catalog: Catalog,
    region_numbers: list[int],
    sanctuary_tiles: list[int],
) -> ScoreBreakdown:
    if len(region_numbers) != 8:
        raise ValueError("Scoring requires exactly 8 region cards")

    totals = Totals.empty()
    for tile in sanctuary_tiles:
        totals.add_card(catalog.sanctuary(tile))

    region_scores: list[int] = [0] * 8
    # Reveal right-to-left: only sanctuaries + cards at index..7 are visible.
    for index in range(7, -1, -1):
        region = catalog.region(region_numbers[index])
        totals.add_card(region)
        points = 0
        if region.fame is not None and check_quest(totals, region.quest):
            points = fame_points(region.fame, totals)
        region_scores[index] = points

    sanctuary_score = 0
    for tile in sanctuary_tiles:
        sanctuary = catalog.sanctuary(tile)
        sanctuary_score += fame_points(sanctuary.fame, totals)

    duration_sum = sum(region_numbers)
    total = sum(region_scores) + sanctuary_score
    return ScoreBreakdown(
        region_scores=region_scores,
        sanctuary_score=sanctuary_score,
        total=total,
        duration_sum=duration_sum,
    )
