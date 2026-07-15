"""FastAPI pass-and-play server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from faraway.domain.game import (
    GameState,
    Phase,
    PrivacyNext,
    acknowledge_privacy,
    choose_region,
    choose_sanctuary,
    new_game,
    pick_market_region,
    public_snapshot,
)

ROOT = Path(__file__).resolve().parents[3]
WEB_DIR = Path(__file__).resolve().parent
STORE_PATH = ROOT / "data" / "active_game.json"

app = FastAPI(title="Faraway Pass & Play")
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
app.mount("/assets", StaticFiles(directory=str(ROOT / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

_state: GameState | None = None


class StartRequest(BaseModel):
    player1: str = Field(default="Player 1", max_length=40)
    player2: str = Field(default="Player 2", max_length=40)
    seed: int | None = None


class ChooseRegionRequest(BaseModel):
    region: int


class ChooseSanctuaryRequest(BaseModel):
    tile: int


class PickMarketRequest(BaseModel):
    region: int


def _game() -> GameState:
    global _state
    if _state is None:
        _state = _load_or_none()
    if _state is None:
        raise HTTPException(status_code=404, detail="No active game. Start a new one.")
    return _state


def _set_game(state: GameState) -> GameState:
    global _state
    _state = state
    _persist(state)
    return state


def _persist(state: GameState) -> None:
    payload = {
        "seed": state.seed,
        "round": state.round,
        "phase": state.phase.value,
        "privacy_next": state.privacy_next.value,
        "active_player_index": state.active_player_index,
        "turn_order": state.turn_order,
        "sanctuary_queue": state.sanctuary_queue,
        "message": state.message,
        "winner_id": state.winner_id,
        "region_deck": state.region_deck,
        "sanctuary_deck": state.sanctuary_deck,
        "market": state.market,
        "discard": state.discard,
        "players": [
            {
                "id": p.id,
                "name": p.name,
                "hand": p.hand,
                "tableau": p.tableau,
                "sanctuaries": p.sanctuaries,
                "pending_sanctuary_options": p.pending_sanctuary_options,
                "chosen_region": p.chosen_region,
                "ready": p.ready,
            }
            for p in state.players
        ],
        "scores": (
            {
                pid: {
                    "region_scores": s.region_scores,
                    "sanctuary_score": s.sanctuary_score,
                    "total": s.total,
                    "duration_sum": s.duration_sum,
                }
                for pid, s in state.scores.items()
            }
            if state.scores
            else None
        ),
    }
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(payload, indent=2))


def _load_or_none() -> GameState | None:
    if not STORE_PATH.is_file():
        return None
    from faraway.domain.cards import load_catalog
    from faraway.domain.game import PlayerState
    from faraway.domain.scoring import ScoreBreakdown

    raw = json.loads(STORE_PATH.read_text())
    catalog = load_catalog()
    players = [PlayerState(**p) for p in raw["players"]]
    scores = None
    if raw.get("scores"):
        scores = {
            pid: ScoreBreakdown(**data) for pid, data in raw["scores"].items()
        }
    return GameState(
        catalog=catalog,
        seed=raw["seed"],
        players=players,
        region_deck=raw["region_deck"],
        sanctuary_deck=raw["sanctuary_deck"],
        market=raw["market"],
        discard=raw.get("discard", []),
        round=raw["round"],
        phase=Phase(raw["phase"]),
        privacy_next=PrivacyNext(raw.get("privacy_next", PrivacyNext.CHOOSE_REGION)),
        active_player_index=raw["active_player_index"],
        turn_order=raw.get("turn_order", []),
        sanctuary_queue=raw.get("sanctuary_queue", []),
        message=raw.get("message", ""),
        scores=scores,
        winner_id=raw.get("winner_id"),
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/api/state")
def get_state() -> dict[str, Any]:
    try:
        state = _game()
    except HTTPException:
        return {"active": False}
    return {"active": True, **public_snapshot(state)}


@app.post("/api/new")
def start_game(body: StartRequest) -> dict[str, Any]:
    state = new_game(body.player1, body.player2, body.seed)
    _set_game(state)
    return {"active": True, **public_snapshot(state)}


@app.post("/api/privacy")
def privacy() -> dict[str, Any]:
    state = acknowledge_privacy(_game())
    _set_game(state)
    return {"active": True, **public_snapshot(state)}


@app.post("/api/choose-region")
def api_choose_region(body: ChooseRegionRequest) -> dict[str, Any]:
    try:
        state = choose_region(_game(), body.region)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_game(state)
    return {"active": True, **public_snapshot(state)}


@app.post("/api/choose-sanctuary")
def api_choose_sanctuary(body: ChooseSanctuaryRequest) -> dict[str, Any]:
    try:
        state = choose_sanctuary(_game(), body.tile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_game(state)
    return {"active": True, **public_snapshot(state)}


@app.post("/api/pick-market")
def api_pick_market(body: PickMarketRequest) -> dict[str, Any]:
    try:
        state = pick_market_region(_game(), body.region)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_game(state)
    return {"active": True, **public_snapshot(state)}


def main() -> None:
    from faraway.cli import main as cli_main

    cli_main(["start"])


if __name__ == "__main__":
    main()
