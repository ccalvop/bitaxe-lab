# collector

`bitaxe_collect.py` reads `GET /api/system/info` from an AxeOS miner and appends one row to a
CSV. Standard library only, Python 3.9+. Deployment options are in [deploy/](../deploy/).

```bash
# one sample, then exit (what the systemd timer runs)
python3 bitaxe_collect.py --url http://192.0.2.10 --csv metrics.csv

# loop every 300 s (what the container runs)
python3 bitaxe_collect.py --url http://192.0.2.10 --csv metrics.csv --interval 300
```

| Option | Environment variable | Default |
|--------|----------------------|---------|
| `--url` | `BITAXE_URL` | required |
| `--csv` | `BITAXE_CSV` | `metrics.csv` |
| `--interval` | `BITAXE_INTERVAL` | `0` (one sample) |
| `--timeout` | `BITAXE_TIMEOUT` | `15` s |
| `--expect-address` | `BITAXE_EXPECT_ADDRESS` | empty (check disabled) |

Behaviour:

- A miner that does not answer produces a row with `status=error:<Exception>` and empty
  metrics, so outages are visible in the data. The process still exits 0, so a timer never
  marks itself failed
- Rows are appended under an exclusive lock and synced to disk; the header is written once
- With `--expect-address`, a `WARNING PAYOUT MISMATCH` line is logged when the stratum user or
  the decoded coinbase pays anywhere else

The CSV columns are documented in [data/SCHEMA.md](../data/SCHEMA.md).

Tests: `make test` from the repository root. They run against [`tests/mock_axeos.py`](tests/mock_axeos.py),
which serves a real, anonymised API response from [`tests/fixtures/`](tests/fixtures/).
