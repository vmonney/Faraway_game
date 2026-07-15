"""Card catalog loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG = ROOT / "data" / "cards.json"

WonderCount = dict[str, int]
Fame = int | dict[str, Any]


@dataclass(frozen=True, slots=True)
class RegionCard:
    id: str
    number: int
    biome: str
    image: str
    night: bool = False
    clue: bool = False
    wonders: WonderCount | None = None
    quest: WonderCount | None = None
    fame: Fame | None = None


@dataclass(frozen=True, slots=True)
class SanctuaryCard:
    id: str
    tile: int
    biome: str
    image: str
    night: bool = False
    clue: bool = False
    wonders: WonderCount | None = None
    fame: Fame | None = None


@dataclass(frozen=True, slots=True)
class Catalog:
    regions: dict[int, RegionCard]
    sanctuaries: dict[int, SanctuaryCard]

    def region(self, number: int) -> RegionCard:
        return self.regions[number]

    def sanctuary(self, tile: int) -> SanctuaryCard:
        return self.sanctuaries[tile]


def _bool_flag(raw: dict[str, Any], key: str) -> bool:
    return bool(raw.get(key))


def load_catalog(path: Path | None = None) -> Catalog:
    catalog_path = path or DEFAULT_CATALOG
    data = json.loads(catalog_path.read_text())
    regions: dict[int, RegionCard] = {}
    for raw in data["regions"]:
        number = int(raw["number"])
        regions[number] = RegionCard(
            id=raw.get("id", f"R{number:02d}"),
            number=number,
            biome=raw["biome"],
            image=raw["image"],
            night=_bool_flag(raw, "night"),
            clue=_bool_flag(raw, "clue"),
            wonders=dict(raw["wonders"]) if raw.get("wonders") else None,
            quest=dict(raw["quest"]) if raw.get("quest") else None,
            fame=raw.get("fame"),
        )
    sanctuaries: dict[int, SanctuaryCard] = {}
    for raw in data["sanctuaries"]:
        tile = int(raw["tile"])
        sanctuaries[tile] = SanctuaryCard(
            id=raw.get("id", f"S{tile:02d}"),
            tile=tile,
            biome=raw["biome"],
            image=raw["image"],
            night=_bool_flag(raw, "night"),
            clue=_bool_flag(raw, "clue"),
            wonders=dict(raw["wonders"]) if raw.get("wonders") else None,
            fame=raw.get("fame"),
        )
    validate_catalog(regions, sanctuaries, catalog_path.parent.parent)
    return Catalog(regions=regions, sanctuaries=sanctuaries)


def validate_catalog(
    regions: dict[int, RegionCard],
    sanctuaries: dict[int, SanctuaryCard],
    root: Path | None = None,
) -> None:
    if len(regions) != 68:
        raise ValueError(f"Expected 68 regions, got {len(regions)}")
    if set(regions) != set(range(1, 69)):
        raise ValueError("Region numbers must be unique 1..68")
    if len(sanctuaries) != 45:
        raise ValueError(f"Expected 45 sanctuaries, got {len(sanctuaries)}")
    if set(sanctuaries) != set(range(1, 46)):
        raise ValueError("Sanctuary tiles must be unique 1..45")

    project_root = root or ROOT
    for card in (*regions.values(), *sanctuaries.values()):
        image_path = project_root / card.image.lstrip("/")
        if not image_path.is_file():
            raise FileNotFoundError(f"Missing card image: {image_path}")
        _validate_fame(card.fame, label=card.id)


def _validate_fame(fame: Fame | None, *, label: str) -> None:
    if fame is None or isinstance(fame, int):
        return
    if not isinstance(fame, dict) or "per" not in fame or "score" not in fame:
        raise ValueError(f"Invalid fame on {label}: {fame}")
    per = fame["per"]
    allowed = {
        "night",
        "stone",
        "chimera",
        "thistle",
        "clue",
        "colorSet",
        "wonderSet",
        "red",
        "green",
        "blue",
        "yellow",
        "colorless",
    }
    if isinstance(per, str):
        if per not in allowed:
            raise ValueError(f"Unknown fame.per {per!r} on {label}")
        return
    if isinstance(per, dict) and {"region1", "region2"} <= set(per):
        return
    raise ValueError(f"Unsupported fame.per on {label}: {per}")
