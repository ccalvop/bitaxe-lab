#!/usr/bin/env python3
"""Render every figure in docs/img from data/metrics.csv. Re-run after updating the data."""

from __future__ import annotations

import math
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402

from dataset import LOCAL_TZ, load, restarts, segments  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "img"
INK, MUTED, ACCENT, WARN, GOOD = "#1f2933", "#9aa5b1", "#d9480f", "#c92a2a", "#2b8a3e"

# Fan PWM -> rpm, read from the AxeOS API while stepping the manual fan speed.
# 40% and 70% were short transitional steps that the 5-minute collector did not capture.
FAN_POINTS = [(40, 4643), (50, 5237), (55, 5561), (70, 6561), (100, 6758)]

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "text.color": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.grid": True, "grid.color": "#e4e7eb", "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "axes.titleweight": "bold", "axes.titlesize": 11,
})  # fmt: skip


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / name)


def config_comparison(segs) -> None:
    keep = [s for s in segs if s.hours >= 5]
    keep.sort(key=lambda s: s.mean("hashrate_ghs"))
    labels = [s.label.replace(" / fan", "\nfan") for s in keep]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    metrics = [
        ("Hashrate (GH/s)", [s.mean("hashrate_ghs") for s in keep], ACCENT, "{:.0f}"),
        ("Efficiency (J/TH, lower is better)", [s.efficiency for s in keep], GOOD, "{:.2f}"),
        ("Peak ASIC temperature (C)", [max(s.values("temp_asic_c")) for s in keep], WARN, "{:.1f}"),
    ]
    for ax, (title, values, color, fmt) in zip(axes, metrics):
        bars = ax.barh(labels, values, color=color, alpha=0.85)
        ax.bar_label(bars, labels=[fmt.format(v) for v in values], padding=3, fontsize=9)
        ax.set_title(title)
        ax.set_xlim(min(values) * 0.9, max(values) * 1.08)
        ax.grid(axis="y", visible=False)
    axes[2].axvline(75, color=WARN, ls="--", lw=1)
    axes[2].text(74.6, -0.6, "throttle 75 C", color=WARN, ha="right", fontsize=8)
    axes[2].set_xlim(55, 77)
    fig.suptitle("Configurations held for at least 5 hours (factory default at the bottom)", y=1.02)
    save(fig, "config-comparison.png")


def voltage_sweep(segs) -> None:
    at525 = sorted((s for s in segs if s.config[0] == 525), key=lambda s: -s.config[1])
    volts = [s.config[1] for s in at525]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.8))
    a1.plot(volts, [s.mean("power_w") for s in at525], "o-", color=ACCENT, label="measured")
    p0, v0 = at525[0].mean("power_w"), volts[0]
    model = [p0 * (v / v0) ** 2 for v in volts + [1000]]
    a1.plot(volts + [1000], model, "--", color=MUTED, label="model  P ~ V^2")
    a1.set(title="Power at 525 MHz", xlabel="core voltage (mV)", ylabel="W")
    a1.invert_xaxis()
    a1.legend(frameon=False)
    a2.plot(volts, [s.mean("hashrate_ghs") for s in at525], "o-", color=INK, label="measured")
    a2.plot([1000], [750], "x", color=WARN, ms=10, mew=2, label="1000 mV: ~750 GH/s (aborted)")
    a2.set(title="Hashrate at 525 MHz", xlabel="core voltage (mV)", ylabel="GH/s", ylim=(700, 1120))
    a2.invert_xaxis()
    a2.legend(frameon=False, loc="lower left")
    fig.suptitle("Undervolting: power follows V^2 until the chip runs out of margin", y=1.02)
    save(fig, "voltage-sweep.png")


def fan_curve() -> None:
    pwm, rpm = zip(*FAN_POINTS)
    db = [50 * math.log10(r / 6758) for r in rpm]
    fig, a1 = plt.subplots(figsize=(7, 3.8))
    a1.plot(pwm, rpm, "o-", color=INK)
    a1.set(xlabel="PWM duty set in AxeOS (%)", ylabel="measured fan speed (rpm)",
           title="Stock fan: almost no control above 70% PWM")  # fmt: skip
    a1.axvspan(70, 100, color=MUTED, alpha=0.15)
    a1.text(85, 4800, "flat zone:\n-30% PWM = -3% rpm", ha="center", color=INK, fontsize=9)
    for x, y, d in zip(pwm, rpm, db):
        a1.annotate(f"{d:+.1f} dB", (x, y), textcoords="offset points", xytext=(10, -14),
                    ha="left", fontsize=8, color=ACCENT)  # fmt: skip
    save(fig, "fan-curve.png")


def daily_cycle(segs) -> None:
    longest = max(segs, key=lambda s: s.hours)
    by_hour = defaultdict(list)
    for smp in longest.samples:
        t = smp.f("temp_asic_c")
        if t is not None:
            by_hour[smp.local.hour].append(t)
    hours = sorted(by_hour)
    mean = [st.mean(by_hour[h]) for h in hours]
    lo = [min(by_hour[h]) for h in hours]
    hi = [max(by_hour[h]) for h in hours]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.fill_between(hours, lo, hi, color=ACCENT, alpha=0.15, label="min-max over the month")
    ax.plot(hours, mean, "o-", color=ACCENT, label="hourly mean")
    ax.set(
        xlabel="local time (Europe/Madrid)",
        ylabel="ASIC temperature (C)",
        xticks=range(0, 24, 2),
        ylim=(50, 76),
        title=f"Daily thermal cycle, {longest.label}, {longest.hours:.0f} h",
    )
    ax.axhline(75, color=WARN, ls="--", lw=1)
    ax.text(0, 74.2, "throttle 75 C", color=WARN, fontsize=8, va="top")
    ax.legend(frameon=False, loc="lower right")
    save(fig, "daily-thermal-cycle.png")


def noise_vs_window(segs) -> None:
    longest = max(segs, key=lambda s: s.hours)
    h = longest.values("hashrate_ghs")
    windows = [1, 3, 6, 12, 24, 72, 144, 288]
    cvs = []
    for n in windows:
        means = [st.mean(h[i : i + n]) for i in range(0, len(h) - n + 1, n)]
        cvs.append(100 * st.pstdev(means) / st.mean(means))
    minutes = [5 * n for n in windows]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.plot(minutes, cvs, "o-", color=ACCENT, label="measured")
    ax.plot(minutes, [cvs[0] / math.sqrt(n) for n in windows], "--", color=MUTED,
            label="1/sqrt(n) for independent samples")  # fmt: skip
    ax.set_xscale("log")
    ax.set_xticks(minutes, ["5m", "15m", "30m", "1h", "2h", "6h", "12h", "24h"])
    ax.set(xlabel="averaging window", ylabel="coefficient of variation (%)",
           title="Reported hashrate is an estimate: average before comparing")  # fmt: skip
    ax.legend(frameon=False)
    save(fig, "hashrate-noise-vs-window.png")


def convergence_gif(segs) -> None:
    longest = max(segs, key=lambda s: s.hours)
    window = longest.samples[-576:]  # last 48 h
    times = [s.local for s in window]
    values = [s.f("hashrate_ghs") for s in window]
    steps = [1, 3, 6, 12, 24, 48, 96, 144, 288]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.scatter(times, values, s=6, color=MUTED, alpha=0.6, label="5-minute samples")
    (line,) = ax.plot([], [], color=ACCENT, lw=2.2, label="rolling mean")
    title = ax.set_title("")
    ax.set(ylabel="GH/s", ylim=(min(values) * 0.97, max(values) * 1.02))
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 12], tz=LOCAL_TZ))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Hh", tz=LOCAL_TZ))
    ax.legend(frameon=True, framealpha=0.9, loc="upper right", fontsize=8)

    def frame(i):
        n = steps[i]
        roll = [st.mean(values[max(0, j - n + 1) : j + 1]) for j in range(len(values))]
        line.set_data(times[n - 1 :], roll[n - 1 :])
        tail = roll[n - 1 :]
        cv = 100 * st.pstdev(tail) / st.mean(tail)
        label = f"{5 * n} min" if n < 12 else f"{n // 12} h"
        title.set_text(f"Same miner, same settings. Averaging window: {label}   spread {cv:.1f}%")
        return line, title

    anim = FuncAnimation(fig, frame, frames=len(steps), blit=False)
    OUT.mkdir(parents=True, exist_ok=True)
    anim.save(OUT / "hashrate-convergence.gif", writer=PillowWriter(fps=1), dpi=90)
    plt.close(fig)
    print("wrote", OUT / "hashrate-convergence.gif")


def month_timeline(samples, segs) -> None:
    ok = [s for s in samples if s.mining]
    t = [s.local for s in ok]
    h = [s.f("hashrate_ghs") for s in ok]
    temp = [s.f("temp_asic_c") for s in ok]
    n = 12
    h_roll = [st.mean(h[max(0, i - n + 1) : i + 1]) for i in range(len(h))]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(12, 5), sharex=True)
    a1.plot(t, h_roll, color=ACCENT, lw=1)
    a1.set(ylabel="GH/s (1 h mean)", title="One month of telemetry")
    a2.plot(t, temp, color=WARN, lw=0.6)
    a2.set(ylabel="ASIC (C)")
    for r in restarts(samples):
        for ax in (a1, a2):
            ax.axvline(r, color=MUTED, lw=0.8, ls=":")
    a2.xaxis.set_major_locator(mdates.DayLocator(interval=4, tz=LOCAL_TZ))
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%d %b", tz=LOCAL_TZ))
    a2.text(t[-1], max(temp), "dotted lines: restarts (unplugged to move it)",
            ha="right", va="top", fontsize=8, color=MUTED)  # fmt: skip
    save(fig, "month-timeline.png")


def main() -> None:
    samples = load()
    segs = segments(samples)
    config_comparison(segs)
    voltage_sweep(segs)
    fan_curve()
    daily_cycle(segs)
    noise_vs_window(segs)
    convergence_gif(segs)
    month_timeline(samples, segs)


if __name__ == "__main__":
    main()
