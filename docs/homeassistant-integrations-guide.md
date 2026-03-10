# Home Assistant Smart Home Integrations Guide

This guide covers the setup and configuration of smart home integrations in Home Assistant.

## Table of Contents

1. [Configured Integrations](#configured-integrations)
2. [Xiaomi Home](#xiaomi-home)
3. [LG ThinQ](#lg-thinq)
4. [Tuya](#tuya)
5. [Meross Cloud](#meross-cloud)
6. [Google Assistant](#google-assistant)
7. [Amazon Alexa](#amazon-alexa)
8. [Troubleshooting](#troubleshooting)

## Configured Integrations

| Integration | Status | Devices | Notes |
|-------------|--------|---------|-------|
| Xiaomi Home | Working | 4 | Token may need periodic refresh |
| LG ThinQ | Working | 1 | Native integration |
| Tuya | Working | 2 | Cloud push support |
| Meross Cloud | Needs Auth | - | Token expired, needs re-authentication |
| Google Assistant | Template | - | Requires GCP setup |
| Amazon Alexa | Template | - | Requires AWS/Amazon setup |

## Xiaomi Home

### Overview

Xiaomi Home integration (via HACS) provides control of Xiaomi/Mi smart home devices.

### Configured Devices

- **Luz Banheiro** - Yeelight Color5 (Bathroom)
- **Luz Principal** - Yeelight Color5 (Bedroom)
- **Luz Secundária** - Yeelight Color5 (Bedroom)
- **Rogério** - Xiaomi Robot Vacuum (Living Room)

### Token Refresh

Xiaomi OAuth tokens expire periodically. To refresh:

1. Go to **Settings > Devices & Services**
2. Click on **Xiaomi Home**
3. Click **Configure** on your hub
4. Follow the re-authentication flow

Documentation: `/config/xiaomi_token_refresh.md`

## LG ThinQ

### Overview

Native Home Assistant integration for LG ThinQ appliances (added in 2024.11).

### Supported Devices

- Air conditioners
- Refrigerators
- Washing machines
- Dryers
- Dishwashers

### Setup

1. Go to **Settings > Devices & Services**
2. Click **Add Integration**
3. Search for "LG ThinQ"
4. Log in with your LG account
5. Select devices to import

## Tuya

### Overview

Native integration with Tuya/Smart Life cloud push support.

### Prerequisites

1. Tuya IoT Platform account (<https://iot.tuya.com/>)
2. Cloud Project with "Smart Home" industry
3. Access ID and Access Secret from the project

### Setup

1. Create account at <https://iot.tuya.com/>
2. Create a Cloud Project
3. Link your Smart Life/Tuya app account
4. Go to **Settings > Devices & Services**
5. Add "Tuya" integration
6. Enter Access ID and Access Secret

## Meross Cloud

### Overview

HACS integration for Meross smart devices.

### Re-authentication Required

The Meross Cloud token has expired. To re-authenticate:

1. Go to **Settings > Devices & Services**
2. Find "Meross Cloud IoT" in the Discovered section
3. Click **Reconfigure**
4. Enter your Meross account credentials

### Troubleshooting

If authentication fails:

- Verify your Meross account credentials
- Check if Meross servers are accessible
- Try the app first to ensure account works

## Google Assistant

### Overview

Control Home Assistant devices with Google Home/Assistant voice commands.

### Prerequisites

1. Google Cloud Platform account
2. Actions on Google project
3. Home Assistant accessible via HTTPS (Cloudflare Tunnel configured)

### Setup Steps

#### 1. Create Google Cloud Project

```
1. Go to https://console.cloud.google.com/
2. Create a new project
3. Enable the HomeGraph API
4. Create a service account with "Service Account Token Creator" role
5. Download JSON key file
```

#### 2. Create Actions on Google Project

```
1. Go to https://console.actions.google.com/
2. Create new project
3. Select "Smart Home"
4. Set fulfillment URL to: https://your-domain/api/google_assistant
```

#### 3. Configure Home Assistant

Place the service account JSON in `/config/google_service_account.json`

Update `secrets.yaml`:

```yaml
google_assistant_project_id: your-project-id
google_assistant_pin: "1234"
```

Uncomment in `configuration.yaml`:

```yaml
google_assistant: !include voice_assistants.yaml
```

## Amazon Alexa

### Overview

Control Home Assistant devices with Amazon Alexa voice commands.

### Prerequisites

1. Amazon Developer account
2. AWS account (for Lambda function)
3. Home Assistant accessible via HTTPS

### Setup Steps

#### 1. Create Alexa Skill

```
1. Go to https://developer.amazon.com/alexa/console/ask
2. Create new skill (Smart Home type)
3. Note the Skill ID
```

#### 2. Create AWS Lambda Function

```
1. Go to AWS Console > Lambda
2. Create function with Python runtime
3. Deploy Home Assistant skill handler code
4. Link to Alexa skill
```

#### 3. Configure Account Linking

```
1. In Alexa Developer Console, set up OAuth
2. Use Home Assistant's OAuth endpoints
3. Configure redirect URIs
```

#### 4. Configure Home Assistant

Update `secrets.yaml`:

```yaml
alexa_client_id: your-client-id
alexa_client_secret: your-client-secret
```

Uncomment in `configuration.yaml`:

```yaml
alexa: !include voice_assistants.yaml
```

## Troubleshooting

### Common Issues

#### Integration Won't Load

1. Check Home Assistant logs: **Settings > System > Logs**
2. Verify credentials in `secrets.yaml`
3. Restart Home Assistant after changes

#### Devices Not Appearing

1. Check if integration is configured correctly
2. Verify devices are online in their native apps
3. Try reloading the integration

#### Token Expired

Cloud-based integrations (Xiaomi, Meross) may have token expiration issues:

1. Go to the integration settings
2. Look for "Reconfigure" or "Reauthenticate" option
3. Log in again with your credentials

### Log Locations

- Home Assistant Core logs: **Settings > System > Logs**
- Docker logs: `docker logs homeassistant`

### Getting Help

- Home Assistant Community: <https://community.home-assistant.io/>
- Integration documentation: <https://www.home-assistant.io/integrations/>
