"""Guards for the published dataset: anonymised, well-formed and consistent with the collector."""

import csv
from pathlib import Path

import bitaxe_collect
from sanitize import EXAMPLE_ADDRESS, sanitize_row

DATA = Path(__file__).resolve().parents[2] / "data" / "metrics.csv"


def rows():
    with open(DATA, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_schema_matches_collector():
    with open(DATA, newline="", encoding="utf-8") as fh:
        assert next(csv.reader(fh)) == bitaxe_collect.FIELDS


def test_only_the_example_address_is_published():
    for row in rows():
        if row["stratum_user"]:
            assert row["stratum_user"].split(".")[0] == EXAMPLE_ADDRESS
        assert row["coinbase_address"] in ("", EXAMPLE_ADDRESS)


def test_sanitize_replaces_address_and_worker():
    row = sanitize_row({"stratum_user": "bc1qreal.myworker", "coinbase_address": "bc1qreal"})
    assert row["stratum_user"] == f"{EXAMPLE_ADDRESS}.worker1"
    assert row["coinbase_address"] == EXAMPLE_ADDRESS
