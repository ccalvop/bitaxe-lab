# Firmware verification and clean flash

Do not trust a miner as it ships. This guide covers two steps, in this order:

1. **Verify** that a Bitaxe bought from a third-party seller runs the published open-source
   [esp-miner](https://github.com/bitaxeorg/ESP-Miner) firmware, before giving it network access
2. **Flash** a clean official image that you downloaded and checked yourself, so you start from
   a known state whatever the verification says

Why it matters: some sellers ship boards whose web UI is also called AxeOS but run a modified
binary that refuses official updates, depends on a subscription app or phones home. The UI
looks the same, the printed manual says the same. Only the bytes on the flash tell the truth.

The story of how this was used on a real unit is in
[docs/02-firmware-verification.md](../docs/02-firmware-verification.md).

## What you need

- `esptool` 5.x (`pip install --user esptool`)
- A USB-C **data** cable
- The board's own power supply

## 1. Power first, then USB

On the Gamma 601 the USB-C port carries **data only**: its `VBUS` pin is not connected to
anything, and the ESP32 is fed from the 5 V rail of the barrel jack. With USB alone the
computer sees nothing and the board looks dead. Plug the barrel jack first, then USB.

You should see an Espressif device (`303a:1001`) and a serial port:

```bash
lsusb | grep 303a
ls -l /dev/ttyACM*
```

On Ubuntu-based systems ModemManager may grab the port and break the transfer halfway.
A udev rule scoped to Espressif's vendor ID avoids it without disabling the service:

```bash
echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ENV{ID_MM_DEVICE_IGNORE}="1"' \
  | sudo tee /etc/udev/rules.d/99-espressif-no-modemmanager.rules
sudo udevadm control --reload-rules
```

## 2. Identify the chip (read-only)

```bash
esptool --port /dev/ttyACM0 flash-id
```

Note the MAC address and flash size (16 MB on the Gamma). If esptool reports flash
encryption or secure boot as enabled, stop: an official image cannot be verified or
reflashed on that board.

## 3. Dump the whole flash (read-only)

```bash
esptool --port /dev/ttyACM0 -b 921600 read-flash 0 0x1000000 stock-dump.bin
sha256sum stock-dump.bin
```

Keep this file private: the `nvs` partition holds the device settings, including the
Wi-Fi password once you configure it. It is also your way back to the factory state
(`esptool write-flash 0x0 stock-dump.bin`).

## 4. Compare against the official image

Download the factory image for **your board version and the firmware version your unit
runs** from the [esp-miner releases](https://github.com/bitaxeorg/ESP-Miner/releases)
(for example `esp-miner-factory-601-v2.15.0.bin`). The tool prints the version found on
the device, so run it once, read the version, fetch that release and run it again.

```bash
python3 verify_firmware.py stock-dump.bin esp-miner-factory-601-v2.15.0.bin
```

Real output from the unit in this repository:

```
Application descriptor
  device    {'project': 'esp-miner', 'version': 'v2.15.0', 'built': 'Aug 21 2026 17:41:15', ...}
  official  {'project': 'esp-miner', 'version': 'v2.15.0', 'built': 'Aug 21 2026 17:41:15', ...}

Partitions
  bootloader boot  0x000000+0x008000    IDENTICAL
  ptable     boot  0x008000+0x001000    IDENTICAL
  nvs        data  0x009000+0x006000    differs (expected: device settings)
  phy_init   data  0x00f000+0x001000    IDENTICAL
  factory    app   0x010000+0x400000    IDENTICAL
  www        data  0x410000+0x300000    IDENTICAL
  ota_0      app   0x710000+0x400000    IDENTICAL
  ota_1      app   0xb10000+0x400000    IDENTICAL
  otadata    data  0xf10000+0x002000    IDENTICAL
  coredump   data  0xf12000+0x010000    not in official image

Domains only in the device: none

VERDICT: matches the official firmware
```

Exit code `0` means the firmware matches, `1` means something differs, `2` means the flash
has no readable partition table (encrypted or not ESP-IDF).

### How to read the result

| Check | What it proves | What it does not |
|-------|----------------|------------------|
| Application descriptor | The build claims to be `esp-miner` vX | A descriptor can be copied in front of other code |
| Partition comparison | The bytes are the published build | Nothing about settings stored in `nvs` |
| Domain inventory | No hard-coded host beyond the official ones | Domains built at runtime would not show |

The partition comparison is the strong check. The descriptor alone is not.

Even with a clean result, **do not keep the shipped settings**: the unit in this repository
was genuine but shipped with the seller's own Bitcoin address in both pools and overclocked
to 740 MHz. Flashing the official image resets them.

## 5. Flash a clean official image

### Pick the right file

From the [esp-miner releases](https://github.com/bitaxeorg/ESP-Miner/releases), download the
**factory** image for your board, latest stable release (not a `rc` pre-release):

```
esp-miner-factory-<board>-<version>.bin      e.g. esp-miner-factory-601-v2.15.1.bin
```

`<board>` is printed on the PCB (601 for the Gamma). It matters: the factory image includes a
default settings partition with the ASIC model, frequency and voltage of that board. The
wrong one writes the wrong chip driver settings:

| Key | 601 (Gamma, BM1370) | 401 (Supra, BM1368) |
|-----|---------------------|---------------------|
| `asicmodel` | BM1370 | BM1368 |
| `asicfrequency` | 525 | 490 |
| `asicvoltage` | 1150 | 1166 |

Record its checksum, so you know later exactly what you flashed:

```bash
sha256sum esp-miner-factory-601-v2.15.1.bin
```

### Write it

Barrel jack powered, USB connected, then:

```bash
esptool --port /dev/ttyACM0 -b 921600 write-flash 0x0 esp-miner-factory-601-v2.15.1.bin
```

It takes under a minute and ends with `Hash of data verified`. The factory image is a merged
binary written at offset `0x0`: bootloader, partition table, default settings, firmware and web
interface in one go.

Prefer the command line over the web flasher: you choose the exact file and offset, you get a
log, and a dropped browser connection halfway through a 15 MB write is the usual way to end up
with a board that needs reflashing.

### What happens next

1. The board reboots and runs a **self-test**, then **waits for you to press RESET**. A board
   sitting on the self-test screen is not a failed flash
2. It opens a setup Wi-Fi hotspot, `Bitaxe_XXXX`
3. Its default pool settings point at the **esp-miner project's donation address**, on both the
   primary and the fallback pool. Change them before it mines for anyone

Continue with the [setup guide](../docs/07-setup-guide.md#3-first-wi-fi-setup).

### Check what you flashed

Optional but cheap: dump it again and compare against the file you wrote. Only `nvs` should
differ once you have configured it.

```bash
esptool --port /dev/ttyACM0 -b 921600 read-flash 0 0x1000000 after-flash.bin
python3 verify_firmware.py after-flash.bin esp-miner-factory-601-v2.15.1.bin
```
