# HACS Add-ons Guide

This guide covers the HACS (Home Assistant Community Store) add-ons installed in this Home Assistant instance.

## Table of Contents

1. [Installed Add-ons](#installed-add-ons)
2. [Configuration](#configuration)
3. [Usage Examples](#usage-examples)

## Installed Add-ons

### Adaptive Lighting

**Purpose:** Automatically adjusts brightness and color temperature of lights based on time of day.

**Configuration:**

1. Go to Settings → Devices & Services
2. Add the Adaptive Lighting integration
3. Configure switches for each light or light group
4. Set your preferences for day/night transitions

**Usage:**

- Creates switches like `switch.adaptive_lighting_<name>`
- Automatically adjusts lights throughout the day
- Can be disabled/enabled via the switch

### Node-RED Companion

**Purpose:** Integrates Node-RED with Home Assistant for advanced automation workflows.

**Configuration:**

1. Install Node-RED (if not already installed)
2. Add the Node-RED Companion integration
3. Configure the connection to your Node-RED instance

**Usage:**

- Access Node-RED flows from Home Assistant
- Create complex automations using Node-RED's visual editor
- Integrate with Home Assistant entities and services

### Auto Backup

**Purpose:** Automated backup service with retention policies and generational backup schemes.

**Configuration:**

1. Go to Settings → Devices & Services
2. Add the Auto Backup integration
3. Configure retention policies:
   - Keep 7 daily backups
   - Keep 4 weekly backups
   - Keep 12 monthly backups
4. Enable automatic deletion of expired backups

**Usage:**

- Automatic daily backups at 2 AM (configured in automations)
- Manual backups via script: `script.manual_backup`
- Custom backups via script: `script.backup_custom`

See [Backup Configuration Guide](backup-configuration.md) for detailed information.

### Card Mod

**Purpose:** Add CSS styles to (almost) any Lovelace card for advanced customization.

**Configuration:**

1. Installed via HACS
2. Automatically added to Lovelace resources
3. Can be configured as a frontend module for better performance

**Usage:**
Add `card_mod` to any card configuration:

```yaml
type: entities
entities:
  - entity: light.example
card_mod:
  style: |
    ha-card {
      background: var(--card-background-color);
      border-radius: 10px;
    }
```

### Mushroom Cards

**Purpose:** Beautiful, easy-to-use card collection for building modern dashboards.

**Configuration:**

1. Installed via HACS
2. Automatically added to Lovelace resources
3. Available in the card picker as "Custom: Mushroom"

**Usage:**

- Access via Dashboard UI editor
- Click "Add Card" → Search for "Mushroom"
- Choose from various card types:
  - Entity cards
  - Light cards
  - Climate cards
  - Media cards
  - And more

### UI Lovelace Minimalist

**Purpose:** Minimalist theme and card collection for Home Assistant.

**Configuration:**

1. Installed via HACS
2. Configured as an integration
3. Available in themes and card picker

**Usage:**

- Apply the minimalist theme
- Use minimalist cards in dashboards
- Customize appearance via theme settings

## Configuration

### HACS Setup

1. HACS is pre-installed in this instance
2. Access via sidebar → HACS
3. Browse and install add-ons from the community store

### Resource Management

Most HACS add-ons automatically add resources to Lovelace. To view/manage:

1. Go to Settings → Dashboards
2. Click the three dots (⋮) → Resources
3. View all installed resources

### Frontend Modules

Some add-ons (like Card Mod) can be installed as frontend modules for better performance:

1. Add to `configuration.yaml`:

   ```yaml
   frontend:
     extra_module_url:
       - /hacsfiles/lovelace-card-mod/card-mod.js?hacstag=12345678901
   ```

2. Restart Home Assistant

## Usage Examples

### Using Adaptive Lighting

```yaml
# In automations.yaml
- id: 'enable_adaptive_lighting'
  alias: 'Enable Adaptive Lighting'
  trigger:
    - platform: sun
      event: sunset
  action:
    - service: switch.turn_on
      target:
        entity_id: switch.adaptive_lighting_living_room
```

### Using Auto Backup

```yaml
# Manual backup via script
- service: script.manual_backup

# Custom backup with name
- service: script.backup_custom
  data:
    backup_name: "Before_update"
```

### Using Card Mod

```yaml
# Styled entity card
type: entities
title: Styled Card
entities:
  - entity: light.example
card_mod:
  style: |
    ha-card {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      border-radius: 15px;
    }
```

### Using Mushroom Cards

```yaml
# Mushroom entity card
type: custom:mushroom-entity-card
entity: light.example
name: Example Light
icon: mdi:lightbulb
```

## Updating Add-ons

1. Go to HACS → Integrations (or Frontend)
2. Find the add-on you want to update
3. Click "Update" if available
4. Restart Home Assistant if required

## Troubleshooting

### Add-on Not Working

1. Check if Home Assistant was restarted after installation
2. Verify the add-on is in the correct category (Integration vs Frontend)
3. Check Home Assistant logs for errors

### Resource Not Loading

1. Verify the resource is added in Dashboard Resources
2. Clear browser cache
3. Check the resource URL is correct

### Performance Issues

1. Consider installing as frontend module (for supported add-ons)
2. Check for conflicting add-ons
3. Review Home Assistant logs for errors

## Additional Resources

- [HACS Documentation](https://hacs.xyz/)
- [Home Assistant Community](https://community.home-assistant.io/)
- [Home Assistant Setup Guide](homeassistant-setup-guide.md)
