#!/usr/bin/env python3
"""Compare a flash dump of an ESP32 miner against an official factory image.

Answers one question before you trust a device bought from a third party: is this the
published open-source firmware, or a modified build? It reports:

  1. The ESP-IDF application descriptor (project, version, build date, ELF SHA-256).
  2. A partition-by-partition byte comparison, using the partition table read from the dump.
  3. The inventory of domain names embedded anywhere in the flash, diffed against the image.

Only the configuration partition (nvs) is expected to differ.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
import sys
from pathlib import Path

PARTITION_TABLE_OFFSET = 0x8000
PARTITION_MAGIC = b"\xaa\x50"
APP_DESC_MAGIC = 0xABCD5432
APP_DESC_OFFSET = 0x20  # esp_app_desc_t follows the 32-byte image header
TYPES = {0x00: "app", 0x01: "data"}
TLDS = rb"io|com|org|net|cn|xyz|top|info|cc|ru|tk|store|shop|site|online|cloud|app"
DOMAIN_RE = re.compile(
    rb"(?<![a-z0-9.-])[a-z][a-z0-9-]{1,62}(?:\.[a-z0-9-]{1,62})*\.(?:" + TLDS + rb")\b"
)
# Regions before the first partition: compared too, a tampered bootloader is the worst case.
FIXED_REGIONS = [("bootloader", 0x0, 0x8000), ("ptable", 0x8000, 0x1000)]


def partitions(image: bytes) -> list[dict]:
    out = []
    for off in range(PARTITION_TABLE_OFFSET, PARTITION_TABLE_OFFSET + 0xC00, 32):
        entry = image[off : off + 32]
        if entry[:2] != PARTITION_MAGIC:
            break
        ptype, subtype, start, size = struct.unpack_from("<BBII", entry, 2)
        label = entry[12:28].split(b"\0")[0].decode("ascii", "replace")
        out.append({"label": label, "type": TYPES.get(ptype, hex(ptype)), "subtype": subtype,
                    "start": start, "size": size})  # fmt: skip
    return out


def app_descriptor(image: bytes, app_offset: int) -> dict | None:
    base = app_offset + APP_DESC_OFFSET
    if len(image) < base + 0xB0 or struct.unpack_from("<I", image, base)[0] != APP_DESC_MAGIC:
        return None

    def text(a: int, b: int) -> str:
        return image[base + a : base + b].split(b"\0")[0].decode("utf-8", "replace")

    return {
        "project": text(0x30, 0x50),
        "version": text(0x10, 0x30),
        "built": f"{text(0x60, 0x70)} {text(0x50, 0x60)}",
        "idf": text(0x70, 0x90),
        "elf_sha256": image[base + 0x90 : base + 0xB0].hex(),
    }


def domains(image: bytes) -> set[str]:
    return {m.decode() for m in DOMAIN_RE.findall(image.lower())}


def main(argv: list | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("dump", type=Path, help="full flash dump read from the device")
    p.add_argument("official", type=Path, help="official factory image for the same board")
    args = p.parse_args(argv)
    dump, ref = args.dump.read_bytes(), args.official.read_bytes()

    table = partitions(dump)
    if not table:
        print("No partition table at 0x8000: encrypted flash or non ESP-IDF layout. Do not trust.")
        return 2

    print("Application descriptor")
    factory = next((t for t in table if t["type"] == "app"), None)
    for name, image in (("device", dump), ("official", ref)):
        desc = app_descriptor(image, factory["start"]) if factory else None
        print(f"  {name:<9}", desc or "no valid esp_app_desc_t")

    print("\nPartitions")
    unexpected = 0
    fixed = [{"label": n, "type": "boot", "start": a, "size": z} for n, a, z in FIXED_REGIONS]
    for part in fixed + table:
        a = dump[part["start"] : part["start"] + part["size"]]
        b = ref[part["start"] : part["start"] + part["size"]]
        if not b:
            verdict = "not in official image"
        elif a == b:
            verdict = "IDENTICAL"
        else:
            verdict = "differs (expected: device settings)" if part["label"] == "nvs" else "DIFFERS"
            unexpected += part["label"] != "nvs"
        rng = f"0x{part['start']:06x}+0x{part['size']:06x}"
        print(f"  {part['label']:<10} {part['type']:<5} {rng:<20} {verdict}")
        if part["type"] == "app" and a == b and b:
            print(f"  {'':10} sha256 {hashlib.sha256(a).hexdigest()}")

    extra = sorted(domains(dump) - domains(ref))
    print(f"\nDomains in official image: {', '.join(sorted(domains(ref)))}")
    print(f"Domains only in the device: {', '.join(extra) if extra else 'none'}")

    ok = unexpected == 0 and not extra
    print("\nVERDICT:", "matches the official firmware" if ok else "DOES NOT MATCH, investigate")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
