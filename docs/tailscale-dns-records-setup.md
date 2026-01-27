# Tailscale DNS Records Setup for Nextcloud

## Current Configuration

Based on your Tailscale DNS settings:
- **Tailnet DNS name**: `tailnet.example.ts.net`
- **MagicDNS**: Enabled ✅
- **Search Domain**: `homelab.example.com` ✅
- **Nameservers**: `100.100.100.100` (Cloudflare) ✅

## Missing: DNS Records

You need to add **DNS A records** to map your domain to your Tailscale IP.

## Step-by-Step Setup

### 1. Add DNS Records

1. In your Tailscale admin console, go to **DNS** section
2. Look for a section called **"DNS records"** or **"Custom DNS records"** (may be below the current view)
3. Click **"Add DNS record"** or similar button
4. Add the following records:

   **Record 1:**
   - **Domain**: `homelab.example.com`
   - **Type**: `A`
   - **Value**: `100.64.0.10`
   - **Description**: Main domain

   **Record 2:**
   - **Domain**: `*.homelab.example.com`
   - **Type**: `A`
   - **Value**: `100.64.0.10`
   - **Description**: Wildcard for all subdomains (cloud, auth, grafana, etc.)

### 2. Verify Device DNS Settings

On your device (where you're trying to access Nextcloud):

**iOS:**
1. Open Tailscale app
2. Go to Settings
3. Ensure "Use Tailscale DNS" is enabled
4. Restart Tailscale if needed

**Android:**
1. Open Tailscale app
2. Go to Settings
3. Enable "Use Tailscale DNS"
4. Restart Tailscale if needed

**macOS/Windows/Linux:**
1. Open Tailscale app
2. Settings → DNS
3. Enable "Use Tailscale DNS"
4. Restart Tailscale if needed

### 3. Test DNS Resolution

After adding records, wait 1-2 minutes for propagation, then test:

```bash
# On your device (not server)
nslookup cloud.homelab.example.com
# Should return: 100.64.0.10

# Or test with ping
ping cloud.homelab.example.com
# Should ping: 100.64.0.10
```

### 4. Alternative: Use Direct IP (Temporary)

While setting up DNS, you can use the direct IP:

**In Nextcloud Mobile App:**
- Server URL: `https://100.64.0.10:443`
- Note: Accept SSL certificate warning

**In Browser:**
- URL: `https://100.64.0.10:443`

## Troubleshooting

### DNS records not showing in Tailscale UI

If you don't see a "DNS records" section:
1. Check if you're on the Free plan (may have limitations)
2. Try refreshing the page
3. Look for "Custom DNS" or "DNS records" in a different tab/section
4. Check Tailscale documentation for your plan tier

### Still can't resolve after adding records

1. **Clear DNS cache on device:**
   - iOS: Restart device or toggle Tailscale off/on
   - Android: Restart device or clear app cache
   - macOS: `sudo dscacheutil -flushcache`
   - Windows: `ipconfig /flushdns`
   - Linux: `sudo systemd-resolve --flush-caches`

2. **Verify Tailscale DNS is enabled on device:**
   - Device must have "Use Tailscale DNS" enabled
   - Check Tailscale app settings

3. **Test from server:**
   ```bash
   # On server
   nslookup cloud.homelab.example.com 100.100.100.100
   # Should return: 100.64.0.10
   ```

## Current Status

✅ MagicDNS: Enabled  
✅ Search Domain: `homelab.example.com` configured  
❌ DNS A Records: Need to be added  
❓ Device DNS: Verify "Use Tailscale DNS" is enabled

## Quick Reference

- **Tailscale IP**: `100.64.0.10`
- **Domain**: `homelab.example.com`
- **Nextcloud URL**: `https://cloud.homelab.example.com`
- **Direct IP**: `https://100.64.0.10:443`
