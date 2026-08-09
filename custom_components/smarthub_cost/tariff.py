"""Pure tariff calculations for SmartHub Cost."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from .const import CONF_EFFECTIVE_FROM, CONF_RATE

MONEY_PRECISION = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class TariffPeriod:
    """A per-kWh tariff beginning on a local calendar date."""

    effective_from: date
    rate: Decimal


def normalize_tariffs(raw_tariffs: Iterable[Mapping[str, Any]]) -> list[TariffPeriod]:
    """Validate, deduplicate, and sort persisted tariff periods."""
    by_date: dict[date, TariffPeriod] = {}
    for raw in raw_tariffs:
        effective_from = date.fromisoformat(str(raw[CONF_EFFECTIVE_FROM]))
        try:
            rate = Decimal(str(raw[CONF_RATE]))
        except InvalidOperation as err:
            raise ValueError("Tariff rate must be numeric") from err
        if not rate.is_finite() or rate < 0:
            raise ValueError("Tariff rate must be a non-negative finite number")
        by_date[effective_from] = TariffPeriod(effective_from, rate)
    if not by_date:
        raise ValueError("At least one tariff period is required")
    return [by_date[key] for key in sorted(by_date)]


def serialize_tariffs(tariffs: Iterable[TariffPeriod]) -> list[dict[str, Any]]:
    """Convert tariff periods to config-entry-safe dictionaries."""
    return [
        {
            CONF_EFFECTIVE_FROM: tariff.effective_from.isoformat(),
            CONF_RATE: float(tariff.rate),
        }
        for tariff in tariffs
    ]


def upsert_tariff(
    raw_tariffs: Iterable[Mapping[str, Any]], effective_from: str, rate: Any
) -> list[dict[str, Any]]:
    """Insert or replace a tariff period by effective date."""
    updated = list(raw_tariffs)
    updated.append({CONF_EFFECTIVE_FROM: effective_from, CONF_RATE: rate})
    return serialize_tariffs(normalize_tariffs(updated))


def _as_utc_datetime(value: datetime | float | int) -> datetime:
    """Normalize a recorder start value to an aware UTC datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Statistic timestamp must be timezone-aware")
        return value.astimezone(UTC)
    return datetime.fromtimestamp(float(value), tz=UTC)


def _timestamp(value: datetime | float | int) -> float:
    """Return a sortable timestamp for a recorder start value."""
    return _as_utc_datetime(value).timestamp()


def _rate_for(
    start: datetime, tariffs: list[TariffPeriod], local_timezone: ZoneInfo
) -> Decimal | None:
    """Return the tariff effective at an hourly statistic timestamp."""
    local_date = start.astimezone(local_timezone).date()
    matching = [
        tariff.rate for tariff in tariffs if tariff.effective_from <= local_date
    ]
    return matching[-1] if matching else None


def build_cost_rows(
    usage_rows: Iterable[Mapping[str, Any]],
    raw_tariffs: Iterable[Mapping[str, Any]],
    timezone_name: str,
    *,
    starting_sum: float | Decimal = 0,
) -> list[dict[str, Any]]:
    """Create hourly cost state and cumulative sum rows from hourly kWh rows."""
    tariffs = normalize_tariffs(raw_tariffs)
    local_timezone = ZoneInfo(timezone_name)
    cumulative = Decimal(str(starting_sum))
    result: list[dict[str, Any]] = []

    for usage in sorted(usage_rows, key=lambda row: _timestamp(row["start"])):
        if usage.get("state") is None:
            continue
        start = _as_utc_datetime(usage["start"])
        rate = _rate_for(start, tariffs, local_timezone)
        if rate is None:
            continue
        try:
            consumption = Decimal(str(usage["state"]))
        except InvalidOperation:
            continue
        if not consumption.is_finite():
            continue
        consumption = max(consumption, Decimal(0))
        hourly_cost = (consumption * rate).quantize(
            MONEY_PRECISION, rounding=ROUND_HALF_UP
        )
        cumulative = (cumulative + hourly_cost).quantize(
            MONEY_PRECISION, rounding=ROUND_HALF_UP
        )
        result.append(
            {"start": start, "state": float(hourly_cost), "sum": float(cumulative)}
        )

    return result
