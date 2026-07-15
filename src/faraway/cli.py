"""CLI for starting and stopping the local Faraway server."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
ROOT = Path(__file__).resolve().parents[2]
PID_PATH = ROOT / "data" / "faraway.pid"
GAME_PATH = ROOT / "data" / "active_game.json"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="faraway", description="Faraway pass-and-play")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("start", help="Start the local web server (default)")
    stop_parser = sub.add_parser("stop", help="Stop the server and free the port")
    stop_parser.add_argument(
        "--keep-save",
        action="store_true",
        help="Keep the persisted active game instead of clearing it",
    )
    args = parser.parse_args(argv)

    if args.command in (None, "start"):
        start_server()
        return
    if args.command == "stop":
        stop_server(clear_save=not args.keep_save)
        return
    parser.error(f"Unknown command: {args.command}")


def start_server() -> None:
    if _port_in_use(PORT):
        print(
            f"Port {PORT} is already in use.\n"
            f"Open http://{HOST}:{PORT} or run: uv run faraway stop",
            file=sys.stderr,
        )
        raise SystemExit(1)

    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    try:
        import uvicorn

        print(f"Starting Faraway on http://{HOST}:{PORT}")
        uvicorn.run("faraway.web.app:app", host=HOST, port=PORT, reload=False)
    finally:
        if PID_PATH.is_file() and PID_PATH.read_text(encoding="utf-8").strip() == str(os.getpid()):
            PID_PATH.unlink(missing_ok=True)


def stop_server(*, clear_save: bool = True) -> None:
    killed: set[int] = set()

    if PID_PATH.is_file():
        try:
            pid = int(PID_PATH.read_text(encoding="utf-8").strip())
        except ValueError:
            pid = None
        if pid is not None and _pid_alive(pid):
            _kill_pid(pid)
            killed.add(pid)

    for pid in _pids_on_port(PORT):
        if pid not in killed:
            _kill_pid(pid)
            killed.add(pid)

    # Wait briefly for the port to release.
    for _ in range(20):
        if not _port_in_use(PORT):
            break
        time.sleep(0.1)

    PID_PATH.unlink(missing_ok=True)

    if clear_save and GAME_PATH.is_file():
        GAME_PATH.unlink()
        print(f"Cleared saved game ({GAME_PATH.name}).")

    if killed:
        print(f"Stopped Faraway process(es): {', '.join(str(p) for p in sorted(killed))}.")
    else:
        print("No Faraway server was running.")

    if _port_in_use(PORT):
        print(f"Warning: port {PORT} is still in use.", file=sys.stderr)
        raise SystemExit(1)

    print(f"Port {PORT} is free.")


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((HOST, port)) == 0


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _kill_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(20):
        if not _pid_alive(pid):
            return
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _pids_on_port(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"TCP:{port}", "-sTCP:LISTEN"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def stop_main() -> None:
    """Console script entry point for `faraway-stop`."""
    main(["stop"])


if __name__ == "__main__":
    main()
