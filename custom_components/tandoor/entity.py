"""Base entity for Tandoor Recipes."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TandoorCoordinator


class TandoorEntity(CoordinatorEntity[TandoorCoordinator]):
    """Groups every entity under one "Tandoor Recipes" service device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TandoorCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Tandoor Recipes",
            manufacturer="Tandoor",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.client.base_url,
        )
