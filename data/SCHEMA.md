# Data contract: `metrics.csv`

One row per sample, written by [`collector/bitaxe_collect.py`](../collector/bitaxe_collect.py)
every 5 minutes. Columns come from the AxeOS `GET /api/system/info` endpoint (firmware
`esp-miner` v2.15). The header is written once; rows are only ever appended.

| Column | Unit | API field | Notes |
|--------|------|-----------|-------|
| `timestamp_utc` | ISO 8601 | - | **Source of truth for time.** Always UTC |
| `timestamp_local` | `YYYY-MM-DD HH:MM:SS` | - | Host local time. In this dataset the host ran in UTC, so it equals `timestamp_utc` |
| `hashrate_ghs` | GH/s | `hashRate` | **An estimate**, derived from accepted shares. Noisy: average it, see [methodology](../docs/05-tuning-methodology.md) |
| `power_w` | W | `power` | DC power measured on the board, not at the wall |
| `voltage_mv` | mV | `voltage` | Input rail from the barrel-jack PSU (nominal 5000) |
| `temp_asic_c` | C | `temp` | `-1` while the ASIC is booting |
| `vr_temp_c` | C | `vrTemp` | Voltage regulator (TPS546) |
| `frequency_mhz` | MHz | `frequency` | Configured ASIC frequency |
| `core_voltage_mv` | mV | `coreVoltage` | Configured ASIC core voltage |
| `fan_rpm` | rpm | `fanrpm` | Measured |
| `fan_pct` | % | `fanspeed` | PWM duty |
| `shares_accepted` | count | `sharesAccepted` | Monotonic, **resets on reboot** |
| `shares_rejected` | count | `sharesRejected` | Monotonic, resets on reboot |
| `best_diff` | difficulty | `bestDiff` | All-time best share |
| `best_session_diff` | difficulty | `bestSessionDiff` | Best share since boot |
| `uptime_s` | s | `uptimeSeconds` | A decrease means a reboot |
| `using_fallback` | 0/1 | `isUsingFallbackStratum` | 1 if mining on the fallback pool |
| `stratum_url` | host | `stratumURL` | Active pool |
| `stratum_user` | `address.worker` | `stratumUser` | **Anonymised** in the published file |
| `coinbase_address` | address | `coinbaseOutputs[]` | Largest output of the decoded coinbase: who the block would pay. **Anonymised** |
| `coinbase_sats` | sat | `coinbaseOutputs[]` | Block subsidy plus fees of the current template |
| `wifi_rssi` | dBm | `wifiRSSI` | |
| `free_heap` | bytes | `freeHeap` | Flat over time means no memory leak |
| `version` | text | `version` | Firmware version |
| `status` | `ok` / `error:<Exception>` | - | Failed samples keep their timestamp and blank metrics, so outages stay visible |

## Published dataset

- 7,830 samples from 2026-09-05 to 2026-10-03, 3 failed
- The payout address and worker name are replaced with the BIP-173 example address
  `bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4` by [`analysis/sanitize.py`](../analysis/sanitize.py)
- `analysis/tests/test_published_data.py` fails the build if any other address appears

## Configurations covered

The same file contains every tuning step, so analyses must **segment by
`(frequency_mhz, core_voltage_mv, fan_pct)`** and drop the first 15 minutes after each change,
while the temperature settles. [`analysis/dataset.py`](../analysis/dataset.py) does both.
