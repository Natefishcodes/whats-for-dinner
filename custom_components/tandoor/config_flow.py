"""Config flow for Tandoor Recipes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    MealType,
    TandoorAuthError,
    TandoorClient,
    TandoorConnectionError,
    TandoorError,
    normalize_url,
)
from .const import (
    CONF_DINNER_MEAL_TYPES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import TandoorConfigEntry

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required(CONF_API_TOKEN): _PASSWORD,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): _PASSWORD})


async def _async_validate(hass: HomeAssistant, url: str, token: str, verify_ssl: bool) -> list[MealType]:
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    return await TandoorClient(session, url, token).async_get_meal_types()


def _errors_for(err: TandoorError) -> dict[str, str]:
    if isinstance(err, TandoorAuthError):
        return {"base": "invalid_auth"}
    if isinstance(err, TandoorConnectionError):
        return {"base": "cannot_connect"}
    LOGGER.exception("Unexpected response from Tandoor")
    return {"base": "unknown"}


class TandoorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a Tandoor instance with its URL and an API token."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            try:
                await _async_validate(self.hass, url, user_input[CONF_API_TOKEN], user_input[CONF_VERIFY_SSL])
            except TandoorError as err:
                errors = _errors_for(err)
            else:
                return self.async_create_entry(
                    title=urlparse(url).netloc or url,
                    data={**user_input, CONF_URL: url},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _async_validate(
                    self.hass,
                    entry.data[CONF_URL],
                    user_input[CONF_API_TOKEN],
                    entry.data.get(CONF_VERIFY_SSL, True),
                )
            except TandoorError as err:
                errors = _errors_for(err)
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"url": entry.data[CONF_URL]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: TandoorConfigEntry) -> TandoorOptionsFlow:
        return TandoorOptionsFlow()


class TandoorOptionsFlow(OptionsFlow):
    """Pick which meal types count as dinner, and how often to poll."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current: list[str] = self.config_entry.options.get(CONF_DINNER_MEAL_TYPES, [])
        names: set[str] = set(current)
        try:
            coordinator = self.config_entry.runtime_data
            names |= {mt.name for mt in await coordinator.client.async_get_meal_types() if mt.name}
        except (AttributeError, TandoorError):
            LOGGER.debug("Could not load meal types for the options form")

        schema = vol.Schema(
            {
                vol.Optional(CONF_DINNER_MEAL_TYPES, default=current): SelectSelector(
                    SelectSelectorConfig(
                        options=sorted(names, key=str.casefold),
                        multiple=True,
                        custom_value=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
