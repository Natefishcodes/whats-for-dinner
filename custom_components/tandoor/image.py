"""Photo of tonight's dinner, served through Home Assistant.

Proxying through HA means the photo loads anywhere HA does (including remote
access), not only on the network that can reach Tandoor.
"""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import TandoorConfigEntry, TandoorCoordinator
from .entity import TandoorEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TandoorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([TandoorDinnerImage(hass, entry.runtime_data, "dinner_photo")])


class TandoorDinnerImage(TandoorEntity, ImageEntity):
    """Recipe photo for whatever the dinner sensor is showing."""

    def __init__(self, hass: HomeAssistant, coordinator: TandoorCoordinator, key: str) -> None:
        TandoorEntity.__init__(self, coordinator, key)
        ImageEntity.__init__(self, hass, verify_ssl=coordinator.config_entry.data.get(CONF_VERIFY_SSL, True))
        self._set_url()

    def _current_url(self) -> str | None:
        recipe = self.coordinator.data.tonight_recipe
        return recipe.image if recipe else None

    def _set_url(self) -> None:
        url = self._current_url()
        if url != getattr(self, "_attr_image_url", None):
            self._attr_image_url = url
            self._attr_image_last_updated = dt_util.utcnow()
            self._cached_image = None

    @property
    def available(self) -> bool:
        return super().available and self._attr_image_url is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        self._set_url()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        if not self._attr_image_url:
            return None
        return await super().async_image()
