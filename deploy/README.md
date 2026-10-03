# Deploying the collector

The collector is one Python file with no dependencies. It needs to reach the miner's
HTTP API (`http://<miner-ip>/api/system/info`) and somewhere to append a CSV.
Pick whichever fits what you already run:

| Option | Good for | Validation status |
|--------|----------|-------------------|
| [A. Proxmox LXC](#a-proxmox-lxc) | an always-on homelab | ran for a month in this project |
| [B. Any Linux with systemd](#b-any-linux-with-systemd) | a Raspberry Pi, a VM, a NAS shell | same installer as A |
| [C. Docker](#c-docker) | a laptop or desktop on any OS | built and exercised in CI against a mock API |

Run it on something that does not sleep. A laptop that suspends or changes network leaves
holes in the data exactly when you need continuity.

Whatever you choose, check first that the host can reach the miner:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://<miner-ip>/api/system/info   # expect 200
```

If the miner lives in an isolated IoT network, the collector host needs a firewall rule
**towards** the miner on TCP 80. That is inbound to the IoT network, so it does not weaken
its isolation: the miner still cannot open connections to your other networks.

---

## A. Proxmox LXC

### 1. Create the container

`Create CT` in the Proxmox UI with:

| Setting | Value | Why |
|---------|-------|-----|
| Template | `debian-12-standard` | ships Python 3.11 |
| Unprivileged | yes | |
| **Nesting** | **yes** (`Options > Features`) | without it `systemd-logind` cannot start and every SSH login hangs ~25 s |
| Cores / RAM / swap / disk | 1 / 512 MB / 512 MB / 4 GB | the CSV grows ~75 KB per day |
| **Bridge** | **the one your other LAN containers use** | the wizard defaults to `vmbr0`, which may not be your LAN |
| IPv4 | static | so your firewall rule has a fixed source |
| **IPv6** | **Static, empty** (or SLAAC if your network advertises IPv6) | **not DHCP** unless you run a DHCPv6 server, see below |

### 2. Install

From your workstation, copy a checkout into the container and run the installer:

```bash
git clone https://github.com/ccalvop/bitaxe-lab.git && cd bitaxe-lab
tar --exclude=.venv -czf - . | ssh root@<ct-ip> 'mkdir -p /root/bitaxe-lab && tar -xzf - -C /root/bitaxe-lab'
ssh root@<ct-ip> /root/bitaxe-lab/deploy/install.sh --url http://<miner-ip> --expect-address <your-btc-address>
```

The installer is idempotent. It creates a `bitaxe` system user, installs the collector,
writes `/etc/default/bitaxe-collect`, enables a 5-minute systemd timer and takes a first
sample.

### 3. Three traps found on the way

All three were hit with the stock Debian 12 template. Each one looks like something else.

**The container boots but nothing answers for five minutes.** Ping works, SSH does not, the
web console is blank. Cause: `ip6=dhcp` with no DHCPv6 server on the network.
`networking.service` waits for a lease until systemd kills it at its 5-minute start timeout,
and everything ordered after the network waits too. Check and fix from the Proxmox node:

```bash
pct exec <ctid> -- systemctl list-jobs          # networking.service stuck in "running"
pct set <ctid> --net0 name=eth0,bridge=<bridge>,ip=<ip>/24,gw=<gw>,hwaddr=<mac>,type=veth
pct reboot <ctid>
```

**SSH accepts the TCP connection but never sends a banner.** The template uses socket
activation: `systemd` holds port 22 and is supposed to spawn `sshd` per connection, which
failed here. Use the regular service instead:

```bash
pct exec <ctid> -- systemctl disable --now ssh.socket
pct exec <ctid> -- systemctl enable --now ssh.service
```

**SSH works but each login takes ~25 s.** The log shows
`pam_systemd: Failed to activate service 'org.freedesktop.login1': timed out`. Enable
nesting on the container and reboot it.

`pct exec <ctid> -- <command>` and `pct enter <ctid>` run commands inside the container from
the node shell, without SSH or a password. They are the way in when the network is the
problem.

---

## B. Any Linux with systemd

On Debian, Ubuntu, Raspberry Pi OS or similar:

```bash
git clone https://github.com/ccalvop/bitaxe-lab.git && cd bitaxe-lab
sudo ./deploy/install.sh --url http://<miner-ip> --expect-address <your-btc-address>
```

---

## C. Docker

```bash
git clone https://github.com/ccalvop/bitaxe-lab.git && cd bitaxe-lab/deploy/docker
BITAXE_URL=http://<miner-ip> BITAXE_EXPECT_ADDRESS=<your-btc-address> docker compose up -d
docker compose logs -f
```

The CSV lands in `deploy/docker/data/metrics.csv`. The container runs as your user, so the
file is yours. `timestamp_utc` is the reference time; set `TZ` if you also want
`timestamp_local` in your zone.

---

## Operating it

| Task | systemd (A, B) | Docker (C) |
|------|----------------|------------|
| See samples as they happen | `journalctl -u bitaxe-collect -f` | `docker compose logs -f` |
| **Payout address changed** | `journalctl -u bitaxe-collect -p warning` | `docker compose logs \| grep MISMATCH` |
| Next run | `systemctl list-timers bitaxe-collect.timer` | runs every `BITAXE_INTERVAL` seconds |
| Change the interval | `systemctl edit bitaxe-collect.timer`, override `OnUnitActiveSec` | set `BITAXE_INTERVAL` |
| Copy the data | `scp root@<host>:/var/lib/bitaxe-lab/metrics.csv .` | it is already in `./data` |
| Uninstall | `systemctl disable --now bitaxe-collect.timer` and remove the files listed in `install.sh` | `docker compose down` |

The `--expect-address` check compares the payout address against what the miner reports in
two places: the stratum user and the **decoded coinbase of the block template it is
hashing**. The second one is what a block would actually pay.
