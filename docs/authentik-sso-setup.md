# Authentik SSO Setup Guide

## Overview

This guide documents the setup and configuration of Authentik as a centralized Single Sign-On (SSO) identity provider for critical homelab services. Authentik provides OAuth2/OIDC authentication for Grafana, Portainer, n8n, Nextcloud, Jellyfin, and Vaultwarden.

## Prerequisites

- Authentik services deployed (`authentik-server`, `authentik-worker`, `authentik-db`, `authentik-redis`)
- Nginx reverse proxy configured for `auth.homelab.example.com`
- SSL certificate valid for `*.homelab.example.com`
- Admin access to all services to be integrated

## Phase 1 Edge Policy (Required Defaults)

Use these defaults for the homelab public edge rollout:

- Primary login source: **GitHub**
- Keep one **local break-glass admin** account
- Access allowlist: exact email + exact GitHub username
- MFA: required for interactive logins
- Session validity: 7 days

### GitHub Source + Break-Glass Local Account

1. Go to **Directory > Federation and Social login > Sources > Create**.
2. Select **GitHub Source**.
3. Configure your GitHub OAuth app callback URL:
   - `https://auth.homelab.example.com/source/oauth/callback/github/`
4. Keep local username/password auth enabled for one emergency admin account only.

### Allowlist Policy (Email + GitHub Username)

Create an **Expression Policy** and attach it to the Authentik flow used by protected applications:

```python
allowed_email = "YOUR_ALLOWED_EMAIL"
allowed_github = "YOUR_ALLOWED_GITHUB_USERNAME"

email_ok = request.user.email == allowed_email
github_ok = False

for ident in request.user.identities.all():
    if ident.provider and ident.provider.name.lower().startswith("github"):
        username = ident.extra_data.get("login", "")
        github_ok = username == allowed_github
        break

return email_ok and github_ok
```

Set values from `.env`:

- `AUTHENTIK_ALLOWED_EMAIL`
- `AUTHENTIK_ALLOWED_GITHUB_USERNAME`

### MFA + Session Policy

1. MFA:
   - **System > Settings > Security** -> enforce MFA for interactive users.
2. Session lifetime:
   - Set interactive session validity to 7 days (`AUTHENTIK_SESSION_DAYS=7`).
3. Keep one break-glass account enrolled in MFA and stored in password manager.

### Proxy Provider / Outpost for Nginx Forward Auth

Nginx forward-auth requires the outpost endpoint to exist. If
`/outpost.goauthentik.io/auth/nginx` returns 404, create/attach a proxy provider:

1. **Applications > Providers > Create** -> **Proxy Provider**.
2. Set **External host** to the protected domain(s) (one provider per domain or grouped design).
3. Attach provider to corresponding **Application**.
4. Ensure an **Outpost** is deployed for proxy integration.
5. Re-check:
   - `curl -I https://auth.homelab.example.com/outpost.goauthentik.io/auth/nginx`
   - Expected: not `404` (typically `401/302` for unauthenticated requests).

## Initial Configuration

### 1. Access Authentik Admin Interface

1. Navigate to: <https://auth.homelab.example.com>
2. On first access, you'll be prompted to create an admin account
3. Username: `admin` (or your preference)
4. Password: Use a strong password (store in password manager)
5. Email: Your admin email address

### 2. Configure Authentik Settings

After login, navigate to **Admin Interface**:

1. **System > Settings > General**:
   - Domain: `auth.homelab.example.com`
   - Branding: "Homelab SSO"
   - Footer: (optional) Custom footer text

2. **System > Settings > Security**:
   - Enable: "Require 2FA for admin users" (recommended)
   - Session timeout: 7 days (adjust as needed)

### 3. Create User Groups

Navigate to **Directory > Groups > Create**:

#### Administrator Groups

1. **Grafana Admins**
   - Name: `Grafana Admins`
   - Description: Full admin access to Grafana dashboards

2. **Portainer Admins**
   - Name: `Portainer Admins`
   - Description: Full admin access to Portainer container management

3. **n8n Admins**
   - Name: `n8n Admins`
   - Description: Full access to n8n workflow automation

#### Editor/Viewer Groups

1. **Grafana Editors**
   - Name: `Grafana Editors`
   - Description: Edit dashboards in Grafana

2. **Grafana Viewers**
   - Name: `Grafana Viewers`
   - Description: View-only access to Grafana dashboards

### 4. Assign Users to Groups

1. Navigate to **Directory > Users**
2. Select your admin user
3. Go to **Groups** tab
4. Add user to appropriate groups (e.g., `Grafana Admins`, `Portainer Admins`, `n8n Admins`)

## Service Integrations

### Grafana OAuth Integration

#### Step 1: Create OAuth2 Provider in Authentik

1. Navigate to **Applications > Providers > Create**
2. Select **OAuth2/OpenID Provider**
3. Configure:
   - **Name**: `Grafana OAuth Provider`
   - **Authorization flow**: `Implicit Flow` + `Authorization Code`
   - **Client Type**: `Confidential`
   - **Redirect URIs**: `https://grafana.homelab.example.com/login/generic_oauth`
   - **Scopes**: `openid`, `profile`, `email`
   - **Subject mode**: `Based on the User's Email`
4. Click **Create**
5. **Important**: Copy the **Client ID** and **Client Secret** (you'll need these)

#### Step 2: Create Application in Authentik

1. Navigate to **Applications > Applications > Create**
2. Configure:
   - **Name**: `Grafana`
   - **Slug**: `grafana`
   - **Provider**: Select `Grafana OAuth Provider` (created above)
   - **Policy engine mode**: `all`
   - **UI settings**: (optional) Upload Grafana icon
3. Click **Create**

#### Step 3: Configure Grafana

Create/edit `config/grafana/grafana.ini`:

```ini
[server]
domain = grafana.homelab.example.com
root_url = https://grafana.homelab.example.com
enforce_domain = true

[auth.generic_oauth]
enabled = true
name = Authentik
allow_sign_up = true
client_id = <CLIENT_ID_FROM_AUTHENTIK>
client_secret = <CLIENT_SECRET_FROM_AUTHENTIK>
scopes = openid profile email
auth_url = https://auth.homelab.example.com/application/o/authorize/
token_url = https://auth.homelab.example.com/application/o/token/
api_url = https://auth.homelab.example.com/application/o/userinfo/
role_attribute_path = contains(groups[*], 'Grafana Admins') && 'Admin' || contains(groups[*], 'Grafana Editors') && 'Editor' || 'Viewer'
allow_assign_grafana_admin = true

[auth]
disable_login_form = true
```

#### Step 4: Restart Grafana

```bash
docker compose restart grafana
```

#### Step 5: Test Login

1. Navigate to <https://grafana.homelab.example.com>
2. Click **Sign in with Authentik**
3. Login with your Authentik credentials
4. Verify role assignment (Admin/Editor/Viewer based on group membership)

> Recovery path: temporarily set `disable_login_form = false` (or `GRAFANA_DISABLE_LOGIN_FORM=false`) and restart Grafana to regain local admin access if SSO is misconfigured.

---

### Portainer OAuth Integration

#### Step 1: Create OAuth2 Provider in Authentik

1. Navigate to **Applications > Providers > Create**
2. Select **OAuth2/OpenID Provider**
3. Configure:
   - **Name**: `Portainer OAuth Provider`
   - **Authorization flow**: `Authorization Code`
   - **Client Type**: `Confidential`
   - **Redirect URIs**: `https://portainer.homelab.example.com`
   - **Scopes**: `openid`, `profile`, `email`, `groups`
4. Click **Create**
5. **Important**: Copy the **Client ID** and **Client Secret**

#### Step 2: Create Application in Authentik

1. Navigate to **Applications > Applications > Create**
2. Configure:
   - **Name**: `Portainer`
   - **Slug**: `portainer`
   - **Provider**: Select `Portainer OAuth Provider`
3. Click **Create**

#### Step 3: Configure Portainer

1. Access Portainer: <https://portainer.homelab.example.com>
2. Navigate to **Settings > Authentication**
3. Enable **OAuth**:
   - **Provider**: Custom
   - **Automatic user provision**: Enable
   - **Client ID**: `<CLIENT_ID_FROM_AUTHENTIK>`
   - **Client Secret**: `<CLIENT_SECRET_FROM_AUTHENTIK>`
   - **Authorization URL**: `https://auth.homelab.example.com/application/o/authorize/`
   - **Access token URL**: `https://auth.homelab.example.com/application/o/token/`
   - **Resource URL**: `https://auth.homelab.example.com/application/o/userinfo/`
   - **Redirect URL**: `https://portainer.homelab.example.com`
   - **User identifier**: `email`
   - **Scopes**: `openid profile email groups`
4. Click **Save settings**

> Keep one local Portainer admin account as break-glass fallback.

#### Step 4: Configure Team Mappings (Optional)

In Portainer Settings > Authentication > OAuth:

- Map Authentik groups to Portainer teams
- Example: `Portainer Admins` → Portainer `administrators` team

#### Step 5: Test Login

1. Logout from Portainer
2. Click **OAuth login**
3. Authenticate with Authentik
4. Verify access and permissions

---

### n8n OAuth Integration

#### Step 1: Create OAuth2 Provider in Authentik

1. Navigate to **Applications > Providers > Create**
2. Select **OAuth2/OpenID Provider**
3. Configure:
   - **Name**: `n8n OAuth Provider`
   - **Authorization flow**: `Authorization Code`
   - **Client Type**: `Confidential`
   - **Redirect URIs**: `https://n8n.homelab.example.com/rest/oauth2-credential/callback`
   - **Scopes**: `openid`, `profile`, `email`
4. Click **Create**
5. **Important**: Copy the **Client ID** and **Client Secret**

#### Step 2: Create Application in Authentik

1. Navigate to **Applications > Applications > Create**
2. Configure:
   - **Name**: `n8n`
   - **Slug**: `n8n`
   - **Provider**: Select `n8n OAuth Provider`
3. Click **Create**

#### Step 3: Update n8n Environment Variables

Edit `docker-compose.yml` for the n8n service, add these environment variables:

```yaml
n8n:
  environment:
    # Existing variables...
    - N8N_AUTH_OAUTH2_ENABLED=true
    - N8N_AUTH_OAUTH2_CLIENT_ID=<CLIENT_ID_FROM_AUTHENTIK>
    - N8N_AUTH_OAUTH2_CLIENT_SECRET=<CLIENT_SECRET_FROM_AUTHENTIK>
    - N8N_AUTH_OAUTH2_AUTHORIZE_URL=https://auth.homelab.example.com/application/o/authorize/
    - N8N_AUTH_OAUTH2_TOKEN_URL=https://auth.homelab.example.com/application/o/token/
    - N8N_AUTH_OAUTH2_USER_INFO_URL=https://auth.homelab.example.com/application/o/userinfo/
    - N8N_AUTH_OAUTH2_SCOPE=openid profile email
```

#### Step 4: Restart n8n

```bash
docker compose restart n8n
```

#### Step 5: Test Login

1. Navigate to <https://n8n.homelab.example.com>
2. Login with Authentik credentials
3. Verify workflow access

---

## Advanced Configurations

### Configure Nextcloud OIDC (Optional)

Nextcloud supports OIDC via the `user_oidc` app:

1. In Nextcloud, install **OpenID Connect user backend** app
2. Configure OIDC:
   - **Provider URL**: `https://auth.homelab.example.com/application/o/authorize/`
   - **Client ID**: (from Authentik provider)
   - **Client Secret**: (from Authentik provider)

### Configure Jellyfin OIDC (Optional)

Jellyfin supports SSO via plugins:

1. Install **SSO-Plugin** in Jellyfin
2. Configure OpenID:
   - **Provider**: Authentik
   - **Authority**: `https://auth.homelab.example.com`
   - **Client ID**: (from Authentik provider)
   - **Client Secret**: (from Authentik provider)

### Configure Vaultwarden SSO (Vaultwarden doesn't support OIDC natively)

Note: Vaultwarden (Bitwarden) doesn't support OAuth/OIDC SSO. Consider using Authentik for password management instead, or keep Vaultwarden separate.

---

## User Management

### Adding New Users

1. Navigate to **Directory > Users > Create**
2. Fill in user details:
   - **Username**: Unique username
   - **Name**: Full name
   - **Email**: User email (required for OIDC)
   - **Password**: Set initial password (user can change)
3. Assign user to appropriate groups
4. Send invitation email (optional)

### Managing User Access

**Grant Admin Access**:

1. Add user to `Grafana Admins`, `Portainer Admins`, or `n8n Admins` groups

**Revoke Access**:

1. Remove user from service groups
2. Or disable user account: **Directory > Users > [User] > Disable**

### Password Reset

Users can reset passwords via:

1. **Forgot Password** link on Authentik login page
2. Or admin can reset: **Directory > Users > [User] > Set password**

---

## Security Best Practices

### Enable 2FA for Admins

1. **System > Settings > Security**
2. Enable: **Require 2FA for admin users**
3. Admins must configure 2FA on next login

### Configure Session Policies

1. **Policies > Policies > Create**
2. **Policy Type**: Reputation
3. Configure:
   - **Failed login threshold**: 5 attempts
   - **Lockout duration**: 30 minutes
   - **Trusted networks**: Add Tailscale subnet (100.0.0.0/8)

### Audit Logs

Monitor authentication events:

1. **Events > System Tasks**
2. Review login attempts, failures, and policy violations
3. Export logs for external SIEM (optional)

### API Access Tokens

For automation:

1. **Directory > Tokens & App passwords**
2. Create tokens for service accounts
3. Store securely in environment variables

---

## Troubleshooting

### Grafana OAuth Redirect Loop

**Symptom**: Redirects endlessly between Grafana and Authentik

**Solution**:

1. Verify `root_url` in `grafana.ini` matches Nginx proxy URL
2. Check redirect URI in Authentik provider exactly matches Grafana callback
3. Ensure `enforce_domain = true` in Grafana config

### Portainer OAuth: "Invalid redirect URI"

**Symptom**: Error after OAuth login

**Solution**:

1. Verify redirect URI in Authentik is exactly: `https://portainer.homelab.example.com`
2. No trailing slash
3. Must match Nginx server_name

### n8n OAuth: "Authorization code invalid"

**Symptom**: Failed to complete OAuth flow

**Solution**:

1. Ensure n8n callback URL is correct: `https://n8n.homelab.example.com/rest/oauth2-credential/callback`
2. Check n8n environment variables are properly set
3. Restart n8n after environment changes

### Users Don't Get Assigned Correct Grafana Roles

**Symptom**: All users login as Viewer

**Solution**:

1. Verify users are in correct Authentik groups (`Grafana Admins`, `Grafana Editors`)
2. Check `role_attribute_path` in grafana.ini exactly matches group names
3. Group names are case-sensitive

### Authentik Login Page Not Accessible

**Symptom**: 502 Bad Gateway or connection refused

**Solution**:

1. Check Authentik containers are running: `docker ps | grep authentik`
2. Verify database connectivity: `docker logs authentik-server`
3. Check Nginx reverse proxy config: `docker exec nginx-proxy nginx -t`

---

## Monitoring and Maintenance

### Check Authentik Health

```bash
# Verify all Authentik containers are healthy
docker ps --filter "name=authentik" --format "table {{.Names}}\t{{.Status}}"

# Check Authentik server logs
docker logs authentik-server --tail 50

# Check Authentik worker logs
docker logs authentik-worker --tail 50
```

### Backup Authentik Data

```bash
# Backup PostgreSQL database
docker exec authentik-db pg_dump -U authentik authentik > backups/authentik_db_$(date +%Y%m%d).sql

# Backup Authentik media files
tar -czf backups/authentik_media_$(date +%Y%m%d).tar.gz appdata/authentik/media/
```

### Update Authentik

```bash
# Pull latest image
docker pull ghcr.io/goauthentik/server:latest

# Restart services
docker compose up -d authentik-server authentik-worker

# Check logs for migration issues
docker logs authentik-server -f
```

---

## Next Steps

After completing Authentik setup:

1. **Test all integrations**: Verify OAuth login works for Grafana, Portainer, n8n
2. **Configure additional services**: Add Nextcloud, Jellyfin if desired
3. **Enable 2FA**: For admin accounts and critical users
4. **Document credentials**: Store OAuth client IDs/secrets in secure location
5. **Monitor logs**: Check for failed login attempts and anomalies
6. **Schedule backups**: Automate daily backup of Authentik database

## References

- [Authentik Documentation](https://goauthentik.io/docs/)
- [Grafana OAuth Configuration](https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/generic-oauth/)
- [Portainer OAuth Configuration](https://docs.portainer.io/admin/settings/authentication/oauth)
- [n8n OAuth Configuration](https://docs.n8n.io/hosting/configuration/user-management/#oauth)
