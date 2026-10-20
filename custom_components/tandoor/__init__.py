"""The Tandoor Recipes integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import TandoorClient
from .const import CARD_FILENAME, CARD_URL_BASE, DATA_CARD_REGISTERED, DOMAIN
from .coordinator import TandoorConfigEntry, TandoorCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.CALENDAR, Platform.IMAGE, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the bundled dinner card so users get it without a separate install."""
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    # Both are part of every normal install; skip quietly where they are not loaded (e.g. tests).
    if hass.data.get(DATA_CARD_REGISTERED) or hass.http is None or "frontend" not in hass.config.components:
        return
    integration = await async_get_integration(hass, DOMAIN)
    card_path = Path(__file__).parent / "frontend" / CARD_FILENAME
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_BASE, str(card_path.parent), True)]
    )
    # The version query busts browser caches when the integration is updated.
    add_extra_js_url(hass, f"{CARD_URL_BASE}/{CARD_FILENAME}?v={integration.version}")
    hass.data[DATA_CARD_REGISTERED] = True


async def async_setup_entry(hass: HomeAssistant, entry: TandoorConfigEntry) -> bool:
    """Set up Tandoor Recipes from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client = TandoorClient(session, entry.data[CONF_URL], entry.data[CONF_API_TOKEN])
    coordinator = TandoorCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: TandoorConfigEntry) -> None:
    """Options changed (dinner meal types, poll interval): reload."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TandoorConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
