# Home Assistant Setup Guide

This guide provides comprehensive instructions for setting up and configuring Home Assistant in the homelab environment.

## Table of Contents

1. [Initial Setup](#initial-setup)
2. [Integration Configuration](#integration-configuration)
3. [Automation Examples](#automation-examples)
4. [Troubleshooting](#troubleshooting)

## Initial Setup

### Accessing Home Assistant

Home Assistant is accessible via:

- **Tailscale Network**: `http://${TAILSCALE_IP}:8123`
- **Note**: Replace `${TAILSCALE_IP}` with your actual Tailscale IP from your `.env` file

### First-Time Setup

1. Navigate to the Home Assistant URL
2. Create an administrator account
3. Set your location and timezone
4. Complete the onboarding process

### Configuration Files

All Home Assistant configuration files are located in:

```
/home/luk-server/homelab/config/homeassistant/config/
```

Key configuration files:

- `configuration.yaml` - Main configuration file
- `automations.yaml` - Automation definitions
- `scripts.yaml` - Reusable scripts
- `secrets.yaml` - Sensitive information (API keys, passwords)

## Integration Configuration

### Meross Cloud Integration

The Meross Cloud integration allows control of Meross smart devices.

**Configuration:**

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Meross Cloud"
4. Enter your Meross account credentials
5. Select devices to add

**Note:** The Home Assistant container runs as `root` to allow package installation for this integration.

### Xiaomi Home Integration

The Xiaomi Home integration connects Xiaomi/Mijia devices.

**Configuration:**

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Xiaomi Home"
4. Follow the authentication flow

**Token Refresh:**
If you encounter "invalid refresh token" errors, see `xiaomi_token_refresh.md` for instructions on refreshing the token.

### Weather Integration

The weather integration uses the MET (Norwegian Meteorological Institute) platform.

**Configuration:**

- Configured in `configuration.yaml`
- Entity ID: `weather.home`

### Mobile App Integration

The mobile app integration enables:

- Push notifications
- Location tracking
- Actionable notifications

**Setup:**

1. Install the Home Assistant mobile app
2. Open the app and scan the QR code or enter the Home Assistant URL
3. Log in with your credentials
4. The device will automatically register

### Voice Assistants

#### Google Assistant

**Configuration:**

1. Set up a Google Cloud Project
2. Enable the Google Assistant API
3. Create a service account
4. Add credentials to `secrets.yaml`
5. Configure in `voice_assistants.yaml`

#### Alexa

**Configuration:**

1. Create an Alexa skill
2. Obtain client ID and secret
3. Add to `secrets.yaml`
4. Configure in `voice_assistants.yaml`

## Automation Examples

### Climate Control

Automations for climate control include:

- Temperature-based HVAC control
- Time-based schedules
- Energy-saving modes

See `automations.yaml` for detailed examples.

### Lighting

Lighting automations include:

- Motion-activated lighting
- Time-based schedules
- Adaptive brightness
- Vacation mode simulation

### Energy Management

Energy automations include:

- High usage alerts
- Peak hour optimization
- Daily cost notifications

### Media Control

Media automations include:

- Presence-based control
- Time-based volume adjustment
- Night mode

## Troubleshooting

### Permission Errors

If you encounter permission errors (e.g., with Meross Cloud integration):

- The container runs as `root` to allow package installation
- Check Docker Compose configuration in `docker-compose.yml`

### Integration Failures

1. Check Home Assistant logs:

   ```bash
   docker logs homeassistant
   ```

2. Verify integration configuration in `configuration.yaml`

3. Restart Home Assistant:

   ```bash
   docker restart homeassistant
   ```

### Token Refresh Issues

For Xiaomi Home integration token issues:

- See `xiaomi_token_refresh.md` for refresh instructions
- Tokens expire periodically and need manual refresh

### Weather Integration Duplicate ID

If you see "Platform met does not generate unique IDs":

- Ensure only one weather platform is configured
- Check `configuration.yaml` for duplicate entries

## Additional Resources

- [Home Assistant Documentation](https://www.home-assistant.io/docs/)
- [HACS Add-ons Guide](hacs-addons-guide.md)
- [Backup Configuration Guide](backup-configuration.md)
- [Dashboard Guide](dashboard-guide.md)
