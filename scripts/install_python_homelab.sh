#!/bin/bash

# Luk's Homelab Manager - Python Installation Script
# Installs the Python-based homelab automation system

set -e

echo "🐍 Installing Luk's Homelab Manager - Python Edition"
echo "=================================================="

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.8+ required. Found: $python_version"
    exit 1
fi

echo "✅ Python version: $python_version"

# Install pip if not available
if ! command -v pip3 &> /dev/null; then
    echo "📦 Installing pip..."
    sudo apt update
    sudo apt install -y python3-pip
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
cd scripts
pip3 install -r requirements.txt

# Make CLI executable
echo "🔧 Setting up CLI..."
chmod +x homelab_manager/cli.py

# Create config directory
echo "📁 Creating configuration directory..."
mkdir -p ../config

# Initialize configuration
echo "⚙️  Initializing configuration..."
python3 -m homelab_manager init

echo ""
echo "🎉 Installation complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit config/homelab.yml with your settings"
echo "2. Set your Cloudflare token: export CF_API_TOKEN='your_token'"
echo "3. Run: python3 -m homelab_manager deploy"
echo ""
echo "📖 For more information, see README.md"
echo ""
echo "🚀 Happy homelabbing!"
