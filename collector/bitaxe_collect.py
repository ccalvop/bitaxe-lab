#!/usr/bin/env python3
"""Sample a Bitaxe (AxeOS) miner and append one row per sample to a CSV file.

Design goals:
  * Never crash and never corrupt the CSV. If the miner does not answer, the row is
    still written with empty metrics and status=error, so outages show up as gaps.
  * Standard library only, so it runs on a bare Debian LXC or a slim container.
  * One sample per invocation (systemd timer) or a loop (--interval, for containers).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import json
import logging
import os
import signal
import sys
import threading
import urllib.request
from typing import Any

API_PATH = "/api/system/info"
DEFAULT_TIMEOUT = 15

FIELDS = [
    "timestamp_utc", "timestamp_local",
    "hashrate_ghs", "power_w", "voltage_mv",
    "temp_asic_c", "vr_temp_c",
    "frequency_mhz", "core_voltage_mv",
    "fan_rpm", "fan_pct",
    "shares_accepted", "shares_rejected",
    "best_diff", "best_session_diff",
    "uptime_s", "using_fallback",
    "stratum_url", "stratum_user",
    "coinbase_address", "coinbase_sats",
    "wifi_rssi", "free_heap", "version",
    "status",
]  # fmt: skip

# CSV column -> AxeOS API field
API_MAP = {
    "hashrate_ghs": "hashRate",
    "power_w": "power",
    "voltage_mv": "voltage",
    "temp_asic_c": "temp",
    "vr_temp_c": "vrTemp",
    "frequency_mhz": "frequency",
    "core_voltage_mv": "coreVoltage",
    "fan_rpm": "fanrpm",
    "fan_pct": "fanspeed",
    "shares_accepted": "sharesAccepted",
    "shares_rejected": "sharesRejected",
    "best_diff": "bestDiff",
    "best_session_diff": "bestSessionDiff",
    "uptime_s": "uptimeSeconds",
    "using_fallback": "isUsingFallbackStratum",
    "stratum_url": "stratumURL",
    "stratum_user": "stratumUser",
    "wifi_rssi": "wifiRSSI",
    "free_heap": "freeHeap",
    "version": "version",
}

log = logging.getLogger("bitaxe-collect")


def fetch_info(base_url: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    url = base_url.rstrip("/") + API_PATH
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def coinbase_payout(data: dict) -> tuple[str, Any]:
    """Return (address, sats) of the largest coinbase output.

    With stratumDecodeCoinbase enabled, AxeOS decodes the coinbase of the block
    template it is hashing. The largest output is the miner payout; zero-value
    outputs are OP_RETURN commitments.
    """
    outputs = [
        o
        for o in data.get("coinbaseOutputs") or []
        if isinstance(o, dict) and int(o.get("value", 0) or 0) > 0
    ]
    if not outputs:
        return "", ""
    best = max(outputs, key=lambda o: int(o["value"]))
    return best.get("address", ""), best.get("value", "")


def build_row(data: dict | None, error: str | None, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    row = {f: "" for f in FIELDS}
    row["timestamp_utc"] = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row["timestamp_local"] = now.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    if data is None:
        row["status"] = f"error:{error or 'unknown'}"
        return row
    for column, field in API_MAP.items():
        value = data.get(field)
        if value is not None:
            row[column] = value
    row["coinbase_address"], row["coinbase_sats"] = coinbase_payout(data)
    row["status"] = "ok"
    return row


def append_row(path: str, row: dict) -> None:
    """Append one row under an exclusive lock, writing the header only once."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.seek(0, os.SEEK_END)
            writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
            if fh.tell() == 0:
                writer.writeheader()
            writer.writerow(row)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def payout_matches(row: dict, expected_address: str) -> bool:
    """True if both the stratum user and the decoded coinbase pay to the expected address."""
    user_address = str(row.get("stratum_user", "")).split(".", 1)[0]
    coinbase = str(row.get("coinbase_address", ""))
    return user_address == expected_address and coinbase in ("", expected_address)


def sample(base_url: str, csv_path: str, timeout: float, expected_address: str = "") -> dict:
    try:
        data, error = fetch_info(base_url, timeout), None
    except Exception as exc:  # any failure must become a recorded gap, not a crash
        data, error = None, type(exc).__name__
    row = build_row(data, error)
    append_row(csv_path, row)
    if row["status"] != "ok":
        log.error("sample failed: %s", row["status"])
    else:
        log.info(
            "ok hashrate=%s GH/s power=%s W asic=%s C vr=%s C",
            row["hashrate_ghs"], row["power_w"], row["temp_asic_c"], row["vr_temp_c"],
        )  # fmt: skip
        if expected_address and not payout_matches(row, expected_address):
            log.warning(
                "PAYOUT MISMATCH: stratum_user=%s coinbase=%s expected=%s",
                row["stratum_user"], row["coinbase_address"], expected_address,
            )  # fmt: skip
    return row


def parse_args(argv: list | None = None) -> argparse.Namespace:
    env = os.environ.get
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--url",
        default=env("BITAXE_URL"),
        help="miner base URL, e.g. http://192.0.2.10 [BITAXE_URL]",
    )
    p.add_argument(
        "--csv", default=env("BITAXE_CSV", "metrics.csv"), help="output CSV path [BITAXE_CSV]"
    )
    p.add_argument(
        "--interval",
        type=int,
        default=int(env("BITAXE_INTERVAL", "0")),
        help="seconds between samples; 0 = take one sample and exit [BITAXE_INTERVAL]",
    )
    p.add_argument(
        "--timeout", type=float, default=float(env("BITAXE_TIMEOUT", str(DEFAULT_TIMEOUT)))
    )
    p.add_argument(
        "--expect-address",
        default=env("BITAXE_EXPECT_ADDRESS", ""),
        help="log a warning if the payout address differs [BITAXE_EXPECT_ADDRESS]",
    )
    args = p.parse_args(argv)
    if not args.url:
        p.error("--url or BITAXE_URL is required")
    return args  # fmt: skip


def main(argv: list | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    args = parse_args(argv)
    if args.interval <= 0:
        sample(args.url, args.csv, args.timeout, args.expect_address)
        return 0

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    log.info("sampling %s every %ss into %s", args.url, args.interval, args.csv)
    while not stop.is_set():
        sample(args.url, args.csv, args.timeout, args.expect_address)
        stop.wait(args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
