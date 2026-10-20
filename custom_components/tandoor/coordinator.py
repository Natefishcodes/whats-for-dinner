"""Data coordinator for Tandoor Recipes."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import MealPlanEntry, Recipe, TandoorAuthError, TandoorClient, TandoorError
from .const import (
    CONF_DINNER_MEAL_TYPES,
    CONF_SCAN_INTERVAL,
    DEFAULT_DINNER_NAMES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    LOOKAHEAD_DAYS,
    SOURCE_MEAL_PLAN,
    SOURCE_NONE,
    SOURCE_SUGGESTION,
)

type TandoorConfigEntry = ConfigEntry[TandoorCoordinator]


@dataclass(frozen=True, slots=True)
class TandoorData:
    """Snapshot shared by all entities."""

    entries: list[MealPlanEntry]
    dinner: MealPlanEntry | None
    suggestion: Recipe | None

    @property
    def source(self) -> str:
        if self.dinner is not None:
            return SOURCE_MEAL_PLAN
        if self.suggestion is not None:
            return SOURCE_SUGGESTION
        return SOURCE_NONE

    @property
    def tonight_recipe(self) -> Recipe | None:
        """The recipe the dinner card shows: planned first, then the suggestion."""
        if self.dinner is not None:
            return self.dinner.recipe
        return self.suggestion

    def entries_on(self, day: date) -> list[MealPlanEntry]:
        return [e for e in self.entries if local_start(e).date() == day]


def local_start(entry: MealPlanEntry) -> datetime:
    """Entry start in Home Assistant's time zone (naive values are taken as local)."""
    start = entry.start
    if start.tzinfo is None:
        start = start.replace(tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_local(start)


class TandoorCoordinator(DataUpdateCoordinator[TandoorData]):
    """Polls the meal plan; keeps one dinner suggestion per day."""

    config_entry: TandoorConfigEntry

    def __init__(self, hass: HomeAssistant, entry: TandoorConfigEntry, client: TandoorClient) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        )
        self.client = client
        self._suggestion: Recipe | None = None
        self._suggestion_day: date | None = None

    @property
    def dinner_meal_types(self) -> set[str]:
        chosen = self.config_entry.options.get(CONF_DINNER_MEAL_TYPES) or []
        return {name.casefold() for name in chosen} or set(DEFAULT_DINNER_NAMES)

    def _pick_dinner(self, entries: list[MealPlanEntry], today: date) -> MealPlanEntry | None:
        names = self.dinner_meal_types
        for entry in entries:
            if (
                local_start(entry).date() == today
                and entry.meal_type is not None
                and entry.meal_type.name.casefold() in names
            ):
                return entry
        return None

    async def _async_update_data(self) -> TandoorData:
        today = dt_util.now().date()
        try:
            entries = await self.client.async_get_meal_plan(today, today + timedelta(days=LOOKAHEAD_DAYS))
            if self._suggestion_day != today:
                # A fresh idea each day; "Suggest another" replaces it on demand.
                self._suggestion = await self.client.async_get_random_recipe()
                self._suggestion_day = today
        except TandoorAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TandoorError as err:
            raise UpdateFailed(str(err)) from err

        return TandoorData(
            entries=entries,
            dinner=self._pick_dinner(entries, today),
            suggestion=self._suggestion,
        )

    async def async_suggest_another(self) -> None:
        """Replace the suggestion with a different random recipe."""
        previous = self._suggestion.id if self._suggestion else None
        try:
            recipe = await self.client.async_get_random_recipe()
            # Small libraries can repeat; try once more for something different.
            if recipe is not None and recipe.id == previous:
                recipe = await self.client.async_get_random_recipe() or recipe
        except TandoorAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise UpdateFailed(str(err)) from err
        except TandoorError as err:
            raise UpdateFailed(str(err)) from err
        self._suggestion = recipe
        self._suggestion_day = dt_util.now().date()
        if self.data is not None:
            self.async_set_updated_data(replace(self.data, suggestion=recipe))
