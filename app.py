from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, request

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATE_FILE = BASE_DIR / "squares.json"
DIGITS = list(range(10))

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")


def default_state() -> Dict[str, Any]:
    return {
        "team_top": "New England Patriots",
        "team_left": "Seattle Seahawks",
        "seed": None,
        "grid": [["" for _ in range(10)] for _ in range(10)],
        "col_digits": [],
        "row_digits": [],
    }


def ensure_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        STATE_FILE.write_text(json.dumps(default_state(), indent=2), encoding="utf-8")
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: Dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def is_filled(state: Dict[str, Any]) -> bool:
    try:
        return all(str(state["grid"][r][c]).strip() for r in range(10) for c in range(10))
    except Exception:
        return False


def fill_grid_randomly(state: Dict[str, Any], entries: List[str]) -> None:
    if len(entries) != 100:
        raise ValueError("Must provide exactly 100 entries.")

    if state.get("seed") is None:
        state["seed"] = random.randint(1, 10_000_000)

    rng = random.Random(state["seed"])
    rng.shuffle(entries)

    idx = 0
    for r in range(10):
        for c in range(10):
            state["grid"][r][c] = entries[idx]
            idx += 1


# ✅ Pages (served from /static)
@app.get("/")
def setup_page():
    return app.send_static_file("setup.html")


@app.get("/board")
def board_page():
    return app.send_static_file("board.html")


# ✅ Debug route to prove Flask can see your files
@app.get("/__debug")
def debug():
    return jsonify({
        "base_dir": str(BASE_DIR),
        "static_dir": str(STATIC_DIR),
        "static_exists": STATIC_DIR.exists(),
        "static_files": sorted([p.name for p in STATIC_DIR.glob("*")]) if STATIC_DIR.exists() else [],
        "state_file": str(STATE_FILE),
        "state_exists": STATE_FILE.exists(),
    })


# ✅ API
@app.get("/api/state")
def api_state():
    return jsonify(ensure_state())


@app.post("/api/reset")
def api_reset():
    STATE_FILE.write_text(json.dumps(default_state(), indent=2), encoding="utf-8")
    return jsonify({"ok": True})


@app.post("/api/fill-random")
def api_fill_random():
    body = request.get_json(force=True) or {}
    entries = body.get("entries", [])
    seed = body.get("seed", None)

    if not isinstance(entries, list) or not entries:
        return jsonify({"ok": False, "error": "entries must be a non-empty list"}), 400

    expanded: List[str] = []
    for item in entries:
        name = str(item.get("name", "")).strip()
        try:
            count = int(item.get("count", 0))
        except Exception:
            return jsonify({"ok": False, "error": "Invalid count"}), 400

        if not name:
            return jsonify({"ok": False, "error": "Name cannot be empty"}), 400
        if count <= 0:
            return jsonify({"ok": False, "error": f"Count must be > 0 for {name}"}), 400

        expanded.extend([name] * count)

    if len(expanded) != 100:
        return jsonify({"ok": False, "error": f"Total squares must be exactly 100 (you have {len(expanded)})"}), 400

    state = ensure_state()
    if seed is not None and str(seed).strip() != "":
        state["seed"] = int(seed)

    # Reset digits when refilling
    state["col_digits"] = []
    state["row_digits"] = []

    fill_grid_randomly(state, expanded)
    save_state(state)
    return jsonify({"ok": True, "seed": state["seed"]})


@app.post("/api/assign-digits")
def api_assign_digits():
    body = request.get_json(force=True) or {}
    seed = body.get("seed", None)

    state = ensure_state()
    if not is_filled(state):
        return jsonify({"ok": False, "error": "Fill all 100 squares before assigning digits."}), 400

    if seed is not None and str(seed).strip() != "":
        state["seed"] = int(seed)
    if state.get("seed") is None:
        state["seed"] = random.randint(1, 10_000_000)

    rng = random.Random(state["seed"])
    col = DIGITS.copy()
    row = DIGITS.copy()
    rng.shuffle(col)
    rng.shuffle(row)

    state["col_digits"] = col
    state["row_digits"] = row
    save_state(state)

    return jsonify({"ok": True, "seed": state["seed"], "col_digits": col, "row_digits": row})


@app.post("/api/update")
def api_update():
    body = request.get_json(force=True) or {}
    r = int(body.get("row"))
    c = int(body.get("col"))
    name = str(body.get("name", "")).strip()

    if not (0 <= r <= 9 and 0 <= c <= 9):
        return jsonify({"ok": False, "error": "row/col out of range"}), 400

    state = ensure_state()
    state["grid"][r][c] = name
    save_state(state)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055, debug=True)
