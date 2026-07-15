# Faraway — Pass & Play

A local, two-player digital version of the [Faraway](https://www.catchupgames.com/games/faraway/) board game. Pass one device back and forth: each player chooses a Region in private, then sanctuary drafts and market picks resolve in exploration order. Scores are computed automatically after 8 rounds.

> Unofficial fan project — not affiliated with Catch Up Games.

## Features

- **Pass-and-play UI** — privacy handoff so the other player does not see your hand
- **Full rules flow** — Region choice → reveal → Sanctuary draft → market pick, for 8 rounds
- **Server-authoritative state** — FastAPI game engine with automatic endgame scoring
- **Persistent save** — resume an in-progress game after a refresh or restart
- **Reproducible deals** — optional seed when starting a new game
- **Card catalog** — Region and Sanctuary data in `data/cards.json`, with scanned art under `assets/`

## Requirements

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/)

## Quick start

```bash
git clone https://github.com/vmonney/Faraway_game.git
cd Faraway_game
uv sync --extra dev
uv run faraway
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765).

### Stop the server

```bash
uv run faraway stop
```

Equivalent: `uv run faraway-stop`.

This stops the process, frees port **8765**, and clears the saved game. To keep the in-progress game on disk:

```bash
uv run faraway stop --keep-save
```

## How to play

1. Enter two player names (optionally set a seed for a reproducible deal).
2. Pass the device: each player privately chooses a Region from their hand, then both cards are revealed together.
3. Eligible players draft Sanctuaries, then pick Region cards from the market in ascending exploration order.
4. After 8 rounds, scores are calculated right-to-left automatically and a winner is shown.

## Project structure

```
Faraway_game/
├── assets/                 # Card and player-aid images
├── data/
│   └── cards.json          # Region & Sanctuary catalog
├── src/faraway/
│   ├── cli.py              # `faraway` / `faraway-stop` entry points
│   ├── domain/             # Game rules, cards, scoring
│   └── web/                # FastAPI app, templates, static UI
└── tests/
```

## Development

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

| Tool | Role |
|------|------|
| **uv** | Package & environment management |
| **Ruff** | Linting |
| **pytest** | Unit tests |
| **FastAPI** + **Uvicorn** | Local web server |
| **Jinja2** | HTML templates |

## License / credits

Game rules and artwork belong to their respective owners (Catch Up Games / Faraway). This repository is a personal, non-commercial digital play-aid.
