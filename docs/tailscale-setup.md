# Homelab Tailscale-Only Configuration

This guide explains how to configure your homelab to be accessible only through Tailscale, providing secure private access to your services.

## 🔒 Security Benefits

- **Private Network Access**: Services are only accessible to devices connected to your Tailscale network
- **No Public Exposure**: Eliminates the need for complex firewall rules or VPN setup
- **Easy Device Management**: Add/remove devices through Tailscale's web interface
- **Encrypted Traffic**: All traffic is encrypted through Tailscale's WireGuard-based network

## 📋 Prerequisites

1. **Tailscale Account**: Sign up at [tailscale.com](https://tailscale.com)
2. **Tailscale Installed**: Install Tailscale on your server and all devices you want to access from
3. **Network Access**: Ensure your server can connect to the internet

## 🚀 Quick Setup

### 1. Switch to Tailscale-Only Mode

```bash
# Run the configuration script
./scripts/switch-to-tailscale.sh
```

This script will:

- Backup your current configuration
- Configure all services to bind only to your Tailscale IP
- Set up nginx reverse proxy for easier access
- Start services in Tailscale-only mode

### 2. Access Your Services

After running the script, your services will be accessible at:

- **Homepage Dashboard**: `http://YOUR_TAILSCALE_IP:3000`
- **Home Assistant**: `http://YOUR_TAILSCALE_IP:8123`
- **Portainer**: `http://YOUR_TAILSCALE_IP:9000`
- **Uptime Kuma**: `http://YOUR_TAILSCALE_IP:3001`
- **What's Up Docker**: `http://YOUR_TAILSCALE_IP:3003`
- **Grafana**: `http://YOUR_TAILSCALE_IP:3002`
- **Prometheus**: `http://YOUR_TAILSCALE_IP:9091`
- **Stremio**: `http://YOUR_TAILSCALE_IP:11470`
- **Pi-hole**: `http://YOUR_TAILSCALE_IP:8054`

## 🔧 Configuration Details

### Docker Compose Changes

The Tailscale configuration uses `docker-compose.tailscale.yml` which:

1. **Binds to Tailscale IP**: All services bind to `YOUR_TAILSCALE_IP:PORT` instead of `0.0.0.0:PORT`
2. **Custom Network**: Uses a dedicated Tailscale network for service communication
3. **DNS Configuration**: Pi-hole DNS still accessible for network-wide ad blocking

### Nginx Reverse Proxy

An optional nginx reverse proxy is included for easier access:

- **Configuration**: `appdata/nginx/nginx.conf`
- **Service Routes**: `appdata/nginx/conf.d/default.conf`
- **Security Headers**: Includes security headers for better protection

## 🔄 Switching Between Modes

### Switch to Tailscale-Only

```bash
./scripts/switch-to-tailscale.sh
```

### Switch Back to Public Access

```bash
./scripts/switch-to-public.sh
```

## 📱 Device Setup

### Install Tailscale on Devices

1. **Desktop/Laptop**: Download from [tailscale.com](https://tailscale.com)
2. **Mobile**: Install from App Store/Google Play
3. **Other Servers**: Install Tailscale and join the same network

### Connect Devices

1. Open Tailscale app
2. Sign in with your account
3. Connect to your network
4. Access services using the Tailscale IP addresses

## 🛡️ Security Considerations

### Access Control

- Only devices connected to your Tailscale network can access services
- You can manage device access through Tailscale's admin console
- Devices can be removed instantly if compromised

### Network Isolation

- Services are isolated from the public internet
- No need for complex firewall rules
- Traffic is encrypted end-to-end

### Best Practices

1. **Regular Updates**: Keep Tailscale and services updated
2. **Device Management**: Remove unused devices from your network
3. **Access Logs**: Monitor access through Tailscale's dashboard
4. **Backup Access**: Keep one device with public access as backup

## 🔍 Troubleshooting

### Services Not Accessible

1. **Check Tailscale Status**:

   ```bash
   tailscale status
   ```

2. **Verify IP Binding**:

   ```bash
   docker-compose -f docker-compose.tailscale.yml ps
   ```

3. **Check Service Logs**:

   ```bash
   docker-compose -f docker-compose.tailscale.yml logs [service-name]
   ```

### Network Issues

1. **Restart Tailscale**:

   ```bash
   sudo tailscale down
   sudo tailscale up
   ```

2. **Check Network Connectivity**:

   ```bash
   ping YOUR_TAILSCALE_IP
   ```

### Reverting to Public Access

If you need to revert to public access:

```bash
./scripts/switch-to-public.sh
```

## 📊 Monitoring

### Service Health

- Use Uptime Kuma to monitor service availability
- Check Grafana dashboards for system metrics
- Monitor through Portainer for container status

### Network Monitoring

- Tailscale provides network usage statistics
- Monitor device connections through Tailscale dashboard
- Check service logs for access patterns

## 🔧 Advanced Configuration

### Custom Domains

You can set up custom domains by:

1. Adding DNS records pointing to your Tailscale IP
2. Configuring nginx with SSL certificates
3. Using Tailscale's MagicDNS feature

### Access Control Lists (ACLs)

Configure Tailscale ACLs for fine-grained access control:

1. Access Tailscale admin console
2. Configure ACLs to restrict access between devices
3. Set up device-specific access rules

## 📝 File Structure

```
homelab/
├── docker-compose.yml              # Original public configuration
├── docker-compose.tailscale.yml    # Tailscale-only configuration
├── scripts/
│   ├── switch-to-tailscale.sh     # Switch to Tailscale mode
│   └── switch-to-public.sh        # Switch to public mode
├── appdata/nginx/                  # Nginx configuration
│   ├── nginx.conf
│   └── conf.d/default.conf
└── TAILSCALE_SETUP.md             # This documentation
```
