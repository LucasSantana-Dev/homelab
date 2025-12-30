# HACS Add-on Installer Guide

This script uses Selenium to automatically navigate Home Assistant and install HACS add-ons.

## Prerequisites

1. **Install Chrome/Chromium and ChromeDriver:**
   ```bash
   sudo apt-get update
   sudo apt-get install -y chromium-browser chromium-chromedriver
   ```

2. **Install Python dependencies:**
   ```bash
   cd /home/luk-server/homelab/scripts
   pip3 install -r requirements-hacs-installer.txt
   ```

## Usage

### Basic Usage

```bash
cd /home/luk-server/homelab/scripts
python3 install_hacs_addons.py --username YOUR_USERNAME --password YOUR_PASSWORD
```

### Headless Mode (no browser window)

```bash
python3 install_hacs_addons.py --username YOUR_USERNAME --password YOUR_PASSWORD --headless
```

## Add-ons to Install

The script will install the following HACS add-ons:

### Integrations
- **Adaptive Lighting** - Circadian lighting automation
- **Auto-entities** - Dynamic dashboard entities

### Frontend Plugins (Lovelace Cards)
- **Card Mod** - Advanced card styling
- **Mini Graph Card** - Enhanced graphs
- **Mushroom Cards** - Modern card collection
- **Layout Card** - Advanced layouts
- **State Switch** - Conditional card display
- **Button Card** - Customizable button cards

## Manual Installation Alternative

If the automated script doesn't work, you can install add-ons manually:

1. **Access Home Assistant:**
   - Navigate to `http://100.64.0.10:8123`
   - Log in with your credentials

2. **Open HACS:**
   - Click on "HACS" in the sidebar
   - Or navigate to `http://100.64.0.10:8123/hacs`

3. **Install Integrations:**
   - Go to "Integrations" tab
   - Click "+ Explore & Download Repositories"
   - Search for the integration name
   - Click "Download"
   - Restart Home Assistant

4. **Install Frontend Plugins:**
   - Go to "Frontend" tab
   - Click "+ Explore & Download Repositories"
   - Search for the plugin name
   - Click "Download"
   - Refresh the browser (Ctrl+F5)

## Troubleshooting

### ChromeDriver Issues

If you get ChromeDriver errors:
```bash
# Check ChromeDriver version
chromedriver --version

# Update ChromeDriver if needed
sudo apt-get update
sudo apt-get install --reinstall chromium-chromedriver
```

### Login Issues

- Make sure your Home Assistant credentials are correct
- Check that Home Assistant is accessible at the configured URL
- Verify you're not already logged in (try incognito mode)

### HACS Not Found

- Ensure HACS is installed in Home Assistant
- Check that HACS is accessible via the sidebar
- Try navigating directly to `/hacs` URL

### Installation Fails

- Some add-ons may already be installed
- Check HACS logs in Home Assistant
- Try manual installation for specific add-ons

## Customizing Add-ons

Edit `install_hacs_addons.py` and modify the `HACS_ADDONS` list:

```python
HACS_ADDONS = [
    {
        "type": "integration",  # or "plugin"
        "name": "Your Add-on Name",
        "repository": "https://github.com/user/repo"
    },
    # Add more add-ons...
]
```
