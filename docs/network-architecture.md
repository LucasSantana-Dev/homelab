# 🏠 Homelab Network Architecture

## 🎯 **Optimal Configuration Strategy**

### **Three-Tier Access Model**

```
┌─────────────────────────────────────────────────────────────┐
│                    ACCESS METHODS                           │
├─────────────────────────────────────────────────────────────┤
│ 1. LOCALHOST    │ 127.0.0.1:PORT  │ Server-only access      │
│ 2. TAILSCALE    │ 100.64.0.10  │ Private network access  │
│ 3. CLOUDFLARE   │ *.domain.com    │ Public internet access  │
└─────────────────────────────────────────────────────────────┘
```

## 🔒 **Security-First Approach**

### **Service Classification**

#### **🔐 Private Services (Tailscale Only)**
- **Portainer** - Docker management (sensitive)
- **Grafana** - Monitoring dashboards (sensitive)
- **Prometheus** - Metrics collection (sensitive)
- **What's Up Docker** - Update monitoring (sensitive)

#### **🌐 Public Services (Cloudflare + Tailscale)**
- **Homepage** - Dashboard (public-friendly)
- **Home Assistant** - Home automation (public-friendly)
- **Stremio** - Media streaming (public-friendly)
- **Uptime Kuma** - Public status page (public-friendly)

#### **🏠 Local Services (Localhost Only)**
- **Pi-hole** - DNS filtering (local network only)
- **Node Exporter** - System metrics (local only)

## 🚀 **Implementation Strategy**

### **1. Fix Cloudflare Tunnel**
```bash
# Get proper tunnel token
cloudflared tunnel login
cloudflared tunnel create homelab
cloudflared tunnel route dns homelab *.homelab.example.com
```

### **2. Optimize Tailscale Configuration**
```bash
# Configure DNS properly
sudo tailscale set --advertise-routes=192.168.0.0/24
sudo tailscale set --accept-routes
```

### **3. Service-Specific Binding**
- **Private Services**: Bind only to Tailscale IP
- **Public Services**: Bind to localhost + Tailscale + Cloudflare
- **Local Services**: Bind only to localhost

## 📊 **Benefits of This Approach**

### **Security**
- ✅ Sensitive services only accessible via Tailscale
- ✅ Public services properly secured with Cloudflare
- ✅ Local services isolated from external access

### **Performance**
- ✅ Tailscale provides low-latency private access
- ✅ Cloudflare provides global CDN and DDoS protection
- ✅ Local access for server management

### **Flexibility**
- ✅ Choose access method based on use case
- ✅ Easy to add/remove services from public access
- ✅ Granular control over service exposure
