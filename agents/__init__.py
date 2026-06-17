"""
ScrantonOS — Agent Utilities
==============================
Shared helpers for loading quotes and building agent configurations.
"""

from __future__ import annotations

import json
import os
import random
from typing import Optional

QUOTES_PATH = os.path.join(os.path.dirname(__file__), "..", "quotes", "lines.json")

_quotes_cache: Optional[dict] = None


def _load_quotes() -> dict:
    global _quotes_cache
    if _quotes_cache is None:
        with open(QUOTES_PATH, "r") as f:
            _quotes_cache = json.load(f)
    return _quotes_cache


def get_random_quote(character_id: str) -> str:
    """Get a random iconic quote for a character."""
    quotes = _load_quotes()
    if character_id in quotes and quotes[character_id].get("quotes"):
        return random.choice(quotes[character_id]["quotes"])
    return ""


def get_character_info(character_id: str) -> dict:
    """Get name and title for a character."""
    quotes = _load_quotes()
    if character_id in quotes:
        return {
            "name": quotes[character_id]["name"],
            "title": quotes[character_id]["title"],
        }
    return {"name": character_id, "title": "Unknown"}


# ── Character ID → Agent ID Mapping ─────────────────────────────────

CHARACTER_REGISTRY = {
    "michael": "michael-scott-orchestrator",
    "dwight": "dwight-schrute-sre",
    "oscar": "oscar-martinez-finops",
    "stanley": "stanley-hudson-iam",
    "toby": "toby-flenderson-hitl",
    "jim": "jim-halpert-uiux",
    "meredith": "meredith-palmer-chaos",
    "gabe": "gabe-lewis-docs",
    "jan": "jan-levinson-techdebt",
    "bob_vance": "bob-vance-legacy",
    "creed": "creed-bratton-purge",
    "angela": "angela-martin-firebase",
    "pam": "pam-beesly-artifacts",
    "erin": "erin-hannon-git",
    "kevin": "kevin-malone-metrics",
    "ryan": "ryan-howard-modernize",
}

# ── Accent Colors for UI ────────────────────────────────────────────

CHARACTER_COLORS = {
    "michael": "#4A90D9",      # Corporate blue
    "dwight": "#C0392B",       # Alert red
    "oscar": "#27AE60",        # Money green
    "stanley": "#7F8C8D",      # Neutral gray
    "toby": "#95A5A6",         # Muted gray-blue
    "jim": "#3498DB",          # Relaxed blue
    "meredith": "#E74C3C",     # Bold red
    "gabe": "#8E44AD",         # Corporate purple
    "jan": "#D4AC0D",          # Power gold
    "bob_vance": "#1ABC9C",    # Refrigeration teal
    "creed": "#2C3E50",        # Dark mystery
    "angela": "#E91E63",       # Strict pink
    "pam": "#F39C12",          # Warm amber
    "erin": "#00BCD4",         # Bright cyan
    "kevin": "#E67E22",        # Chili orange
    "ryan": "#BDC3C7",         # Tech silver
}
