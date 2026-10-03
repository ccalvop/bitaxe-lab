"""Load the collector CSV and split it into stable configuration segments."""

from __future__ import annotations

import csv
import datetime as dt
import statistics as st
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

DATA = Path(__file__).resolve().parent.parent / "data" / "metrics.csv"
LOCAL_TZ = ZoneInfo("Europe/Madrid")
SAMPLE_MINUTES = 5
SETTLE_SAMPLES = 3  # drop the first 15 min after a change: temperature is still moving


@dataclass
class Sample:
    ts: dt.datetime
    local: dt.datetime
    ok: bool
    raw: dict

    def f(self, key: str) -> float | None:
        try:
            return float(self.raw[key])
        except (KeyError, TypeError, ValueError):
            return None

    @property
    def mining(self) -> bool:
        """False while booting: AxeOS reports temp -1 and 0 GH/s until the ASIC is up."""
        return self.ok and (self.f("hashrate_ghs") or 0) > 0 and (self.f("temp_asic_c") or 0) > 0

    @property
    def config(self) -> tuple[int, int, int]:
        """(frequency MHz, core voltage mV, fan % rounded to 5)."""
        fan = self.f("fan_pct") or 0
        return (int(self.f("frequency_mhz") or 0), int(self.f("core_voltage_mv") or 0),
                int(5 * round(fan / 5)))  # fmt: skip


@dataclass
class Segment:
    config: tuple[int, int, int]
    samples: list[Sample] = field(default_factory=list)

    def values(self, key: str) -> list[float]:
        return [v for v in (s.f(key) for s in self.samples) if v is not None]

    def mean(self, key: str) -> float:
        return st.mean(self.values(key))

    @property
    def hours(self) -> float:
        return len(self.samples) * SAMPLE_MINUTES / 60

    @property
    def efficiency(self) -> float:
        """J/TH from measured power and hashrate means, not from any firmware field."""
        return self.mean("power_w") / (self.mean("hashrate_ghs") / 1000)

    @property
    def reject_rate(self) -> float:
        """Rejected / submitted within the segment, robust to counter resets."""
        acc = rej = 0.0
        prev = None
        for s in self.samples:
            a, r = s.f("shares_accepted"), s.f("shares_rejected")
            if a is None or r is None:
                continue
            if prev and a >= prev[0] and r >= prev[1]:
                acc += a - prev[0]
                rej += r - prev[1]
            prev = (a, r)
        return 100 * rej / (acc + rej) if acc + rej else 0.0

    @property
    def label(self) -> str:
        f, v, fan = self.config
        return f"{f} MHz / {v} mV / fan {fan}%"


def load(path: Path | str = DATA) -> list[Sample]:
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ts = dt.datetime.strptime(row["timestamp_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc
            )
            out.append(Sample(ts, ts.astimezone(LOCAL_TZ), row.get("status") == "ok", row))
    return out


def segments(samples: list[Sample], min_hours: float = 0.75) -> list[Segment]:
    """Group consecutive ok samples by configuration, skipping the settling period."""
    result: list[Segment] = []
    current: Segment | None = None
    since_change = 0
    for s in (x for x in samples if x.mining):
        if current is None or s.config != current.config:
            current = Segment(s.config)
            result.append(current)
            since_change = 0
        since_change += 1
        if since_change > SETTLE_SAMPLES:
            current.samples.append(s)
    merged: dict[tuple, Segment] = {}
    for seg in result:
        merged.setdefault(seg.config, Segment(seg.config)).samples.extend(seg.samples)
    return [s for s in merged.values() if s.hours >= min_hours]


def restarts(samples: list[Sample]) -> list[dt.datetime]:
    ok = [s for s in samples if s.ok and s.f("uptime_s") is not None]
    return [b.local for a, b in zip(ok, ok[1:]) if b.f("uptime_s") < a.f("uptime_s")]
