"""Button: suggest a different dinner."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TandoorConfigEntry
from .entity import TandoorEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TandoorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([TandoorSuggestButton(entry.runtime_data, "suggest_another")])


class TandoorSuggestButton(TandoorEntity, ButtonEntity):
    """Pick another random recipe for the dinner suggestion."""

    async def async_press(self) -> None:
        await self.coordinator.async_suggest_another()
