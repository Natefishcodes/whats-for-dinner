"""Diagnostics for Tandoor Recipes (the API token is always redacted)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import TandoorConfigEntry

TO_REDACT = {CONF_API_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TandoorConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "source": data.source,
        "meal_plan_entries": [asdict(e) for e in data.entries],
        "dinner": asdict(data.dinner) if data.dinner else None,
        "suggestion": asdict(data.suggestion) if data.suggestion else None,
    }
