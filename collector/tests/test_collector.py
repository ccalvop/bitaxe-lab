import csv
import datetime as dt
import json

import pytest

import bitaxe_collect as bc
from mock_axeos import FIXTURE, serve

EXAMPLE = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
NOW = dt.datetime(2026, 9, 5, 16, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def info():
    return json.loads(FIXTURE.read_text())


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_build_row_maps_every_field(info):
    row = bc.build_row(info, None, NOW)
    assert row["status"] == "ok"
    assert row["timestamp_utc"] == "2026-09-05T16:00:00Z"
    assert row["frequency_mhz"] == info["frequency"]
    assert row["core_voltage_mv"] == info["coreVoltage"]
    assert row["stratum_user"].startswith(EXAMPLE)
    assert set(row) == set(bc.FIELDS)


def test_coinbase_payout_picks_largest_non_zero_output(info):
    address, sats = bc.coinbase_payout(info)
    assert address == EXAMPLE
    assert sats > 0


def test_coinbase_payout_ignores_op_return_only():
    data = {"coinbaseOutputs": [{"value": 0, "address": "OP_RETURN: ..."}]}
    assert bc.coinbase_payout(data) == ("", "")


def test_error_row_keeps_timestamp_and_blanks_metrics():
    row = bc.build_row(None, "TimeoutError", NOW)
    assert row["status"] == "error:TimeoutError"
    assert row["timestamp_utc"]
    assert row["hashrate_ghs"] == ""


def test_append_writes_header_once(tmp_path, info):
    path = tmp_path / "sub" / "metrics.csv"
    for _ in range(3):
        bc.append_row(str(path), bc.build_row(info, None, NOW))
    lines = path.read_text().splitlines()
    assert lines[0].split(",") == bc.FIELDS
    assert len(lines) == 4


def test_unreachable_miner_records_a_gap(tmp_path):
    path = tmp_path / "metrics.csv"
    row = bc.sample("http://127.0.0.1:9", str(path), timeout=1)
    assert row["status"].startswith("error:")
    assert read_csv(path)[0]["status"].startswith("error:")


def test_end_to_end_against_mock_api(tmp_path):
    server, _ = serve()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        path = tmp_path / "metrics.csv"
        bc.main(["--url", url, "--csv", str(path)])
    finally:
        server.shutdown()
    rows = read_csv(path)
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["coinbase_address"] == EXAMPLE


@pytest.mark.parametrize(
    ("user", "coinbase", "expected"),
    [
        (f"{EXAMPLE}.worker1", EXAMPLE, True),
        (f"{EXAMPLE}.worker1", "", True),
        ("bc1qsomeoneelse.worker1", EXAMPLE, False),
        (f"{EXAMPLE}.worker1", "bc1qsomeoneelse", False),
    ],
)
def test_payout_matches(user, coinbase, expected):
    assert (
        bc.payout_matches({"stratum_user": user, "coinbase_address": coinbase}, EXAMPLE) is expected
    )


def test_payout_mismatch_logs_warning(tmp_path, caplog):
    server, _ = serve()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        bc.sample(url, str(tmp_path / "m.csv"), timeout=5, expected_address="bc1qsomeoneelse")
    finally:
        server.shutdown()
    assert "PAYOUT MISMATCH" in caplog.text


def test_url_is_required(monkeypatch):
    monkeypatch.delenv("BITAXE_URL", raising=False)
    with pytest.raises(SystemExit):
        bc.parse_args([])


def test_fixture_only_holds_documentation_identifiers(info):
    """The fixture is a real response: it must carry documentation values, never real ones."""
    assert info["stratumUser"].split(".")[0] == EXAMPLE
    assert info["fallbackStratumUser"].split(".")[0] == EXAMPLE
    assert {o["address"] for o in info["coinbaseOutputs"] if o["value"]} == {EXAMPLE}
    assert info["ipv4"].startswith("192.0.2.")  # RFC 5737 documentation range
    assert info["macAddr"] == "AA:BB:CC:DD:EE:FF"
