# Weather Integration Duplicate ID Fix

## Issue

Error: `Platform met does not generate unique IDs. ID home already exists - ignoring weather.forecast_casa`

This occurs when multiple weather integrations try to use the same entity ID.

## Solution

### Method 1: Remove Duplicate via UI (Recommended)

1. **Open Home Assistant UI**
   - Navigate to: Settings > Devices & Services
   - Find all Weather integrations

2. **Identify Duplicates**
   - Look for multiple weather integrations with similar names
   - Check entity IDs in Developer Tools > States

3. **Remove Duplicates**
   - Click on duplicate weather integration
   - Click the three dots menu
   - Select "Delete"
   - Keep only one weather integration

4. **Re-add with Unique Name**
   - Click "+ Add Integration"
   - Search for "Met Office" or your weather provider
   - During setup, use a unique name (e.g., "Home Weather", "Office Weather")
   - Complete setup

### Method 2: Configure via YAML

If you prefer YAML configuration, add to `configuration.yaml`:

```yaml
weather:
  - platform: met
    name: "Home Weather"
    latitude: !secret latitude
    longitude: !secret longitude
    elevation: 0
    monitored_conditions:
      - weather
      - temperature
      - temperature_max
      - temperature_min
      - precipitation
      - wind_speed
      - wind_bearing
      - pressure
      - cloud_coverage
      - visibility
```

**Important:** Use unique `name` values for each weather entity.

### Verification

1. **Check Entities**
   - Go to Developer Tools > States
   - Search for "weather"
   - Verify all weather entities have unique IDs

2. **Check Logs**

   ```bash
   docker logs homeassistant | grep -i weather
   ```

   - Should not show duplicate ID errors

3. **Test Dashboard**
   - Add weather card to dashboard
   - Verify it displays correctly

## Prevention

- Always use unique names when adding weather integrations
- Check existing weather entities before adding new ones
- Use location-specific names (e.g., "Home", "Office", "Garden")
