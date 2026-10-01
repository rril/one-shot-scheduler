"""Config flow for One Shot Scheduler."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_OVERVIEW_SHORTCUTS, DOMAIN


class OneShotSchedulerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure One Shot Scheduler."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="One Shot Scheduler", data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "OneShotSchedulerOptionsFlow":
        """Create the options flow."""
        return OneShotSchedulerOptionsFlow()


class OneShotSchedulerOptionsFlow(OptionsFlowWithReload):
    """Configure automatic Overview shortcut entities."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = list(self.config_entry.options.get(CONF_OVERVIEW_SHORTCUTS, []))
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_OVERVIEW_SHORTCUTS,
                    default=current,
                ): EntitySelector(
                    EntitySelectorConfig(domain="switch", multiple=True)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
