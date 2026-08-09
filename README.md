# SmartHub Cost

SmartHub Cost is a Home Assistant companion integration for utility data imported as external long-term statistics. It leaves the source kWh statistic untouched and creates a timestamp-aligned cost statistic for the Energy dashboard.

It was built for [SmartHub Coop Energy](https://github.com/gagata/ha-smarthub-energy-sensor), whose delayed hourly usage is available as an external statistic but cannot use Home Assistant's entity-based fixed-price calculation.

## What it does

- Reads an hourly external energy statistic from Home Assistant Recorder.
- Calculates each hour as `kWh x effective rate`.
- Stores hourly cost in `state` and cumulative cost in `sum` using Home Assistant's external-statistics API.
- Backfills all retained hourly history on setup or tariff changes.
- Reprocesses the latest seven days every six hours so delayed utility corrections are reflected.
- Preserves effective-dated rates instead of retroactively applying a new price to old usage.

Fixed customer charges, taxes, and bill adjustments are intentionally not spread across hourly consumption. The resulting statistic represents the variable per-kWh charge.

## Installation

1. In HACS, add `stavencross/ha-smarthub-cost` as a custom integration repository.
2. Download SmartHub Cost and restart Home Assistant.
3. Add **SmartHub Cost** under **Settings > Devices & services**.
4. Select the hourly SmartHub statistic and enter the per-kWh rate.
5. In the Energy dashboard, use the SmartHub hourly statistic for grid consumption and the generated `smarthub_cost:*_cost` statistic for cost.

The initial effective date defaults to 1970 so the first rate covers all retained data. When a rate changes, use **Configure** and add the new rate with its actual effective date.

## Compatibility

- Home Assistant Core 2026.8 or newer
- Recorder enabled
- An hourly external statistic with `state` and cumulative `sum`

## Development

```bash
python -m pytest
python -m compileall custom_components
```

The tariff calculation is isolated in `tariff.py` and covered without requiring a running Home Assistant instance.
