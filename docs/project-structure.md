# 🏗️ Project Structure

This document describes the improved project structure for the homelab management system.

## 📁 **New Project Structure**

```
homelab/
├── 📁 homelab_manager/          # Main Python package (moved to root)
│   ├── __init__.py
│   ├── __main__.py
│   ├── interactive_cli.py       # Interactive CLI application
│   ├── mode_manager.py         # Mode switching (public/tailscale)
│   ├── security_tester.py      # Security testing and validation
│   ├── automation.py           # Automation tasks
│   ├── health.py              # Health monitoring
│   ├── updates.py              # Update management
│   ├── config.py              # Configuration management
│   ├── container_manager.py   # Container management
│   ├── cli_tools.py           # CLI tools
│   └── cli.py                 # Legacy CLI
├── 📁 config/                  # Service configurations
│   ├── 📁 nginx/              # Nginx configurations
│   │   ├── nginx.conf
│   │   ├── homelab-proxy.conf
│   │   └── nginx-config/
│   ├── 📁 homepage/           # Homepage configurations
│   │   ├── services.yaml
│   │   ├── widgets.yaml
│   │   ├── bookmarks.yaml
│   │   ├── settings.yaml
│   │   ├── docker.yaml
│   │   ├── kubernetes.yaml
│   │   ├── proxmox.yaml
│   │   ├── custom.css
│   │   ├── custom.js
│   │   └── logs/
│   ├── 📁 prometheus/          # Prometheus configurations
│   │   └── prometheus.yml
│   ├── 📁 grafana/            # Grafana configurations
│   │   ├── grafana.db
│   │   ├── csv/
│   │   ├── pdf/
│   │   ├── plugins/
│   │   ├── png/
│   │   └── provisioning/
│   ├── 📁 homeassistant/      # Home Assistant configurations
│   ├── 📁 pihole/             # Pi-hole configurations
│   ├── 📁 stremio/            # Stremio configurations
│   ├── 📁 portainer/          # Portainer configurations
│   ├── 📁 uptime-kuma/        # Uptime Kuma configurations
│   ├── 📁 whats-up-docker/    # What's Up Docker configurations
│   │   └── wud-config.json    # What's Up Docker configuration
│   └── cloudflared-config.yml   # Cloudflare tunnel configuration
├── 📁 scripts/                 # Scripts and utilities
│   ├── homelab                # Interactive CLI entry point
│   ├── homelab-tools          # CLI tools entry point
│   ├── requirements.txt       # Python dependencies
│   ├── requirements-dev.txt    # Development dependencies
│   ├── pyproject.toml         # Python project configuration
│   └── setup.py              # Package setup
├── 📁 tests/                  # Test suite
│   ├── unit/                  # Unit tests
│   │   ├── test_config.py
│   │   ├── test_health.py
│   │   └── test_updates.py
│   └── integration/           # Integration tests
├── 📁 docs/                   # Documentation
│   ├── README.md              # Documentation index
│   ├── interactive-cli.md     # Interactive CLI guide
│   ├── tailscale-setup.md     # Tailscale setup guide
│   ├── python-migration.md    # Python migration guide
│   └── project-structure.md   # This file
├── 📁 appdata/                # Application data
│   ├── homepage/
│   ├── homeassistant/
│   ├── pihole/
│   ├── stremio/
│   ├── portainer/
│   ├── uptime-kuma/
│   └── whats-up-docker/
├── 📁 backups/                # Backup storage
├── 📁 logs/                   # Log files
├── docker-compose.yml         # Main Docker Compose file
├── .env                       # Environment variables
├── .gitignore                 # Git ignore rules
├── Makefile                   # Build and test commands
├── README.md                  # Main project documentation
└── CHANGELOG.md              # Change log
```

## 🔄 **Key Changes Made**

### **1. Moved `homelab_manager` to Root**
- **Before**: `scripts/homelab_manager/`
- **After**: `homelab_manager/`
- **Benefit**: Cleaner imports, better package structure

### **2. Created Centralized `config/` Directory**
- **Before**: Scattered configuration files
- **After**: Organized by service in `config/`
- **Benefit**: Easy to find and manage configurations

### **3. Updated Import Paths**
- **Before**: `from scripts.homelab_manager.module import Class`
- **After**: `from homelab_manager.module import Class`
- **Benefit**: Cleaner, more standard Python imports

### **4. Updated Docker Compose Paths**
- **Before**: `./nginx.conf`, `./prometheus/prometheus.yml`
- **After**: `./config/nginx/nginx.conf`, `./config/prometheus/prometheus.yml`
- **Benefit**: Consistent configuration management

## 📋 **Service Configuration Structure**

### **Nginx Configuration**
```
config/nginx/
├── nginx.conf                 # Main Nginx configuration
├── homelab-proxy.conf        # Proxy configuration
└── nginx-config/
    └── conf.d/               # Additional configurations
```

### **Homepage Configuration**
```
config/homepage/
├── services.yaml             # Service definitions
├── widgets.yaml              # Widget configurations
├── bookmarks.yaml            # Bookmark definitions
├── settings.yaml             # General settings
├── docker.yaml               # Docker service config
├── kubernetes.yaml           # Kubernetes service config
└── proxmox.yaml              # Proxmox service config
```

### **Prometheus Configuration**
```
config/prometheus/
└── prometheus.yml            # Prometheus configuration
```

## 🚀 **Benefits of New Structure**

### **1. Better Organization**
- **Clear separation** between code, config, and data
- **Service-specific** configuration folders
- **Logical grouping** of related files

### **2. Easier Maintenance**
- **Centralized configuration** management
- **Standard Python package** structure
- **Consistent file locations**

### **3. Improved Development**
- **Cleaner imports** in Python code
- **Better IDE support** with standard structure
- **Easier testing** with proper package layout

### **4. Enhanced Security**
- **Configuration isolation** from application data
- **Clear separation** of concerns
- **Easier backup** of configurations

## 🔧 **Usage Examples**

### **Accessing Configurations**
```python
# In Python code
from homelab_manager.config import HomelabConfig

# Configuration files are now in config/
config_path = Path("config/nginx/nginx.conf")
```

### **Docker Compose Integration**
```yaml
# docker-compose.yml
services:
  nginx:
    volumes:
      - ./config/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./config/nginx/nginx-config/conf.d:/etc/nginx/conf.d:ro
```

### **Interactive CLI**
```bash
# Start the interactive CLI
./scripts/homelab

# All configurations are automatically found in config/
```

## 📚 **Migration Guide**

### **For Developers**
1. **Update imports**: Change `scripts.homelab_manager` to `homelab_manager`
2. **Update paths**: Use `config/` instead of scattered config files
3. **Update tests**: Fix import paths in test files

### **For Users**
1. **No changes needed**: All functionality remains the same
2. **Configurations**: Now organized in `config/` directory
3. **Interactive CLI**: Enhanced with better organization

## 🎯 **Next Steps**

1. **Test the new structure**: Run tests to ensure everything works
2. **Update documentation**: Keep docs in sync with new structure
3. **Add new services**: Use the new `config/` structure for new services
4. **Backup configurations**: Ensure all configs are properly backed up

## 🎉 **Summary**

The new project structure provides:
- **Better organization** with clear separation of concerns
- **Easier maintenance** with centralized configuration management
- **Improved development** experience with standard Python structure
- **Enhanced security** with proper configuration isolation

Your homelab is now **better organized, more maintainable, and easier to extend**! 🚀✨
