"""Setup, entities and the dinner-picking logic."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.tandoor.api import TandoorAuthError, TandoorConnectionError
from custom_components.tandoor.const import CONF_DINNER_MEAL_TYPES

from .conftest import DINNER, LUNCH, entry_today, recipe

SENSOR = "sensor.tandoor_recipes_dinner_tonight"
MEALS = "sensor.tandoor_recipes_meals_today"
IMAGE = "image.tandoor_recipes_dinner_photo"
BUTTON = "button.tandoor_recipes_suggest_another"
CALENDAR = "calendar.tandoor_recipes_meal_plan"


async def _setup(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_suggestion_when_nothing_planned(hass: HomeAssistant, config_entry, mock_client) -> None:
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(SENSOR)
    assert state.state == "Salsa Mexicana"
    assert state.attributes["source"] == "suggestion"
    assert state.attributes["recipe_url"].endswith("/recipe/63")
    assert state.attributes["total_time"] == 30
    assert hass.states.get(MEALS).state == "0"
    assert hass.states.get(IMAGE) is not None
    assert hass.states.get(CALENDAR) is not None


async def test_planned_dinner_beats_lunch(hass: HomeAssistant, config_entry, mock_client) -> None:
    mock_client.async_get_meal_plan.return_value = [
        entry_today(LUNCH, recipe(5, "Turkey Club"), eid=1),
        entry_today(DINNER, recipe(12, "Chicken Parm"), eid=2),
    ]
    await _setup(hass, config_entry)

    state = hass.states.get(SENSOR)
    assert state.state == "Chicken Parm"
    assert state.attributes["source"] == "meal_plan"
    assert state.attributes["meal_type"] == "Dinner"
    assert state.attributes["servings"] == 2
    assert hass.states.get(MEALS).state == "2"


async def test_custom_dinner_meal_type(hass: HomeAssistant, config_entry, mock_client) -> None:
    mock_client.async_get_meal_plan.return_value = [entry_today(LUNCH, recipe(5, "Turkey Club"))]
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={CONF_DINNER_MEAL_TYPES: ["Lunch"]})
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR).state == "Turkey Club"
    assert hass.states.get(SENSOR).attributes["source"] == "meal_plan"


async def test_suggest_another(hass: HomeAssistant, config_entry, mock_client) -> None:
    await _setup(hass, config_entry)
    mock_client.async_get_random_recipe.return_value = recipe(70, "Pad Kra Pao")
    await hass.services.async_call("button", "press", {"entity_id": BUTTON}, blocking=True)
    assert hass.states.get(SENSOR).state == "Pad Kra Pao"


async def test_auth_failure_starts_reauth(hass: HomeAssistant, config_entry, mock_client) -> None:
    mock_client.async_get_meal_plan.side_effect = TandoorAuthError("nope")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(flow["context"]["source"] == "reauth" for flow in hass.config_entries.flow.async_progress())


async def test_unreachable_retries(hass: HomeAssistant, config_entry, mock_client) -> None:
    mock_client.async_get_meal_plan.side_effect = TandoorConnectionError("down")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload(hass: HomeAssistant, config_entry, mock_client) -> None:
    await _setup(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
