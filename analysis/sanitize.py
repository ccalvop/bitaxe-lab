#!/usr/bin/env python3
"""Anonymise a collector CSV before publishing it.

Replaces the payout address and worker name with the BIP-173 example address, so the
dataset can be shared without linking a real address to an identity. Every other column
is kept as recorded.
"""

from __future__ import annotations

import argparse
import csv
import sys

EXAMPLE_ADDRESS = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
EXAMPLE_WORKER = "worker1"


def sanitize_row(row: dict) -> dict:
    row = dict(row)
    if row.get("stratum_user"):
        row["stratum_user"] = f"{EXAMPLE_ADDRESS}.{EXAMPLE_WORKER}"
    if row.get("coinbase_address", "").startswith(("bc1", "1", "3", "tb1")):
        row["coinbase_address"] = EXAMPLE_ADDRESS
    return row


def main(argv: list | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument(
        "--forbid",
        action="append",
        default=[],
        help="string that must not appear in the output (repeatable)",
    )
    args = p.parse_args(argv)

    with open(args.src, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = [sanitize_row(r) for r in reader]
        fields = reader.fieldnames
    with open(args.dst, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    text = open(args.dst, encoding="utf-8").read().lower()
    leaks = [s for s in args.forbid if s.lower() in text]
    if leaks:
        print(f"LEAK: {len(leaks)} forbidden value(s) still present in {args.dst}", file=sys.stderr)
        return 1
    print(f"{len(rows)} rows written to {args.dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
