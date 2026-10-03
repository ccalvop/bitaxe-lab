#!/usr/bin/env python3
"""Print the tuning report: one line per configuration, stability, restarts and integrity."""

from __future__ import annotations

import statistics as st
import sys

from dataset import DATA, load, restarts, segments

EXAMPLE = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"


def main(path: str = str(DATA)) -> int:
    samples = load(path)
    ok = [s for s in samples if s.ok]
    first, last = samples[0].local, samples[-1].local
    print(f"{len(samples)} samples ({len(samples) - len(ok)} failed)")
    print(f"{first:%Y-%m-%d %H:%M} -> {last:%Y-%m-%d %H:%M} (Europe/Madrid)\n")

    print(f"{'configuration':<30}{'hours':>7}{'GH/s':>9}{'W':>7}{'J/TH':>7}"
          f"{'ASIC':>7}{'max':>7}{'VR':>6}{'reject':>9}")  # fmt: skip
    for seg in sorted(segments(samples), key=lambda s: s.samples[0].ts):
        cols = [
            f"{seg.hours:>7.1f}",
            f"{seg.mean('hashrate_ghs'):>9.1f}",
            f"{seg.mean('power_w'):>7.2f}",
            f"{seg.efficiency:>7.2f}",
            f"{seg.mean('temp_asic_c'):>7.2f}",
            f"{max(seg.values('temp_asic_c')):>7.2f}",
            f"{seg.mean('vr_temp_c'):>6.1f}",
            f"{seg.reject_rate:>8.3f}%",
        ]
        print(f"{seg.label:<30}" + "".join(cols))

    longest = max(segments(samples), key=lambda seg: seg.hours)
    hashrate, power = longest.values("hashrate_ghs"), longest.values("power_w")
    print(f"\nNoise by averaging window, within one configuration ({longest.label}, "
          f"{longest.hours:.0f} h):")  # fmt: skip
    for label, n in [("5 min", 1), ("30 min", 6), ("1 h", 12), ("6 h", 72), ("24 h", 288)]:
        means = [st.mean(hashrate[i : i + n]) for i in range(0, len(hashrate) - n + 1, n)]
        print(f"  hashrate {label:<7} CV {100 * st.pstdev(means) / st.mean(means):5.2f}%")
    print(f"  power    5 min   CV {100 * st.pstdev(power) / st.mean(power):5.2f}%")

    print(f"\nRestarts: {len(restarts(samples))}")
    for r in restarts(samples):
        print(f"  {r:%Y-%m-%d %H:%M}")

    users = {s.raw.get("stratum_user", "").split(".")[0] for s in ok}
    payouts = {s.raw.get("coinbase_address") for s in ok if s.raw.get("coinbase_address")}
    print(f"\nPayout integrity: stratum users {users}, coinbase payouts {payouts}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
