# Faraway — Pass & Play

Local two-player Faraway using your scanned Region and Sanctuary cards.

## Run

```bash
uv sync --extra dev
uv run faraway
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765).

## Stop

```bash
uv run faraway stop
```

Same thing: `uv run faraway-stop`.

This kills the server, frees port 8765, and clears the saved active game. Use `uv run faraway stop --keep-save` to leave the in-progress game on disk.

## Play

1. Enter two player names (optional seed for reproducible deals).
2. Pass the device: each player privately chooses a Region, then both cards reveal together.
3. Eligible players draft Sanctuaries; then pick Region cards from the market in ascending exploration order.
4. After 8 rounds, scores are calculated right-to-left automatically.

## Develop

```bash
uv run ruff check .
uv run pytest
```

Card data lives in `data/cards.json`. Original scans stay under `src/`.
