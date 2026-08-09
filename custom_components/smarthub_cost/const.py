"""Constants for SmartHub Cost."""

from __future__ import annotations

DOMAIN = "smarthub_cost"

CONF_SOURCE_STATISTIC_ID = "source_statistic_id"
CONF_TARIFFS = "tariffs"
CONF_RATE = "rate"
CONF_EFFECTIVE_FROM = "effective_from"
CONF_REPROCESS_DAYS = "reprocess_days"

DEFAULT_EFFECTIVE_FROM = "1970-01-01"
DEFAULT_REPROCESS_DAYS = 7
DEFAULT_UPDATE_INTERVAL_HOURS = 6


def cost_statistic_id(source_statistic_id: str) -> str:
    """Return the deterministic external cost statistic ID for a source."""
    safe_source = source_statistic_id.replace(":", "_").replace(".", "_")
    return f"{DOMAIN}:{safe_source}_cost"
