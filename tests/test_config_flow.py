"""Config, reauth and options flows."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.tandoor.api import TandoorAuthError, TandoorConnectionError
from custom_components.tandoor.const import CONF_DINNER_MEAL_TYPES, CONF_SCAN_INTERVAL, DOMAIN

USER_INPUT = {CONF_URL: "tandoor.local:8080/", CONF_API_TOKEN: "tda_secret", CONF_VERIFY_SSL: True}


async def test_user_flow_creates_entry(hass: HomeAssistant, mock_client) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "tandoor.local:8080"
    # The URL is normalised: scheme added, trailing slash removed.
    assert result["data"][CONF_URL] == "http://tandoor.local:8080"
    assert result["result"].unique_id == "http://tandoor.local:8080"


async def test_user_flow_errors_then_recovers(hass: HomeAssistant, mock_client) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    mock_client.async_get_meal_types.side_effect = TandoorAuthError("bad")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.async_get_meal_types.side_effect = TandoorConnectionError("down")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.async_get_meal_types.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_aborts(hass: HomeAssistant, mock_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_URL: config_entry.data[CONF_URL]}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_token(hass: HomeAssistant, mock_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_TOKEN: "tda_new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_API_TOKEN] == "tda_new"


async def test_options_flow(hass: HomeAssistant, mock_client, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DINNER_MEAL_TYPES: ["Dinner"], CONF_SCAN_INTERVAL: 30}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_DINNER_MEAL_TYPES] == ["Dinner"]
