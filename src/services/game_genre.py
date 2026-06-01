"""Genre inference and same-genre competitor assignment (no game_intel dependency)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

STEAM_APP_GENRES: Dict[str, str] = {
    "10": "FPS",
    "730": "FPS",
    "570": "MOBA",
    "1172470": "FPS",
    "440": "FPS",
    "252490": "Survival",
    "578080": "Battle Royale",
    "381210": "Horror",
    "236390": "Simulation",
    "1091500": "Open World",
    "1245620": "RPG",
}

STEAM_APP_NAMES: Dict[str, str] = {
    "10": "Counter-Strike",
    "730": "Counter-Strike 2",
    "570": "Dota 2",
    "1172470": "Apex Legends",
    "440": "Team Fortress 2",
    "252490": "Rust",
    "578080": "PUBG",
    "381210": "Dead by Daylight",
    "236390": "War Thunder",
    "1091500": "Cyberpunk 2077",
    "1245620": "Elden Ring",
}

# When a genre has only one title in the batch, pull peers from these related genres first.
RELATED_GENRES: Dict[str, List[str]] = {
    "RPG": ["Open World", "Survival", "PC Game"],
    "Open World": ["RPG", "Survival", "PC Game"],
    "FPS": ["Battle Royale", "MOBA", "Simulation"],
    "MOBA": ["FPS", "Battle Royale"],
    "Battle Royale": ["FPS", "Survival"],
    "Survival": ["Battle Royale", "Horror", "Simulation"],
    "Horror": ["Survival", "PC Game"],
    "Simulation": ["FPS", "Survival"],
    "PC Game": ["RPG", "Open World", "FPS"],
}


def normalize_steam_app_id(product_id: str) -> str:
    pid = str(product_id or "").strip()
    if pid.startswith("steam_"):
        return pid.replace("steam_", "", 1)
    return pid


def lookup_steam_product_name(product_id: str) -> str:
    return STEAM_APP_NAMES.get(normalize_steam_app_id(product_id), "")


def infer_product_genre(product_id: str, product_name: str = "") -> str:
    pid = normalize_steam_app_id(product_id)
    if pid in STEAM_APP_GENRES:
        return STEAM_APP_GENRES[pid]
    name = (product_name or "").lower()
    rules = [
        ("MOBA", ("dota", "moba", "legend", "league")),
        ("FPS", ("counter", "shooter", "apex", "cs2", "valorant", "fortress")),
        ("Battle Royale", ("pubg", "battleground", "royale")),
        ("RPG", ("elden", "ring", "rpg", "souls")),
        ("Open World", ("cyberpunk", "open world", "gta")),
        ("Roguelike", ("rogue", "spire", "deck")),
        ("Horror", ("dead by daylight", "horror")),
        ("Survival", ("rust", "survival")),
        ("Simulation", ("war thunder", "sim")),
    ]
    for genre, keywords in rules:
        if any(k in name for k in keywords):
            return genre
    return "PC Game"


def assign_competitors_by_genre(products: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """Return game_id -> competitor_ids (same genre first, then related / batch fallback, up to 4)."""
    by_genre: Dict[str, List[str]] = defaultdict(list)
    genres: Dict[str, str] = {}
    all_game_ids = [f"steam_{pid}" for pid in products]

    for pid, meta in products.items():
        game_id = f"steam_{pid}"
        genre = meta.get("genre") or infer_product_genre(pid, meta.get("name", ""))
        genres[game_id] = genre
        by_genre[genre].append(game_id)

    result: Dict[str, List[str]] = {}
    for pid in products:
        game_id = f"steam_{pid}"
        genre = genres[game_id]
        peers: List[str] = [gid for gid in by_genre.get(genre, []) if gid != game_id]
        seen = {game_id, *peers}

        if not peers:
            for related in RELATED_GENRES.get(genre, []):
                for gid in by_genre.get(related, []):
                    if gid not in seen:
                        peers.append(gid)
                        seen.add(gid)
                    if len(peers) >= 4:
                        break
                if len(peers) >= 4:
                    break

        if not peers:
            peers = [gid for gid in all_game_ids if gid != game_id][:4]

        result[game_id] = peers[:4]
    return result
