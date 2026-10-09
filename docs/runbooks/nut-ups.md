# NUT UPS Runbook (TS Shara UPS Senoidal Universal 2200)

Status: **pending hardware**. Run this when the UPS arrives, inside the 7-day return window
(CDC art. 49). If any check in step 6 fails, return the unit.

Goal: on a power outage, the Windows desktop shuts down cleanly, while **the homelab, the modem
and one MacBook stay up for at least 2 hours** (owner requirement, 2026-10-06). The homelab then
shuts down cleanly before the battery is empty and boots by itself when AC returns. Context: the 2026-09-28 outage left the host off for ~24h and
`prometheus` in `Exited (255)` after a hard power loss. The fix is clean shutdown plus automatic
power-on, not long runtime.

## Hardware and topology

- UPS: TS Shara UPS Senoidal Universal 2200 (#4222). Pure sine, ~1540W, 1 ms transfer,
  internal 4x 12V 7Ah (24V, ~336Wh nominal). **No external bank at first**: the acceptance test
  decides (see step 6). Fallback: 2x 12V 45Ah via engate, after TS Shara confirms the charger
  current in writing.
- Output switch: set it on purpose before plugging loads (115V or 220V; all loads are 100-240V).
- Loads: desktop (Ryzen 9800X3D + RX 9070 XT, XPG 850W Gold), 2 monitors, modem, homelab N100.
  One MacBook charger on a battery outlet; the second MacBook runs on its own battery.
- NUT roles:
  - `homelab` (Ubuntu, `192.168.0.250`): USB to the UPS, `upsd` + `upsmon` **primary**.
  - Windows desktop: WinNUT-Client as **secondary**, over LAN.
- Shutdown policy:
  - Desktop: shuts down after **5-10 min** on battery.
  - Homelab: stays up as long as possible and shuts down at **~85% of the measured runtime**
    (upssched timer), with low battery as backup.

## 1. Identify the USB device

```bash
lsusb                      # expect STMicroelectronics Virtual COM Port (0483:5740)
sudo dmesg | tail -20
ls -l /dev/ttyACM* /dev/serial/by-id/ 2>/dev/null
```

`nut-scanner` does not autodetect this unit; the port is set by hand.

## 2. Install

Ubuntu's `nut` package already ships `nutdrv_qx` (verified 2026-10-06 on 2.8.1), so no source
build is needed.

```bash
sudo apt install nut
```

## 3. Config (`/etc/nut/`)

`nut.conf`:

```
MODE=netserver
```

`ups.conf` (use the `/dev/serial/by-id/...` path from step 1; `ttyACM0` can change across boots):

```
[shara]
  driver = nutdrv_qx
  protocol = megatec
  port = /dev/serial/by-id/<id-from-step-1>
  # port = /dev/ttyACM0   # fallback only if by-id is missing
  desc = "TS Shara UPS Senoidal Universal 2200"
  runtimecal = 600,100,1500,50
  default.battery.voltage.high = 27.6
  default.battery.voltage.low = 21.0
  default.battery.voltage.nominal = 24
  ondelay = 180
  offdelay = 60
```

`runtimecal` and the voltage limits are starting values; tune them with the runtime measured in
step 6. `ondelay` must be longer than the homelab's shutdown time.

Test the driver alone (Ctrl+C after it prints values):

```bash
sudo upsdrvctl -D start shara
```

`upsd.conf` (LAN only; port 3493 must not be exposed through Cloudflare or Caddy):

```
LISTEN 127.0.0.1 3493
LISTEN 192.168.0.250 3493
```

`upsd.users` (passwords live in the secret store, never in this repo):

```
[upsmon_local]
  password = <secret>
  upsmon primary
  actions = SET
  instcmds = ALL

[upsmon_desktop]
  password = <secret>
  upsmon secondary
```

`upsmon.conf`:

```
MONITOR shara@localhost 1 upsmon_local <secret> primary
SHUTDOWNCMD "/sbin/shutdown -h +0"
NOTIFYCMD /usr/sbin/upssched
NOTIFYFLAG ONBATT SYSLOG+WALL+EXEC
NOTIFYFLAG ONLINE SYSLOG+WALL+EXEC
POWERDOWNFLAG /etc/killpower
FINALDELAY 5
```

`POWERDOWNFLAG` makes the system-shutdown hook (`nutshutdown`) tell the UPS to cut output after
`offdelay` and restore it after `ondelay` once AC is back. Without it the UPS keeps feeding a
halted host and the BIOS power-on never triggers.

`upssched.conf` (set `<seconds>` to ~85% of the runtime measured in step 6):

```
CMDSCRIPT /usr/bin/upssched-cmd
PIPEFN /run/nut/upssched.pipe
LOCKFN /run/nut/upssched.lock
AT ONBATT * START-TIMER onbatt-shutdown <seconds>
AT ONLINE * CANCEL-TIMER onbatt-shutdown
```

Until step 6 measures the runtime, set `<seconds>` to `10800` (3h) so low battery triggers the
shutdown first during the test.

`/usr/bin/upssched-cmd` (Ubuntu ships a placeholder; replace it):

```bash
sudo tee /usr/bin/upssched-cmd >/dev/null <<'EOF'
#!/bin/sh
case "$1" in
  onbatt-shutdown)
    logger -t upssched-cmd "on battery past timer, forcing shutdown"
    /sbin/upsmon -c fsd
    ;;
  *)
    logger -t upssched-cmd "unrecognized command: $1"
    ;;
esac
EOF
sudo chown root:root /usr/bin/upssched-cmd
sudo chmod 755 /usr/bin/upssched-cmd
```

Install the script before enabling `nut-monitor`, then:

```bash
sudo chown root:nut /etc/nut/*.conf /etc/nut/upsd.users
sudo chmod 640 /etc/nut/*.conf /etc/nut/upsd.users
sudo systemctl enable --now nut-server nut-monitor
upsc shara@localhost
```

## 4. Windows desktop (secondary)

Install WinNUT-Client (<https://github.com/nutdotnet/WinNUT-Client>), point it at
`192.168.0.250:3493`, UPS name `shara`, user `upsmon_desktop`, and set shutdown after 5-10 min
on battery.

## 5. Auto power-on

NUT shuts the host down; the BIOS brings it back. `Restore on AC Power Loss = Power On` and
`ErP Ready = Disabled` are required: see [bios-power-on-setup.md](../bios-power-on-setup.md).
The host is headless; do not use `systemctl reboot --firmware-setup` without a monitor and keyboard.

## 6. Acceptance test (inside the return window)

Run with the real outage load on battery outlets: modem, homelab and one MacBook charger
(MacBook below 50% so it is actually charging). Run the desktop for its first 5-10 min too, then
let WinNUT shut it down.

Someone must stay near the UPS: step 5 needs a person to plug it back into the wall.

1. `upsc shara@localhost ups.status` shows `OL`. The upssched timer is at `10800` (step 3).
2. Pull the UPS plug from the wall: status goes `OB`. Note the time.
3. Leave it on battery until `ups.status` shows `OB LB`. Record the runtime to `LB` (this is the
   usable runtime, not time to empty) and the load (`upsc shara@localhost ups.load`).
4. On `LB`, `upsmon` sets FSD and the homelab shuts down cleanly. About `offdelay` (60 s) later
   the UPS cuts its output. The battery is not fully drained at this point.
5. Within 10 min of the output cut, plug the UPS back into the wall. After `ondelay` (180 s) the
   output comes back, the homelab boots by itself (BIOS, step 5) and the modem comes back.
   If the output does not come back within 10 min of AC returning, the test fails.
6. After boot, check:
   - `journalctl -b -1 -u nut-monitor | grep -i -E 'fsd|shutdown'` shows the FSD.
   - `last -x shutdown | head -3` shows a clean shutdown at the expected time.
   - `upsc shara@localhost ups.status` shows `OL` (or `OL CHRG`).
   - `make power-restore-check` and `docker ps -a --filter status=exited`
     (an `Exited (255)` with no logs is fixed with `docker start <name>`).

Pass criterion: all checks in step 6 pass **and** runtime to `LB` is **>= 3h** (2h requirement
plus margin for battery aging in heat). Between 2h and 3h, or below: keep the UPS and add the
2x 45Ah external bank (charger current confirmed first; replace internal and external batteries
together; fuse the string). Then set the upssched timer to ~85% of the measured runtime.

## Maintenance

- Quarterly: `upscmd -u upsmon_local shara test.battery.start.quick`.
- Replace all 4 internal batteries together every 2-3 years (heat shortens VRLA life).
