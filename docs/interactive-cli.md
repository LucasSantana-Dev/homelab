# Interactive Homelab CLI

A comprehensive interactive console application for managing your homelab with a beautiful, navigable interface.

## 🚀 **Quick Start**

```bash
# Start the interactive CLI
./scripts/homelab

# Or with custom homelab directory
./scripts/homelab --homelab-dir /path/to/your/homelab
```

## 🎯 **Features**

### 🏠 **Dashboard**
- **System Overview**: Quick status of all services
- **Mode Status**: Current access mode (public/tailscale)
- **Service Health**: Running services and their status
- **Resource Usage**: System resources at a glance

### 🔄 **Mode Management**
- **Switch Modes**: Toggle between public and Tailscale-only access
- **Current Mode**: View current access configuration
- **Security Status**: Verify mode-specific security settings

### 🔒 **Security**
- **Security Testing**: Comprehensive security verification
- **Port Binding**: Check which ports are bound to public vs Tailscale
- **Access Verification**: Test service accessibility
- **Auto-Fix**: Automatically resolve common security issues

### 📊 **Health Monitoring**
- **Quick Health Check**: Fast status check of all services
- **Full Health Check**: Comprehensive health analysis
- **System Resources**: CPU, memory, and disk usage
- **Container Status**: Docker container health and status

### 🔄 **Updates**
- **Check Updates**: Scan for available service updates
- **Update Services**: Update all services to latest versions
- **Version Management**: View current service versions
- **Auto-Update**: Configure automatic update settings

### ⚙️ **Configuration**
- **View Config**: Display current configuration
- **Edit Environment**: Modify environment variables
- **Secure Setup**: Setup secure environment variables
- **Validation**: Validate configuration integrity

### 🐳 **Container Management**
- **Container Status**: View all container statuses
- **Service Control**: Start, stop, restart services
- **Cleanup**: Remove unused containers and images
- **Logs**: View container logs and output

### 📋 **Logs & Monitoring**
- **Service Logs**: View logs for specific services
- **System Logs**: Access system-level logs
- **Log Search**: Search through log files
- **Performance**: View performance metrics and statistics

## 🎮 **Navigation**

### **Menu Navigation**
- **Arrow Keys**: Navigate through menu options
- **Enter**: Select an option
- **Ctrl+C**: Exit the application
- **Back**: Return to previous menu

### **Interactive Prompts**
- **Text Input**: Type responses to prompts
- **Confirmation**: Yes/No questions for important actions
- **Selection**: Choose from available options
- **Number Input**: Enter numeric values when needed

## 📋 **Menu Structure**

```
🏠 Homelab Manager
├── 🏠 Dashboard
├── 🔄 Mode Management
│   ├── 🌐 Switch to Public Mode
│   ├── 🔒 Switch to Tailscale Mode
│   └── 📊 Show Current Mode
├── 🔒 Security
│   ├── 🔍 Run Security Test
│   ├── 📊 Show Security Status
│   └── 🔧 Fix Security Issues
├── 📊 Health Monitoring
│   ├── 🏥 Quick Health Check
│   ├── 🔍 Full Health Check
│   ├── 📊 System Resources
│   └── 🐳 Container Status
├── 🔄 Updates
│   ├── 🔍 Check for Updates
│   ├── 🔄 Update All Services
│   ├── 📋 Show Current Versions
│   └── ⚙️ Auto-Update Settings
├── ⚙️ Configuration
│   ├── 📋 Show Configuration
│   ├── 🔧 Edit Environment Variables
│   ├── 🔒 Setup Secure Environment
│   └── ✅ Validate Configuration
├── 🐳 Container Management
│   ├── 📊 Container Status
│   ├── 🔄 Restart Services
│   ├── 🛑 Stop Services
│   ├── ▶️ Start Services
│   └── 🧹 Cleanup Containers
├── 📋 Logs & Monitoring
│   ├── 📋 View Service Logs
│   ├── 📊 System Logs
│   ├── 🔍 Search Logs
│   └── 📈 Performance Metrics
├── ❓ Help
└── 🚪 Exit
```

## 🎨 **Visual Features**

### **Rich Output**
- **Colored Text**: Different colors for status, errors, and information
- **Progress Bars**: Visual progress indicators for long operations
- **Tables**: Structured data display
- **Panels**: Organized information sections
- **Icons**: Visual indicators for different types of information

### **Status Indicators**
- **✅ Green**: Success, healthy, working
- **❌ Red**: Error, failed, unhealthy
- **⚠️ Yellow**: Warning, partial, attention needed
- **🔵 Blue**: Information, neutral status
- **🟡 Yellow**: In progress, loading

## 🔧 **Technical Details**

### **Dependencies**
- `rich` - Beautiful terminal output and formatting
- `psutil` - System resource monitoring
- `docker` - Docker container management
- `subprocess` - System command execution

### **Architecture**
```
scripts/homelab_manager/
├── interactive_cli.py    # Main interactive CLI
├── mode_manager.py       # Mode switching logic
├── security_tester.py   # Security testing
├── automation.py        # Automation tasks
├── health.py           # Health monitoring
├── updates.py          # Update management
├── config.py           # Configuration management
└── container_manager.py # Container management
```

### **Error Handling**
- **Graceful Failures**: Operations fail gracefully with helpful messages
- **Retry Logic**: Automatic retry for transient failures
- **User Feedback**: Clear error messages and suggestions
- **Logging**: Detailed logging for debugging

## 🚀 **Usage Examples**

### **Basic Usage**
```bash
# Start the interactive CLI
./scripts/homelab

# Navigate to Dashboard to see overview
# Navigate to Mode Management to switch modes
# Navigate to Security to run tests
```

### **Advanced Usage**
```bash
# Start with custom directory
./scripts/homelab --homelab-dir /custom/path

# The CLI will automatically detect your homelab setup
```

## 🔍 **Troubleshooting**

### **Common Issues**

**1. Permission Errors:**
```bash
# Make sure the script is executable
chmod +x scripts/homelab
```

**2. Missing Dependencies:**
```bash
# Install required packages
pip install rich psutil
```

**3. Docker Not Running:**
```bash
# Start Docker service
sudo systemctl start docker
```

**4. Tailscale Not Connected:**
```bash
# Connect to Tailscale
tailscale up
```

### **Getting Help**
- **Help Menu**: Use the ❓ Help option in the main menu
- **Error Messages**: Read error messages carefully for solutions
- **Logs**: Check logs for detailed error information

## 🎯 **Benefits**

### **User Experience**
- **Intuitive Navigation**: Easy-to-use menu system
- **Visual Feedback**: Clear status indicators and progress
- **Error Recovery**: Helpful error messages and suggestions
- **Comprehensive**: All homelab functions in one place

### **Developer Experience**
- **Modular Design**: Easy to extend with new features
- **Rich Integration**: Beautiful output with minimal code
- **Error Handling**: Robust error handling and recovery
- **Testing**: Easy to test individual components

## 📚 **Next Steps**

1. **Start the CLI**: `./scripts/homelab`
2. **Explore Features**: Navigate through different menus
3. **Test Functions**: Try different operations
4. **Customize**: Modify configuration as needed
5. **Automate**: Set up automated tasks

## 🎉 **Enjoy Your Interactive Homelab Management!**

Your homelab management is now **interactive, beautiful, and comprehensive**! 🚀✨
