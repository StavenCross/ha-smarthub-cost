"""Schema construction tests against the installed Home Assistant version."""

import asyncio

from homeassistant.core import HomeAssistant

from custom_components.smarthub_cost.config_flow import SmartHubCostConfigFlow


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
