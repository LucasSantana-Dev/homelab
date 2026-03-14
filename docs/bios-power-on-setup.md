# BIOS/UEFI Power-On After AC Loss (Firebat T8 Plus)

This guide configures **automatic boot after power restoration**.
Hardware detected on this host:

- Vendor: `Firebat_Computer`
- Model: `T8_Plus`
- Firmware: `American Megatrends International, LLC. 5.26`

## Goal

When AC power returns after an outage, the homelab host must boot automatically without pressing the power button.

## BIOS Settings (AMI firmware)

1. Reboot and enter BIOS/UEFI (`Del` or `F2` during POST).
2. Open one of these menus (name varies by firmware build):
   - `Advanced -> APM Configuration`
   - `Chipset -> PCH-IO Configuration`
   - `Power -> Restore on AC Power Loss`
3. Set power-restore behavior to:
   - `Power On`

### Alternate option names you may see

- `Restore on AC/Power Loss`
- `State After G3`
- `AC Back`
- `After Power Failure`
- `AC Power Recovery`

If only `Last State` and `Power On` are available, choose `Power On`.

## ErP / Deep Sleep Note

If `ErP` or `Deep Sleep` is enabled, automatic power-on after AC restore may be blocked.

Set the following (if present):

- `ErP Ready` = `Disabled`
- `Deep S4/S5` = `Disabled`

Save BIOS changes and exit.

## Post-Boot Verification (OS Side)

Run:

```bash
cd /home/luk-server/homelab
make power-restore-check
```

Expected:

- `docker.service`, `tailscaled.service`, `homelab-docker.service` enabled
- `homelab-update.timer`, `homelab-watchdog.timer` enabled
- active timers/services after boot

## Mandatory Physical AC-Loss Drill

Perform this once after BIOS change and after major firmware updates:

1. Confirm services are healthy (`make watchdog-status`).
2. Shut down gracefully: `sudo poweroff`.
3. Remove AC power from the host for at least 15 seconds.
4. Restore AC power.
5. Wait up to 3 minutes.
6. Validate host is online and run:
   - `make power-restore-check`
   - `make watchdog-status`

### Pass Criteria

- Host boots automatically without button press.
- SSH becomes available.
- Docker, tailscaled, homelab services, and watchdog timer are active.

### Fail Criteria

- Host stays off after AC restore.
- Host boots but required services/timers are disabled or inactive.
- Manual power button is required.

If failed, re-check BIOS power and ErP settings, then repeat the drill.
