"""Schema construction tests against the installed Home Assistant version."""

import asyncio
from types import SimpleNamespace

from homeassistant.core import HomeAssistant

from custom_components.smarthub_cost.config_flow import (
    SmartHubCostConfigFlow,
    SmartHubCostOptionsFlow,
)


def test_user_form_schema_constructs() -> None:
    """Ensure Home Assistant accepts every selector configuration."""

    async def render_form() -> dict:
        hass = HomeAssistant(".")
        flow = SmartHubCostConfigFlow()
        flow.hass = hass
        return await flow.async_step_user()

    result = asyncio.run(render_form())

    assert result["type"] == "form"
    assert result["step_id"] == "user"


def test_options_flow_does_not_assign_read_only_config_entry() -> None:
    """Ensure construction is compatible with HA's managed config_entry property."""
    entry = SimpleNamespace(options={"reprocess_days": 7})

    flow = SmartHubCostOptionsFlow(entry)

    assert flow._initial_options == {"reprocess_days": 7}
