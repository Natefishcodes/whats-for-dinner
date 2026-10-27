"""Sensors: tonight's dinner and today's meal count."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import TandoorConfigEntry, local_start
from .entity import TandoorEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TandoorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            TandoorDinnerTonightSensor(coordinator, "dinner_tonight"),
            TandoorMealsTodaySensor(coordinator, "meals_today"),
        ]
    )


class TandoorDinnerTonightSensor(TandoorEntity, SensorEntity):
    """Name of tonight's planned dinner, or today's suggestion when nothing is planned."""

    # Long text the recorder does not need to keep a history of.
    _unrecorded_attributes = frozenset({"description", "keywords", "note", "upcoming"})

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if data.dinner is not None:
            return data.dinner.name[:255]
        if data.suggestion is not None:
            return data.suggestion.name[:255]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        recipe = data.tonight_recipe
        attrs: dict[str, Any] = {"source": data.source}
        if data.dinner is not None:
            attrs["meal_type"] = data.dinner.meal_type.name if data.dinner.meal_type else None
            attrs["planned_for"] = local_start(data.dinner).isoformat()
            attrs["note"] = data.dinner.note
            servings = data.dinner.servings or (recipe.servings if recipe else None)
        else:
            servings = recipe.servings if recipe else None
        if recipe is not None:
            attrs.update(
                recipe_id=recipe.id,
                recipe_url=recipe.url,
                image_url=recipe.image,
                description=recipe.description,
                working_time=recipe.working_time,
                waiting_time=recipe.waiting_time,
                total_time=recipe.total_time,
                rating=recipe.rating,
                keywords=recipe.keywords,
            )
        attrs["servings"] = servings
        # One row per day for the card's 3-day and week views; name is None when nothing is planned.
        attrs["upcoming"] = [
            {
                "date": day.isoformat(),
                "name": entry.name if entry else None,
                "recipe_url": entry.recipe.url if entry and entry.recipe else None,
                "image_url": entry.recipe.image if entry and entry.recipe else None,
                "total_time": entry.recipe.total_time if entry and entry.recipe else None,
            }
            for day, entry in data.dinners_ahead
        ]
        return attrs


class TandoorMealsTodaySensor(TandoorEntity, SensorEntity):
    """How many meals are planned today, with a compact list as an attribute."""

    _attr_native_unit_of_measurement = "meals"
    _unrecorded_attributes = frozenset({"meals"})

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.entries_on(dt_util.now().date()))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "meals": [
                {
                    "meal_type": entry.meal_type.name if entry.meal_type else None,
                    "name": entry.name,
                    "recipe_url": entry.recipe.url if entry.recipe else None,
                    "start": local_start(entry).isoformat(),
                }
                for entry in self.coordinator.data.entries_on(dt_util.now().date())
            ]
        }
