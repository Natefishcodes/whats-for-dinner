"""Meal plan entries → calendar events."""

from __future__ import annotations

from datetime import time, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.tandoor.api import MealPlanEntry, MealType
from custom_components.tandoor.calendar import to_event

from .conftest import DINNER, entry_today, recipe


async def test_midnight_entry_uses_meal_type_time(hass: HomeAssistant) -> None:
    timed_dinner = MealType(id=3, name="Dinner", time=time(18, 0))
    event = to_event(entry_today(timed_dinner, recipe(12, "Chicken Parm")))
    assert event.summary == "Dinner: Chicken Parm"
    assert event.start.time() == time(18, 0)
    assert event.end - event.start == timedelta(hours=1)
    assert event.description.endswith("/recipe/12")


async def test_midnight_entry_without_time_is_all_day(hass: HomeAssistant) -> None:
    event = to_event(entry_today(DINNER, recipe()))
    assert event.all_day
    assert event.end == event.start + timedelta(days=1)


async def test_timed_entry_keeps_its_time(hass: HomeAssistant) -> None:
    start = dt_util.start_of_local_day() + timedelta(hours=19, minutes=30)
    entry = MealPlanEntry(id=4, title="Pizza night", start=start, end=None, meal_type=None, recipe=None)
    event = to_event(entry)
    assert event.summary == "Pizza night"
    assert event.start == start
    assert event.end == start + timedelta(hours=1)
    assert event.description is None


async def test_calendar_entity_lists_events(hass: HomeAssistant, config_entry, mock_client) -> None:
    mock_client.async_get_meal_plan.return_value = [entry_today(DINNER, recipe(12, "Chicken Parm"))]
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    start = dt_util.start_of_local_day()
    result = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": "calendar.tandoor_recipes_meal_plan",
            "start_date_time": start,
            "end_date_time": start + timedelta(days=2),
        },
        blocking=True,
        return_response=True,
    )
    events = result["calendar.tandoor_recipes_meal_plan"]["events"]
    assert [e["summary"] for e in events] == ["Dinner: Chicken Parm"]
