"""Server-authoritative Faraway game state for two human players."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from faraway.domain.cards import Catalog, load_catalog
from faraway.domain.scoring import ScoreBreakdown, score_tableau

ROUNDS = 8
HAND_SIZE = 3


class Phase(StrEnum):
    SETUP = "setup"
    PRIVACY = "privacy"
    CHOOSE_REGION = "choose_region"
    REVEAL = "reveal"
    CHOOSE_SANCTUARY = "choose_sanctuary"
    PICK_REGION = "pick_region"
    GAME_OVER = "game_over"


class PrivacyNext(StrEnum):
    """What happens after the player acknowledges the privacy handoff."""

    CHOOSE_REGION = "choose_region"
    END_TURN = "end_turn"


@dataclass
class PlayerState:
    id: str
    name: str
    hand: list[int] = field(default_factory=list)
    tableau: list[int] = field(default_factory=list)
    sanctuaries: list[int] = field(default_factory=list)
    pending_sanctuary_options: list[int] = field(default_factory=list)
    chosen_region: int | None = None
    ready: bool = False


@dataclass
class GameState:
    catalog: Catalog
    seed: int
    players: list[PlayerState]
    region_deck: list[int]
    sanctuary_deck: list[int]
    market: list[int]
    discard: list[int] = field(default_factory=list)
    round: int = 1
    phase: Phase = Phase.PRIVACY
    privacy_next: PrivacyNext = PrivacyNext.CHOOSE_REGION
    active_player_index: int = 0
    turn_order: list[int] = field(default_factory=list)
    sanctuary_queue: list[int] = field(default_factory=list)
    message: str = ""
    scores: dict[str, ScoreBreakdown] | None = None
    winner_id: str | None = None

    @property
    def active_player(self) -> PlayerState:
        return self.players[self.active_player_index]


def new_game(
    player1_name: str = "Player 1",
    player2_name: str = "Player 2",
    seed: int | None = None,
    catalog: Catalog | None = None,
) -> GameState:
    catalog = catalog or load_catalog()
    rng_seed = seed if seed is not None else random.randrange(1, 1_000_000_000)
    rng = random.Random(rng_seed)

    region_deck = list(range(1, 69))
    sanctuary_deck = list(range(1, 46))
    rng.shuffle(region_deck)
    rng.shuffle(sanctuary_deck)

    players = [
        PlayerState(id="p1", name=player1_name or "Player 1"),
        PlayerState(id="p2", name=player2_name or "Player 2"),
    ]
    for player in players:
        player.hand = [region_deck.pop() for _ in range(HAND_SIZE)]

    market = [region_deck.pop() for _ in range(len(players) + 1)]

    return GameState(
        catalog=catalog,
        seed=rng_seed,
        players=players,
        region_deck=region_deck,
        sanctuary_deck=sanctuary_deck,
        market=market,
        phase=Phase.PRIVACY,
        privacy_next=PrivacyNext.CHOOSE_REGION,
        active_player_index=0,
        message=f"Pass the device to {players[0].name}.",
    )


def acknowledge_privacy(state: GameState) -> GameState:
    _require(state.phase == Phase.PRIVACY, "Not waiting for a privacy handoff")
    if state.privacy_next == PrivacyNext.END_TURN:
        _begin_end_of_exploration_turn(state)
        return state
    state.phase = Phase.CHOOSE_REGION
    player = state.active_player
    state.message = f"{player.name}: choose a Region from your hand."
    return state


def choose_region(state: GameState, region_number: int) -> GameState:
    _require(state.phase == Phase.CHOOSE_REGION, "Not choosing a region")
    player = state.active_player
    _require(region_number in player.hand, "That Region is not in your hand")

    player.chosen_region = region_number
    player.ready = True
    player.hand = [card for card in player.hand if card != region_number]

    if not all(p.ready for p in state.players):
        state.phase = Phase.PRIVACY
        state.privacy_next = PrivacyNext.CHOOSE_REGION
        state.active_player_index = 1 if state.active_player_index == 0 else 0
        next_player = state.active_player
        state.message = f"Pass the device to {next_player.name}."
        return state

    _reveal_and_continue(state)
    return state


def choose_sanctuary(state: GameState, tile: int) -> GameState:
    _require(state.phase == Phase.CHOOSE_SANCTUARY, "Not choosing a sanctuary")
    player = state.active_player
    _require(tile in player.pending_sanctuary_options, "That Sanctuary was not offered")

    leftovers = [opt for opt in player.pending_sanctuary_options if opt != tile]
    player.sanctuaries.append(tile)
    player.pending_sanctuary_options = []
    # Put unchosen options under the sanctuary deck (face down).
    state.sanctuary_deck = leftovers + state.sanctuary_deck

    _advance_end_of_exploration(state)
    return state


def pick_market_region(state: GameState, region_number: int) -> GameState:
    _require(state.phase == Phase.PICK_REGION, "Not picking from the market")
    _require(state.round < ROUNDS, "No market pick on the final round")
    player = state.active_player
    _require(region_number in state.market, "That Region is not in the market")
    _require(len(player.hand) < HAND_SIZE, "Hand is already full")

    state.market.remove(region_number)
    player.hand.append(region_number)
    _continue_after_market_pick(state)
    return state


def _reveal_and_continue(state: GameState) -> None:
    state.phase = Phase.REVEAL
    for player in state.players:
        assert player.chosen_region is not None
        player.tableau.append(player.chosen_region)

    # Sanctuary eligibility: higher exploration duration than previously played card.
    # Round 1: nobody can gain a Sanctuary.
    if state.round > 1:
        for player in state.players:
            previous = player.tableau[-2]
            current = player.tableau[-1]
            if current > previous:
                clues = _clue_count(state, player)
                player.pending_sanctuary_options = _draw_sanctuaries(state, 1 + clues)

    for player in state.players:
        player.chosen_region = None
        player.ready = False

    # End of Exploration: ascending duration. On a turn: market pick (if any), then sanctuary.
    state.turn_order = sorted(
        range(len(state.players)),
        key=lambda i: state.players[i].tableau[-1],
    )
    _start_next_end_turn(state)


def _start_next_end_turn(state: GameState) -> None:
    if not state.turn_order:
        _finish_round_or_game(state)
        return

    state.active_player_index = state.turn_order.pop(0)
    player = state.active_player
    state.phase = Phase.PRIVACY
    state.privacy_next = PrivacyNext.END_TURN
    state.message = f"Pass the device to {player.name}."


def _begin_end_of_exploration_turn(state: GameState) -> None:
    player = state.active_player
    if state.round < ROUNDS:
        state.phase = Phase.PICK_REGION
        state.message = f"{player.name}: take a Region from the market."
        return

    _continue_after_market_pick(state)


def _continue_after_market_pick(state: GameState) -> None:
    player = state.active_player
    if player.pending_sanctuary_options:
        state.phase = Phase.CHOOSE_SANCTUARY
        state.message = f"{player.name}: choose 1 Sanctuary to keep."
        return
    _advance_end_of_exploration(state)


def _advance_end_of_exploration(state: GameState) -> None:
    _start_next_end_turn(state)


def _finish_round_or_game(state: GameState) -> None:
    # Discard the leftover market card, then refill unless game ends.
    if state.market:
        state.discard.extend(state.market)
        state.market = []

    if state.round >= ROUNDS:
        _score_game(state)
        return

    state.round += 1
    state.market = [
        state.region_deck.pop()
        for _ in range(len(state.players) + 1)
        if state.region_deck
    ]
    state.phase = Phase.PRIVACY
    state.privacy_next = PrivacyNext.CHOOSE_REGION
    state.active_player_index = 0
    state.message = f"Round {state.round}. Pass the device to {state.players[0].name}."


def _score_game(state: GameState) -> None:
    state.phase = Phase.GAME_OVER
    scores: dict[str, ScoreBreakdown] = {}
    for player in state.players:
        scores[player.id] = score_tableau(
            state.catalog,
            player.tableau,
            player.sanctuaries,
        )
    state.scores = scores

    ranking = sorted(
        state.players,
        key=lambda p: (
            scores[p.id].total,
            -scores[p.id].duration_sum,  # lower duration sum wins ties
        ),
        reverse=True,
    )
    # With reverse=True on (total, -duration), higher total first; if totals equal,
    # larger -duration (i.e. lower duration) wins. Correct.
    state.winner_id = ranking[0].id
    winner = ranking[0]
    state.message = f"{winner.name} wins with {scores[winner.id].total} fame!"


def _clue_count(state: GameState, player: PlayerState) -> int:
    clues = 0
    for number in player.tableau:
        if state.catalog.region(number).clue:
            clues += 1
    for tile in player.sanctuaries:
        if state.catalog.sanctuary(tile).clue:
            clues += 1
    return clues


def _draw_sanctuaries(state: GameState, count: int) -> list[int]:
    drawn: list[int] = []
    for _ in range(count):
        if not state.sanctuary_deck:
            break
        drawn.append(state.sanctuary_deck.pop())
    return drawn


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def public_snapshot(state: GameState, viewer_id: str | None = None) -> dict[str, Any]:
    """Snapshot for UI. Hides opponents' hands except during own choose phase."""
    active = state.active_player
    players_out = []
    for player in state.players:
        show_hand = (
            state.phase in {Phase.CHOOSE_REGION, Phase.CHOOSE_SANCTUARY, Phase.PICK_REGION}
            and player.id == active.id
            and (viewer_id is None or viewer_id == player.id)
        )
        # During privacy, hide everything private.
        if state.phase == Phase.PRIVACY:
            show_hand = False
        show_pending = (
            show_hand
            and state.phase in {Phase.CHOOSE_SANCTUARY, Phase.PICK_REGION}
            and player.id == active.id
        )
        players_out.append(
            {
                "id": player.id,
                "name": player.name,
                "hand": [_region_view(state, n) for n in player.hand] if show_hand else [],
                "hand_count": len(player.hand),
                "tableau": [_region_view(state, n) for n in player.tableau],
                "sanctuaries": [_sanctuary_view(state, t) for t in player.sanctuaries],
                "pending_sanctuaries": (
                    [_sanctuary_view(state, t) for t in player.pending_sanctuary_options]
                    if show_pending
                    else []
                ),
                "ready": player.ready,
            }
        )

    scores_out = None
    if state.scores is not None:
        scores_out = {
            pid: asdict(breakdown) for pid, breakdown in state.scores.items()
        }

    return {
        "seed": state.seed,
        "round": state.round,
        "phase": state.phase.value,
        "message": state.message,
        "active_player_id": active.id if state.phase != Phase.GAME_OVER else None,
        "market": [_region_view(state, n) for n in state.market],
        "players": players_out,
        "scores": scores_out,
        "winner_id": state.winner_id,
        "region_deck_count": len(state.region_deck),
        "sanctuary_deck_count": len(state.sanctuary_deck),
    }


def _region_view(state: GameState, number: int) -> dict[str, Any]:
    card = state.catalog.region(number)
    return {
        "id": card.id,
        "number": card.number,
        "biome": card.biome,
        "image": card.image,
        "night": card.night,
        "clue": card.clue,
        "wonders": card.wonders or {},
        "quest": card.quest or {},
        "fame": card.fame,
        "summary": _region_summary(card),
    }


def _sanctuary_view(state: GameState, tile: int) -> dict[str, Any]:
    card = state.catalog.sanctuary(tile)
    return {
        "id": card.id,
        "tile": card.tile,
        "biome": card.biome,
        "image": card.image,
        "night": card.night,
        "clue": card.clue,
        "wonders": card.wonders or {},
        "fame": card.fame,
        "summary": _sanctuary_summary(card),
    }


def _region_summary(card: Any) -> str:
    parts = [f"#{card.number}", card.biome]
    if card.night:
        parts.append("night")
    if card.clue:
        parts.append("clue")
    if card.wonders:
        parts.append("+".join(f"{k}:{v}" for k, v in card.wonders.items()))
    if card.quest:
        parts.append("need " + "+".join(f"{k}:{v}" for k, v in card.quest.items()))
    if card.fame is not None:
        parts.append(f"fame={card.fame}")
    return " · ".join(parts)


def _sanctuary_summary(card: Any) -> str:
    parts = [f"S{card.tile}", card.biome]
    if card.night:
        parts.append("night")
    if card.clue:
        parts.append("clue")
    if card.wonders:
        parts.append("+".join(f"{k}:{v}" for k, v in card.wonders.items()))
    if card.fame is not None:
        parts.append(f"fame={card.fame}")
    return " · ".join(parts)
