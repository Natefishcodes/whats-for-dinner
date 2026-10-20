"""Meal plan calendar."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import MealPlanEntry, TandoorError
from .coordinator import TandoorConfigEntry, local_start
from .entity import TandoorEntity

PARALLEL_UPDATES = 0
DEFAULT_MEAL_LENGTH = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TandoorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([TandoorMealPlanCalendar(entry.runtime_data, "meal_plan")])


def to_event(entry: MealPlanEntry) -> CalendarEvent:
    """Turn a meal plan entry into a calendar event.

    Tandoor stores most entries at midnight; when the meal type has a time
    (e.g. Dinner 18:00) the event is placed then, otherwise it is all-day.
    """
    start = local_start(entry)
    meal = entry.meal_type.name if entry.meal_type else None
    summary = f"{meal}: {entry.name}" if meal and meal.casefold() != entry.name.casefold() else entry.name
    description = (
        "\n".join(part for part in (entry.note, entry.recipe.url if entry.recipe else None) if part) or None
    )
    uid = str(entry.id)

    if start.time() == time.min:
        if entry.meal_type and entry.meal_type.time:
            timed = datetime.combine(start.date(), entry.meal_type.time, tzinfo=start.tzinfo)
            return CalendarEvent(timed, timed + DEFAULT_MEAL_LENGTH, summary, description, uid=uid)
        return CalendarEvent(start.date(), start.date() + timedelta(days=1), summary, description, uid=uid)

    end = dt_util.as_local(entry.end) if entry.end and entry.end.tzinfo else None
    if end is None or end <= start:
        end = start + DEFAULT_MEAL_LENGTH
    return CalendarEvent(start, end, summary, description, uid=uid)


def _event_end(event: CalendarEvent) -> datetime:
    return event.end_datetime_local


class TandoorMealPlanCalendar(TandoorEntity, CalendarEntity):
    """The Tandoor meal plan as a calendar."""

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next meal in the coordinator's look-ahead window."""
        now = dt_util.now()
        upcoming = [ev for ev in map(to_event, self.coordinator.data.entries) if _event_end(ev) > now]
        return min(upcoming, key=lambda ev: ev.start_datetime_local, default=None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        try:
            entries = await self.coordinator.client.async_get_meal_plan(
                dt_util.as_local(start_date).date(), dt_util.as_local(end_date).date()
            )
        except TandoorError as err:
            raise HomeAssistantError(f"Could not load the Tandoor meal plan: {err}") from err
        events = [to_event(e) for e in entries]
        return [ev for ev in events if ev.start_datetime_local < end_date and _event_end(ev) > start_date]
