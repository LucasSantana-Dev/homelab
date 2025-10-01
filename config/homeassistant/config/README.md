# Home Assistant Configuration

This directory contains the Home Assistant configuration files.

## Directory Structure

- `configuration.yaml` - Main configuration file
- `secrets.yaml` - Sensitive configuration (not in git)
- `resources.yaml` - Lovelace resources configuration
- `dashboards/` - Dashboard configurations
- `themes/` - Custom themes
- `scripts/` - Scripts, automations, and scenes
- `blueprints/` - Blueprint configurations
- `custom_components/` - Custom integrations (HACS, etc.)
- `backups/` - Automatic backups
- `www/` - Web assets

## Important Files

- `configuration.yaml` - Main configuration
- `secrets.yaml` - Contains sensitive data (API keys, passwords)
- `resources.yaml` - Lovelace dashboard resources
- `dashboards/dashboard_config.yaml` - Main dashboard configuration

## Security Note

The `secrets.yaml` file contains sensitive information and should never be committed to version control.
