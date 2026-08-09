"""Tests for effective-dated hourly tariff calculations."""

from datetime import UTC, datetime

from custom_components.smarthub_cost.tariff import build_cost_rows, upsert_tariff


def test_build_cost_rows_uses_effective_local_date() -> None:
    tariffs = [
        {"effective_from": "1970-01-01", "rate": 0.10},
        {"effective_from": "2026-08-01", "rate": 0.12},
    ]
    usage = [
        {"start": datetime(2026, 8, 1, 4, tzinfo=UTC), "state": 2.0},
        {"start": datetime(2026, 8, 1, 5, tzinfo=UTC), "state": 3.0},
    ]

    rows = build_cost_rows(usage, tariffs, "America/Chicago")

    assert rows[0]["state"] == 0.2
    assert rows[0]["sum"] == 0.2
    assert rows[1]["state"] == 0.36
    assert rows[1]["sum"] == 0.56


def test_build_cost_rows_preserves_incremental_sum_and_clamps_negative_usage() -> None:
    rows = build_cost_rows(
        [
            {"start": 1786208400, "state": -1},
            {"start": 1786212000, "state": 1.25},
        ],
        [{"effective_from": "1970-01-01", "rate": 0.1228}],
        "America/Chicago",
        starting_sum=10,
    )

    assert rows[0]["state"] == 0.0
    assert rows[0]["sum"] == 10.0
    assert rows[1]["state"] == 0.1535
    assert rows[1]["sum"] == 10.1535


def test_upsert_tariff_replaces_same_date_and_sorts() -> None:
    updated = upsert_tariff(
        [
            {"effective_from": "2026-08-01", "rate": 0.12},
            {"effective_from": "1970-01-01", "rate": 0.10},
        ],
        "2026-08-01",
        0.13,
    )

    assert updated == [
        {"effective_from": "1970-01-01", "rate": 0.1},
        {"effective_from": "2026-08-01", "rate": 0.13},
    ]
