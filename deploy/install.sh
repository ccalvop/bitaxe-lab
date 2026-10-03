#!/usr/bin/env bash
# Install the Bitaxe collector as a systemd timer on Debian/Ubuntu (LXC, VM or bare metal).
set -euo pipefail

usage() {
  cat <<USAGE
Usage: sudo $0 --url http://<miner-ip> [--expect-address <btc-address>]

  --url             AxeOS base URL of the miner (required)
  --expect-address  log a warning whenever the payout address differs (optional)

Re-running is safe: files are overwritten, the CSV is kept.
USAGE
}

URL=""
EXPECT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --url) URL="${2:-}"; shift 2 ;;
    --expect-address) EXPECT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done
[ -n "$URL" ] || { usage; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR=/var/lib/bitaxe-lab

echo "==> python3"
command -v python3 >/dev/null || { apt-get update -qq && apt-get install -y -qq python3; }
python3 --version

echo "==> service user and data directory"
id bitaxe >/dev/null 2>&1 || useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin bitaxe
install -d -o bitaxe -g bitaxe -m 0750 "$DATA_DIR"

echo "==> collector"
install -D -m 0755 "$REPO_ROOT/collector/bitaxe_collect.py" /usr/local/lib/bitaxe-lab/bitaxe_collect.py

echo "==> configuration (/etc/default/bitaxe-collect)"
cat > /etc/default/bitaxe-collect <<CONF
BITAXE_URL=$URL
BITAXE_CSV=$DATA_DIR/metrics.csv
BITAXE_EXPECT_ADDRESS=$EXPECT
CONF

echo "==> systemd units"
install -m 0644 "$REPO_ROOT/deploy/systemd/bitaxe-collect.service" /etc/systemd/system/
install -m 0644 "$REPO_ROOT/deploy/systemd/bitaxe-collect.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now bitaxe-collect.timer

echo "==> first sample"
systemctl start bitaxe-collect.service
tail -n 1 "$DATA_DIR/metrics.csv"

echo
systemctl list-timers bitaxe-collect.timer --no-pager
echo
echo "Done. Logs: journalctl -u bitaxe-collect   Data: $DATA_DIR/metrics.csv"
