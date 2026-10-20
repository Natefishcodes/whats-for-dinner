"""Parsing of Tandoor API payloads (no network)."""

from __future__ import annotations

from datetime import time

from custom_components.tandoor.api import MealPlanEntry, Recipe, normalize_url

BASE = "http://tandoor.local:8080"

RECIPE = {
    "id": 63,
    "name": "Salsa Mexicana",
    "description": "A cooked salsa.",
    "image": "/media/recipes/63.jpg",
    "working_time": 2,
    "waiting_time": 5,
    "servings": 8,
    "keywords": [{"id": 1, "label": "Mexican"}, {"id": 2, "name": "Quick"}],
}


def test_normalize_url() -> None:
    assert normalize_url(" tandoor.local:8080/ ") == "http://tandoor.local:8080"
    assert normalize_url("https://r.example.com") == "https://r.example.com"


def test_recipe_relative_image_and_url() -> None:
    r = Recipe.from_api(RECIPE, BASE)
    assert r.image == f"{BASE}/media/recipes/63.jpg"
    assert r.url == f"{BASE}/recipe/63"
    assert r.total_time == 7
    assert r.keywords == ["Mexican", "Quick"]


def test_meal_plan_entry_parsing() -> None:
    entry = MealPlanEntry.from_api(
        {
            "id": 9,
            "title": "",
            "recipe": RECIPE,
            "servings": 4,
            "note": "Double it",
            "from_date": "2026-10-20T00:00:00-04:00",
            "to_date": "2026-10-20T00:00:00-04:00",
            "meal_type": {"id": 3, "name": "Dinner", "time": "18:00:00"},
        },
        BASE,
    )
    assert entry is not None
    assert entry.name == "Salsa Mexicana"
    assert entry.meal_type.time == time(18, 0)
    assert entry.start.utcoffset().total_seconds() == -4 * 3600


def test_title_only_entry_and_bad_date() -> None:
    entry = MealPlanEntry.from_api(
        {"id": 1, "title": "Leftovers", "recipe": None, "from_date": "2026-10-20", "meal_type": None}, BASE
    )
    assert entry.name == "Leftovers"
    assert MealPlanEntry.from_api({"id": 2, "from_date": "nope"}, BASE) is None
