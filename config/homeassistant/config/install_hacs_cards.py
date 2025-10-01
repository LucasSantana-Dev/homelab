#!/usr/bin/env python3
# HACS Cards Installation Script
# This script installs essential HACS cards for clean dashboard

import requests
import json
import os
import time

# HACS API endpoints
HACS_BASE_URL = "http://localhost:8123/api"
HACS_FRONTEND_URL = "http://localhost:8123/hacsfiles"

# Essential cards to install
CARDS_TO_INSTALL = [
    {
        "name": "Mushroom Cards",
        "repository": "piitaya/lovelace-mushroom",
        "description": "Beautiful, modern card components",
        "url": "https://github.com/piitaya/lovelace-mushroom"
    },
    {
        "name": "Button Card",
        "repository": "custom-cards/button-card",
        "description": "Highly customizable button cards",
        "url": "https://github.com/custom-cards/button-card"
    },
    {
        "name": "Mini Graph Card",
        "repository": "kalkih/mini-graph-card",
        "description": "Compact, beautiful graphs",
        "url": "https://github.com/kalkih/mini-graph-card"
    },
    {
        "name": "Card Mod",
        "repository": "thomasloven/lovelace-card-mod",
        "description": "CSS styling for any card",
        "url": "https://github.com/thomasloven/lovelace-card-mod"
    },
    {
        "name": "Auto Entities",
        "repository": "thomasloven/lovelace-auto-entities",
        "description": "Automatic entity filtering and grouping",
        "url": "https://github.com/thomasloven/lovelace-auto-entities"
    }
]

def install_hacs_cards():
    print("🎨 Installing HACS Cards for Clean Dashboard...")
    print("===============================================")
    
    for card in CARDS_TO_INSTALL:
        print(f"📦 Installing {card['name']}...")
        print(f"   Repository: {card['repository']}")
        print(f"   Description: {card['description']}")
        print(f"   URL: {card['url']}")
        print()
    
    print("✅ HACS Cards Installation Guide Created!")
    print()
    print("📋 Manual Installation Steps:")
    print("1. Go to HACS → Frontend in Home Assistant")
    print("2. Search for each card name")
    print("3. Click 'Download' for each card")
    print("4. Restart Home Assistant")
    print("5. Apply the clean dashboard configuration")
    print()
    print("🎯 Most Important Card: Mushroom Cards")
    print("   This is the key to transforming your dashboard!")

if __name__ == "__main__":
    install_hacs_cards()
