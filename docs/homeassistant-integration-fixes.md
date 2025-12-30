# Home Assistant Integration Fixes

## Meross Cloud Integration Fix

### Issue
The Meross Cloud integration was failing with permission errors when trying to install the `meross_iot` Python package.

### Solution
1. **Updated Docker Compose configuration** to set `PYTHONUSERBASE=/config/deps` environment variable
   - This tells Python to install packages in the config directory instead of system directories
   - The deps directory is writable by the container user

2. **Ensured proper permissions** on the deps directory
   - Directory is owned by the container user (PUID:PGID)
   - Permissions set to 755 for proper access

### How to Apply
1. Restart the Home Assistant container:
   ```bash
   cd /home/luk-server/homelab
   docker compose restart homeassistant
   ```

2. Wait for Home Assistant to fully start (check logs)

3. Reconfigure Meross Cloud integration:
   - Go to Settings > Devices & Services
   - Remove the Meross Cloud integration if it exists
   - Add Meross Cloud integration again
   - Follow the setup wizard

### Verification
Check Home Assistant logs for successful package installation:
```bash
docker logs homeassistant | grep -i meross
```

You should see successful package installation instead of permission errors.

## Xiaomi Home Integration Token Refresh

### Issue
Xiaomi Home integration shows "invalid refresh token" error, requiring token refresh.

### Solution
1. **Access Xiaomi Home integration settings:**
   - Go to Settings > Devices & Services
   - Find "Xiaomi Home" integration
   - Click "Configure"

2. **Refresh OAuth token:**
   - The integration should prompt for re-authentication
   - Follow the OAuth flow to get a new token
   - Save the new credentials

3. **Alternative: Manual token refresh:**
   - If automatic refresh doesn't work, remove and re-add the integration
   - You'll need to re-authenticate with Xiaomi account

### Prevention
- Tokens expire after a period of inactivity
- Set up periodic checks to refresh tokens before expiration
- Monitor integration status in Home Assistant

## Weather Integration Duplicate ID Fix

### Issue
Weather integration shows duplicate entity ID error: "Platform met does not generate unique IDs. ID home already exists"

### Solution
1. **Remove duplicate weather entities:**
   - Go to Settings > Devices & Services
   - Find weather integrations
   - Remove duplicate weather entities

2. **Configure unique entity IDs:**
   - When adding weather integration, ensure unique names
   - Use location-specific names (e.g., "weather_home", "weather_office")

3. **Update configuration.yaml if using YAML:**
   ```yaml
   weather:
     - platform: met
       name: "Home Weather"
       latitude: !secret latitude
       longitude: !secret longitude
   ```

### Verification
Check for duplicate entities:
```bash
docker logs homeassistant | grep -i "duplicate\|weather"
```

All weather entities should have unique IDs.
