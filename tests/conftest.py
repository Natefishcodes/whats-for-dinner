"""Shared fixtures: a fake Tandoor answering the three endpoints the integration uses."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tandoor.api import MealPlanEntry, MealType, Recipe
from custom_components.tandoor.const import DOMAIN

BASE = "http://tandoor.local:8080"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load custom_components/tandoor."""


def recipe(rid: int = 63, name: str = "Salsa Mexicana", **kw: Any) -> Recipe:
    return Recipe(
        id=rid,
        name=name,
        url=f"{BASE}/recipe/{rid}",
        description=kw.get("description", "A cooked salsa."),
        image=kw.get("image", f"{BASE}/media/recipes/{rid}.jpg"),
        working_time=kw.get("working_time", 10),
        waiting_time=kw.get("waiting_time", 20),
        servings=kw.get("servings", 4),
    )


DINNER = MealType(id=3, name="Dinner")
LUNCH = MealType(id=2, name="Lunch")


def entry_today(meal_type: MealType, rec: Recipe | None, eid: int = 1) -> MealPlanEntry:
    start = dt_util.start_of_local_day()
    return MealPlanEntry(
        id=eid, title="", start=start, end=start, meal_type=meal_type, recipe=rec, servings=2
    )


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="tandoor.local:8080",
        unique_id=BASE,
        data={CONF_URL: BASE, CONF_API_TOKEN: "tda_test", CONF_VERIFY_SSL: True},
    )


@pytest.fixture
def mock_client():
    """Patch TandoorClient everywhere it is constructed."""
    with (
        patch("custom_components.tandoor.TandoorClient", autospec=True) as cls,
        patch("custom_components.tandoor.config_flow.TandoorClient", new=cls),
    ):
        client = cls.return_value
        client.base_url = BASE
        client.async_get_meal_types = AsyncMock(return_value=[LUNCH, DINNER])
        client.async_get_meal_plan = AsyncMock(return_value=[])
        client.async_get_random_recipe = AsyncMock(return_value=recipe())
        yield client


def today() -> date:
    return dt_util.now().date()
