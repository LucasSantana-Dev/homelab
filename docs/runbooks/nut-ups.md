# NUT UPS Runbook (NHS Premium PDV Senoidal 2200VA)

Status: **pending hardware**. Run this when the UPS arrives.

Goal: on a power outage, the homelab (and the Windows desktop) shut down cleanly when the
battery runs low, and the homelab boots by itself when AC returns. Context: the 2026-09-28
outage left the host off for ~24h and `prometheus` in `Exited (255)` after a hard power loss.

## Hardware and topology

- UPS: NHS Premium PDV **Senoidal** 2200VA / 1320W, 24V bank (2x 18Ah internal + 2x 12V 45Ah
  external in series), USB, output 120V (all loads are 100-240V).
- Load (~275W avg): desktop (Ryzen 9800X3D + RX 9070 XT), 2 monitors, modem, homelab N100,
  2 MacBook chargers.
- NUT roles:
  - `homelab` (Ubuntu 25.04, `192.168.0.250`): USB to the UPS, `upsd` + `upsmon` **primary**.
  - Windows desktop: WinNUT-Client as **secondary**, over LAN.
  - MacBooks: own battery, no NUT client.

## 1. Identify the USB device

```bash
lsusb
dmesg | tail -20
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

NHS senoidal units usually show up as a USB serial port (`/dev/ttyACM0`), not as HID.

## 2. Pick the driver

`nhs_ser` is the NUT driver for the NHS senoidal line. **Ubuntu 25.04 ships NUT 2.8.1 and its
`nut-server` package does not include `nhs_ser`** (checked 2026-10-06; only `nutdrv_qx` etc.).

Order of attempts:

1. `nutdrv_qx` with `port = auto` (works if the unit speaks a Megatec/Q1 variant).
2. If (1) fails: NUT >= 2.8.3 with `nhs_ser`, built from source
   (<https://github.com/networkupstools/nut>, `./configure --with-serial --with-usb`)
   or from a newer distro release. Do not mix the source build with the apt `nut` package.

Test the driver alone before wiring `upsmon`:

```bash
sudo upsdrvctl -D start nhs   # Ctrl+C after it prints values
```

## 3. Config (`/etc/nut/`)

`nut.conf`:

```
MODE=netserver
```

`ups.conf` (nhs_ser variant; `ah` = total bank, 18 + 45):

```
[nhs]
  driver = nhs_ser
  port = /dev/ttyACM0
  desc = "NHS Premium PDV Senoidal 2200VA"
  va = 2200
  ah = 63
  vbat = 24.00
  pf = 0.60
```

For `nutdrv_qx`, replace the body with `driver = nutdrv_qx` and `port = auto`.

`upsd.conf` (LAN only; port 3493 must not be exposed through Cloudflare or Caddy):

```
LISTEN 127.0.0.1 3493
LISTEN 192.168.0.250 3493
```

`upsd.users` (passwords live in `.env`/secret store, never in this repo):

```
[upsmon_local]
  password = <secret>
  upsmon primary

[upsmon_desktop]
  password = <secret>
  upsmon secondary
```

`upsmon.conf`:

```
MONITOR nhs@localhost 1 upsmon_local <secret> primary
SHUTDOWNCMD "/sbin/shutdown -h +0"
FINALDELAY 5
```

```bash
sudo chown root:nut /etc/nut/*.conf /etc/nut/upsd.users
sudo chmod 640 /etc/nut/*.conf /etc/nut/upsd.users
sudo systemctl enable --now nut-server nut-monitor
upsc nhs@localhost
```

## 4. Windows desktop (secondary)

Install WinNUT-Client (<https://github.com/nutdotnet/WinNUT-Client>), point it at
`192.168.0.250:3493`, UPS name `nhs`, user `upsmon_desktop`, and enable "shutdown on low battery".

## 5. Auto power-on

NUT shuts the host down; the BIOS brings it back. `Restore on AC Power Loss = Power On` and
`ErP Ready = Disabled` are required: see [bios-power-on-setup.md](../bios-power-on-setup.md).
The host is headless; do not use `systemctl reboot --firmware-setup` without a monitor and keyboard.

## 6. Drill (mandatory once)

1. `upsc nhs@localhost` shows `ups.status: OL`.
2. Pull the UPS plug from the wall: status goes `OB`, desktop and host stay up.
3. Simulate low battery without draining it: `sudo upsmon -c fsd`. Both machines must shut down.
4. Restore AC, power-cycle the UPS output if needed, confirm the host boots alone.
5. After boot: `make power-restore-check` and `docker ps -a --filter status=exited`
   (an `Exited (255)` with no logs is fixed with `docker start <name>`).
