# 7. Setting up a Bitaxe Gamma: a practical guide

From the box to mining for yourself, with the traps found along the way. Firmware
`esp-miner` v2.15.x, AxeOS web UI.

## 0. Before connecting it to your network

1. **Verify the firmware** ([firmware-verification/](../firmware-verification/)). Ten minutes,
   read-only, and you get a backup of the factory state
2. **Decide where it will live on the network**: an isolated IoT network is the right place
   ([network isolation](03-network-isolation.md))

## 1. Power

Barrel jack first, always. The USB-C port is data only on the Gamma 601; with USB alone the
board does not even appear on the computer.

The included 5 V / 6 A supply has plenty of margin at factory settings (under 60 % load).
Plan a bigger one only if you intend to push towards 1.5 TH/s.

## 2. Flash a clean official image

Recommended if you bought it from a third party, even when the verification passes: you start
from an image you downloaded yourself, and the seller's settings are gone. Step by step in
[firmware-verification/](../firmware-verification/README.md#5-flash-a-clean-official-image).

## 3. First Wi-Fi setup

1. The miner opens a setup hotspot, `Bitaxe_XXXX`, with **no password**
2. Connect to it and open `http://192.168.4.1` **in a normal browser tab**. The pop-up that
   phones show automatically on open networks is a reduced view that only shows the network page
3. Type the SSID **by hand and check the capitals**: it is case sensitive, and phone keyboards
   capitalise the first letter. The scan button may find nothing; ignore it
4. 2.4 GHz networks only
5. Save and restart. The small OLED shows the IP it got

If it does not connect, the USB serial console tells you why in seconds
(`cat /dev/ttyACM0`): `reason 201` means the SSID was not found; `15` or `202` usually mean a wrong password.

Then reserve that IP in your DHCP server, using the MAC shown in the miner's settings.

## 4. Pools: point it at yourself

Out of the box the pools point somewhere else. On a fresh official image, at the esp-miner
project's donation address; on the unit in this repository, at **the seller's address**.
Fix it before anything else, in **both** pools.

`Pool` page, for the primary and the fallback pool:

| Field | Value |
|-------|-------|
| Stratum host | the pool, e.g. `pool.bitronics.store` |
| Port | the pool's **TLS** port, e.g. `3443` |
| User | `<your-bitcoin-address>.<worker-name>`, e.g. `bc1q...xyz.bitaxe1` |
| Password | `x` (solo pools ignore it) |
| Connection security | `TLS (System certificate)` |
| Decode Coinbase Tx | **on** |
| Stratum protocol | V1 |

About the address:

- **Use a wallet whose seed you control.** Never an exchange deposit address: a block reward
  arrives as a coinbase output, which some exchanges do not credit, and it cannot be spent for
  100 blocks
- Pick distinct pools for primary and fallback, ideally different software and operators, so
  one outage does not take both down

### The two pools used here (October 2026)

| | pool.bitronics.store | public-pool.io |
|---|---|---|
| Fee (solo) | 0 % | 0 % |
| Custody | none, coinbase pays you directly | none |
| Software | ckpool-based | public-pool, open source and self-hostable |
| Plain / TLS port | 3333 / 3443 | 3333 / 4333 |
| Status page | yes | no |

Check fees from the pool's own data, not from its homepage marketing. One homepage showed
"19 solo blocks" which turned out to be statistics for the whole network; the pool's own API
listed none. That says nothing bad about the pool (finding a block depends on its total
hashrate), but it is the kind of number to verify.

## 5. Check that you mine for yourself

Dashboard, **Block Header** panel, **Outputs**: it must show your address with the whole block
value. That is decoded from the template the miner is hashing right now, so it is the real
answer, not the username you typed.

Same check from the API:

```bash
curl -s http://<miner-ip>/api/system/info | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d['coinbaseOutputs'])"
```

## 6. Tuning

Run at factory settings for a day first, then follow the [methodology](05-tuning-methodology.md).
The settings menu only offers fixed steps (here 1000 to 1250 mV and 400 to 625 MHz), which
keeps experiments simple.

Measured on **one** unit, as a reference point and not as a recipe:

| Goal | Frequency | Voltage | GH/s | J/TH | ASIC peak |
|------|-----------|---------|------|------|-----------|
| Coolest and most efficient | 525 MHz | 1060 mV | ~1057 | 13.6 | 57 C |
| Balanced | 600 MHz | 1060 mV | ~1176 | 14.1 | 65.5 C |
| More hashrate (used for a month) | 600 MHz | 1100 mV | ~1223 | 14.4 | 70.1 C |
| Highest tested | 625 MHz | 1100 mV | ~1266 | 14.9 | 69.5 C* |

\* Measured over 11 hours, warmer configurations need more margin in summer.

Fan: set it manually. The automatic mode aims at 60 C and on a chip that runs a bit above
that it stays at full speed. 50 % was a good compromise here; check your temperatures after.

## 7. Keep it safe

- The web UI and API have **no authentication**. Only networks you control should reach it
- Anyone who can reach it can change the pool user. A collector with
  `--expect-address` ([deploy/](../deploy/)) tells you if that ever happens
