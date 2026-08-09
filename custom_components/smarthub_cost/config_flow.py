"""Config flow for SmartHub Cost."""

from __future__ import annotations

from datetime import date
from functools import partial
from typing import Any

import voluptuous as vol
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import get_metadata
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_EFFECTIVE_FROM,
    CONF_RATE,
    CONF_REPROCESS_DAYS,
    CONF_SOURCE_STATISTIC_ID,
    CONF_TARIFFS,
    DEFAULT_EFFECTIVE_FROM,
    DEFAULT_REPROCESS_DAYS,
    DOMAIN,
)
from .tariff import upsert_tariff


async def _validate_source(hass: HomeAssistant, statistic_id: str) -> None:
    """Validate that the selected statistic exists and has a sum."""
    metadata = await get_instance(hass).async_add_executor_job(
        partial(get_metadata, hass, statistic_ids={statistic_id})
    )
    if statistic_id not in metadata:
        raise ValueError("source_not_found")
    if not metadata[statistic_id][1]["has_sum"]:
        raise ValueError("source_has_no_sum")


class SmartHubCostConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a SmartHub Cost config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a cost calculation from an external energy statistic."""
        errors: dict[str, str] = {}
        if user_input is not None:
            source = user_input[CONF_SOURCE_STATISTIC_ID]
            try:
                await _validate_source(self.hass, source)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                await self.async_set_unique_id(source)
                self._abort_if_unique_id_configured()
                data = {
                    CONF_SOURCE_STATISTIC_ID: source,
                    CONF_TARIFFS: [
                        {
                            CONF_EFFECTIVE_FROM: user_input[CONF_EFFECTIVE_FROM],
                            CONF_RATE: user_input[CONF_RATE],
                        }
                    ],
                    CONF_REPROCESS_DAYS: user_input[CONF_REPROCESS_DAYS],
                }
                return self.async_create_entry(title="SmartHub energy cost", data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_SOURCE_STATISTIC_ID): selector.StatisticSelector(),
                vol.Required(CONF_RATE, default=0.1228): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=10, step="any", mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_EFFECTIVE_FROM, default=DEFAULT_EFFECTIVE_FROM
                ): selector.DateSelector(),
                vol.Required(
                    CONF_REPROCESS_DAYS, default=DEFAULT_REPROCESS_DAYS
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=90, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return SmartHubCostOptionsFlow(config_entry)


class SmartHubCostOptionsFlow(OptionsFlow):
    """Add or correct effective-dated tariff periods."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update tariff history and the correction window."""
        current_tariffs = self.config_entry.options.get(
            CONF_TARIFFS, self.config_entry.data[CONF_TARIFFS]
        )
        current_days = self.config_entry.options.get(
            CONF_REPROCESS_DAYS,
            self.config_entry.data.get(CONF_REPROCESS_DAYS, DEFAULT_REPROCESS_DAYS),
        )
        if user_input is not None:
            updated_tariffs = upsert_tariff(
                current_tariffs,
                user_input[CONF_EFFECTIVE_FROM],
                user_input[CONF_RATE],
            )
            return self.async_create_entry(
                title="",
                data={
                    CONF_TARIFFS: updated_tariffs,
                    CONF_REPROCESS_DAYS: user_input[CONF_REPROCESS_DAYS],
                },
            )

        latest_rate = current_tariffs[-1][CONF_RATE]
        schema = vol.Schema(
            {
                vol.Required(CONF_RATE, default=latest_rate): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=10, step="any", mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_EFFECTIVE_FROM, default=date.today().isoformat()
                ): selector.DateSelector(),
                vol.Required(
                    CONF_REPROCESS_DAYS, default=current_days
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=90, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
