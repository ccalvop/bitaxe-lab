# 8. Lessons learned

Most of what is useful in this repository came from something going wrong first. Each item
is what was believed, what the data said, and what changed.

## Measurement

**The dashboard hashrate is an estimate.** Single readings swing by more than 5 %. Early
comparisons between settings were made on a few minutes of data and were noise. Fixed by
averaging over at least an hour and using power, which is measured directly, as the reliable
signal. ([methodology](05-tuning-methodology.md#1-know-what-you-are-measuring))

**Rejected shares were the wrong stability signal.** A jump in rejections at 625 MHz / 1060 mV
was read as instability. A month later every rejection turned out to be `Stale`: network
timing, unrelated to the chip. The conclusion survived for a different reason (the hashrate
was 4.8 % below linear scaling), but it had been reached with the wrong instrument.

**A short test hides edge effects.** 1060 mV looked free at 525 MHz in a one-hour step. A month
of data showed it costs 4 % of the hashrate at 600 MHz. Edges only show over long windows.

**Time zones.** The collector container ran in UTC, so its "local time" column was UTC. Daily
cycles were first read two hours off. The published analysis converts from `timestamp_utc`,
and the schema says which column is the reference.

## Physical world

**Outdoor temperature does not predict the chip.** A projection of "35 C outside means 5 more
degrees on the ASIC" was used to reject a configuration. The data showed the ASIC cooler on a
35 C afternoon than at 21:00 with 30 C, because it follows the room, which lags behind. The
decision was reversed once the measured hottest hours were looked at instead of a model.

**Limits come from the source code, not from habit.** For a while the regulator was watched
against a self-imposed 65 C limit. The firmware throttles the regulator at 105 C and the ASIC at
75 C: the ASIC was the component to watch.

**Blogs said the USB port powers the ESP32 for flashing.** The schematic says its `VBUS` is not
connected. The board looked dead until the barrel jack was plugged in.

## Network

**A responding gateway is not a reachable network.** The gateway address answers from the
firewall itself.

**Documentation drifts.** The homelab notes said client isolation was off on the IoT SSID; the
access point said otherwise. Measure, then update the notes.

**The serial console beats guessing.** A Wi-Fi failure that looked like a network problem was a
capital letter, and the console said so in its first lines.

**Container templates have opinions.** Three traps in one Debian 12 LXC: a wrong default
bridge, a 5-minute boot hang from IPv6 DHCP with no DHCPv6 server, and SSH that needed
nesting and a non socket-activated service. ([deploy](../deploy/README.md#3-three-traps-found-on-the-way))

## Trust

**"Genuine firmware" and "safe to plug in" are different questions.** The binary was the
official build, byte for byte. The settings pointed both pools at the seller's address and
overclocked the chip by 41 %.

**Verify claims at the source.** A pool homepage advertising blocks found, a seller's leaflet
saying "AxeOS", a review saying "1.3 TH/s": each one was checked against an API, a flash dump
or a dataset before being used for a decision.
