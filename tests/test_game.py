"""Catalog and scoring unit tests."""

from __future__ import annotations

import pytest

from faraway.domain.cards import load_catalog
from faraway.domain.game import (
    acknowledge_privacy,
    choose_region,
    choose_sanctuary,
    new_game,
    pick_market_region,
)
from faraway.domain.scoring import Totals, check_quest, fame_points, score_tableau


def test_catalog_loads_complete_set() -> None:
    catalog = load_catalog()
    assert len(catalog.regions) == 68
    assert len(catalog.sanctuaries) == 45
    assert catalog.region(1).biome == "red"
    assert catalog.region(68).quest == {"stone": 5}
    assert catalog.region(68).fame == 24


def test_quest_and_flat_fame() -> None:
    totals = Totals.empty()
    totals.values["stone"] = 5
    totals.refresh_sets()
    assert check_quest(totals, {"stone": 5})
    assert not check_quest(totals, {"stone": 6})
    assert fame_points(24, totals) == 24


def test_per_resource_and_sets() -> None:
    totals = Totals.empty()
    totals.values.update(
        {
            "stone": 2,
            "chimera": 2,
            "thistle": 1,
            "red": 2,
            "green": 1,
            "blue": 1,
            "yellow": 1,
            "night": 3,
            "clue": 2,
        }
    )
    totals.refresh_sets()
    assert totals.values["wonderSet"] == 1
    assert totals.values["colorSet"] == 1
    assert fame_points({"per": "night", "score": 2}, totals) == 6
    assert fame_points({"per": "wonderSet", "score": 10}, totals) == 10
    assert fame_points({"per": "colorSet", "score": 10}, totals) == 10
    assert (
        fame_points(
            {"per": {"region1": "red", "region2": "blue"}, "score": 1},
            totals,
        )
        == 3
    )


def test_right_to_left_visibility() -> None:
    catalog = load_catalog()
    # Put high-resource low-fame cards on the right so early cards can see them.
    # Region 2 has 2 stones, no fame. Region 13 gives 2 fame per stone.
    # Tableau left→right: 13, then fillers without stone, then 2 at the end.
    fillers = [3, 5, 9, 10, 11, 12]  # mostly no stones
    tableau = [13, *fillers, 2]
    assert len(tableau) == 8
    breakdown = score_tableau(catalog, tableau, [])
    # When scoring 13 (index 0), all cards including region 2 are visible → stones from 2.
    # Region 13 itself has no stones; region 2 has 2.
    assert breakdown.region_scores[0] == 4  # 2 stones * 2
    # When scoring region 2 last among reveals? Actually scored early in right-to-left.
    # Region 2 has no fame.
    assert breakdown.region_scores[7] == 0


def test_sanctuary_scores_after_regions() -> None:
    catalog = load_catalog()
    # Sanctuary 40: chimera + 1 per chimera. Need 8 regions; use low cards.
    regions = [1, 2, 3, 4, 5, 6, 7, 8]
    breakdown = score_tableau(catalog, regions, [40])
    # Regions contribute some chimeras; sanctuary adds 1 and scores all chimeras at end.
    assert breakdown.sanctuary_score >= 1
    assert breakdown.total == sum(breakdown.region_scores) + breakdown.sanctuary_score


def test_full_seeded_game_eight_rounds() -> None:
    state = new_game("A", "B", seed=42)
    assert state.round == 1
    assert len(state.market) == 3
    assert all(len(p.hand) == 3 for p in state.players)

    for round_no in range(1, 9):
        assert state.round == round_no
        # Privacy → P1 choose
        state = acknowledge_privacy(state)
        p1_card = state.players[0].hand[0]
        state = choose_region(state, p1_card)
        # Privacy → P2 choose
        assert state.phase.value == "privacy"
        state = acknowledge_privacy(state)
        p2_card = state.players[1].hand[0]
        state = choose_region(state, p2_card)

        # End of exploration: market pick then sanctuary, ascending duration.
        while state.phase.value in {"pick_region", "choose_sanctuary"}:
            if state.phase.value == "pick_region":
                state = pick_market_region(state, state.market[0])
            else:
                player = state.active_player
                state = choose_sanctuary(state, player.pending_sanctuary_options[0])

        if round_no < 8:
            assert state.round == round_no + 1
        else:
            assert state.phase.value == "game_over"

    assert state.scores is not None
    assert state.winner_id in {"p1", "p2"}
    for player in state.players:
        assert len(player.tableau) == 8
        assert len(player.hand) == 2  # never picked on round 8; started round 8 with 3, played 1


def test_illegal_actions_rejected() -> None:
    state = new_game("A", "B", seed=1)
    with pytest.raises(ValueError):
        choose_region(state, 99)
    state = acknowledge_privacy(state)
    with pytest.raises(ValueError):
        pick_market_region(state, state.market[0])


def test_no_sanctuary_round_one() -> None:
    state = new_game("A", "B", seed=7)
    state = acknowledge_privacy(state)
    state = choose_region(state, state.players[0].hand[0])
    state = acknowledge_privacy(state)
    state = choose_region(state, state.players[1].hand[0])
    # After round 1 reveal, skip straight to market (or somehow not sanctuary)
    assert state.phase.value == "pick_region"
    assert all(not p.pending_sanctuary_options for p in state.players)
