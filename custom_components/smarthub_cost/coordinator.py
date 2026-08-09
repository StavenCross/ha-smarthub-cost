"""Recorder statistics coordinator for SmartHub Cost."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_metadata,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_REPROCESS_DAYS,
    CONF_SOURCE_STATISTIC_ID,
    CONF_TARIFFS,
    DEFAULT_REPROCESS_DAYS,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
    cost_statistic_id,
)
from .tariff import build_cost_rows

_LOGGER = logging.getLogger(__name__)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class SmartHubCostCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Synchronize a derived cost statistic with an hourly usage statistic."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the cost coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(hours=DEFAULT_UPDATE_INTERVAL_HOURS),
        )
        self.entry = entry
        self.source_statistic_id = entry.data[CONF_SOURCE_STATISTIC_ID]
        self.cost_statistic_id = cost_statistic_id(self.source_statistic_id)
        self._full_rebuild = True

    async def _async_update_data(self) -> dict[str, Any]:
        """Read usage statistics and upsert the matching cost rows."""
        try:
            return await self._async_sync_statistics()
        except Exception as err:
            raise UpdateFailed(f"Unable to synchronize cost statistics: {err}") from err

    async def _async_statistics(
        self,
        start: datetime,
        end: datetime | None,
        statistic_id: str,
        types: set[str],
    ) -> list[dict[str, Any]]:
        """Read hourly long-term statistics without blocking the event loop."""
        result = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            start,
            end,
            {statistic_id},
            "hour",
            None,
            types,
        )
        return result.get(statistic_id, [])

    async def _async_source_metadata(self) -> StatisticMetaData:
        """Fetch and validate source statistic metadata."""
        metadata = await get_instance(self.hass).async_add_executor_job(
            partial(
                get_metadata,
                self.hass,
                statistic_ids={self.source_statistic_id},
            )
        )
        if self.source_statistic_id not in metadata:
            raise ValueError(
                f"Source statistic {self.source_statistic_id} was not found"
            )
        source_metadata = metadata[self.source_statistic_id][1]
        if not source_metadata["has_sum"]:
            raise ValueError("Source statistic must provide a cumulative sum")
        return source_metadata

    async def _async_sync_statistics(self) -> dict[str, Any]:
        """Calculate a full backfill once, then refresh a rolling correction window."""
        source_metadata = await self._async_source_metadata()
        now = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
        reprocess_days = int(
            self.entry.options.get(
                CONF_REPROCESS_DAYS,
                self.entry.data.get(CONF_REPROCESS_DAYS, DEFAULT_REPROCESS_DAYS),
            )
        )

        start = _EPOCH
        starting_sum = 0.0
        if not self._full_rebuild:
            start = now - timedelta(days=reprocess_days)
            previous_cost = await self._async_statistics(
                start - timedelta(hours=1), start, self.cost_statistic_id, {"sum"}
            )
            if previous_cost and previous_cost[-1].get("sum") is not None:
                starting_sum = float(previous_cost[-1]["sum"])
            else:
                start = _EPOCH

        usage_rows = await self._async_statistics(
            start, None, self.source_statistic_id, {"state", "sum"}
        )
        raw_tariffs = self.entry.options.get(
            CONF_TARIFFS, self.entry.data[CONF_TARIFFS]
        )
        cost_rows = build_cost_rows(
            usage_rows,
            raw_tariffs,
            self.hass.config.time_zone,
            starting_sum=starting_sum,
        )

        source_name = source_metadata.get("name") or self.source_statistic_id
        cost_metadata = StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"{source_name} cost",
            source=DOMAIN,
            statistic_id=self.cost_statistic_id,
            unit_class=None,
            unit_of_measurement=None,
        )
        statistics = [StatisticData(**row) for row in cost_rows]
        async_add_external_statistics(self.hass, cost_metadata, statistics)
        self._full_rebuild = False

        latest = cost_rows[-1] if cost_rows else None
        _LOGGER.info(
            "Synchronized %s cost rows from %s to %s",
            len(cost_rows),
            self.source_statistic_id,
            self.cost_statistic_id,
        )
        return {
            "source_statistic_id": self.source_statistic_id,
            "cost_statistic_id": self.cost_statistic_id,
            "rows_written": len(cost_rows),
            "latest_start": latest["start"].isoformat() if latest else None,
            "latest_sum": latest["sum"] if latest else None,
        }
