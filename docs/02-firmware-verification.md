# 2. Verifying a miner bought from a third party

The tool and the exact commands are in [firmware-verification/](../firmware-verification/).
This page is what happened with the unit in this repository and what it taught.

## The risk

Bitmain does not sell the BM1370 on its own, so every Bitaxe Gamma is built by someone around
recovered chips, and many are sold through marketplaces. Some sellers ship boards with a
modified firmware that keeps the AxeOS look but:

- rejects official firmware updates
- depends on a companion app that turns into a subscription after a trial period
- includes a remote kill switch, documented in their own manuals

The printed leaflet of this unit said "AxeOS". So do the leaflets of the closed forks. A
seller's reviews saying "I flashed it fine" are a good sign but not proof.

## Order of operations

1. **Read the flash before anything else.** It costs ten minutes, it is read-only, and it gives
   both the verdict and a backup to restore the factory state
2. **Compare it against the official release** before the device ever touches your network
3. **Only then** flash, and only an image you downloaded and checked yourself

The original plan was to flash first and judge by whether the official image booted. A dump
answers the same question without writing anything, and without trusting a test that a
cleverly modified bootloader could pass.

## A board that looked dead

With only the USB-C cable connected, the computer saw nothing: no USB device, not even a
failed enumeration in the kernel log. Two cables and two ports, same result.

Several shop blogs state that the ESP32 is powered over USB for flashing. The board's own
KiCad schematic says otherwise: on the Gamma 601 the USB-C connector only wires `D+`, `D-` and
ground, its `VBUS` pins go nowhere, and the ESP32's 3.3 V regulator hangs off the 5 V rail of
the barrel jack. **Power from the barrel jack first, then USB.** The official flashing guide
says exactly that, and it turns out it is a requirement, not a suggestion.

## The verdict

```
factory    app   0x010000+0x400000    IDENTICAL   (esp-miner v2.15.0, built Aug 21 2026)
www        data  0x410000+0x300000    IDENTICAL   (the AxeOS web UI)
bootloader, partition table, ota_0, ota_1, otadata: IDENTICAL
nvs        data  0x009000+0x006000    differs     (device settings)
Domains only in the device: none
```

Genuine, unmodified, published firmware. No flash encryption and no secure boot, so it
accepts official updates.

## What the settings partition revealed

The bytes were clean. The **settings** were not what a buyer would want:

| Setting | Shipped | Official default for board 601 |
|---------|---------|--------------------------------|
| Primary pool user | **the seller's own Bitcoin address** | the esp-miner project's address |
| Fallback pool user | **the seller's own Bitcoin address** | the esp-miner project's address |
| ASIC frequency | **740 MHz** | 525 MHz |
| Core voltage | 1150 mV | 1150 mV |
| Wi-Fi | placeholder `myssid` / `password` | empty |

The `nvs` also kept a 130-minute burn-in session from before shipping, with 88 best-share
records. So the hardware had been tested hashing against a real pool, which made a separate
"does the hardware work" test unnecessary.

Plugging it in and giving it Wi-Fi would have mined for the seller, on both the primary and
the fallback pool, with a 41 % overclock and no extra voltage. Whether that is a leftover
test-bench configuration or something more deliberate cannot be told from the data, and it
does not change the advice: **read the configuration before connecting a miner to anything.**

## Flashing a clean image

The factory image (`esp-miner-factory-<board>-<version>.bin`) is a merged binary written at
offset `0x0`. It contains the bootloader, partition table, application, web UI **and a default
settings partition specific to the board version**. Picking the wrong board writes the wrong
ASIC driver settings:

| Key | 601 (Gamma, BM1370) | 401 (Supra, BM1368) |
|-----|---------------------|---------------------|
| `asicmodel` | BM1370 | BM1368 |
| `asicfrequency` | 525 | 490 |
| `asicvoltage` | 1150 | 1166 |

```bash
esptool --port /dev/ttyACM0 -b 921600 write-flash 0x0 esp-miner-factory-601-v2.15.1.bin
```

After flashing, the board runs a **self-test and waits for the RESET button**. A board sitting
on the self-test screen is not a failed flash.

The default settings of the official image point both pools at the **esp-miner project's
donation address**. Change the user on both pools before or right after connecting it. The
[setup guide](07-setup-guide.md) walks through it.
