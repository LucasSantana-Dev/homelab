#!/usr/bin/env python3
# Apply Clean Dashboard Configuration

import os
import shutil
import time

def apply_clean_dashboard():
    print("🧹 Applying Clean Dashboard Configuration...")
    print("============================================")
    
    # Check if clean dashboard config exists
    if os.path.exists("/config/clean_dashboard.yaml"):
        print("✅ Clean dashboard configuration found")
        
        # Create backup of current dashboard
        if os.path.exists("/config/ui-lovelace.yaml"):
            shutil.copy("/config/ui-lovelace.yaml", "/config/ui-lovelace.yaml.backup")
            print("📁 Backup of current dashboard created")
        
        # Apply clean dashboard
        shutil.copy("/config/clean_dashboard.yaml", "/config/ui-lovelace.yaml")
        print("🎨 Clean dashboard configuration applied")
        
        print()
        print("✅ Dashboard Configuration Applied!")
        print("📋 Next Steps:")
        print("1. Install HACS cards (especially Mushroom Cards)")
        print("2. Restart Home Assistant")
        print("3. Check your dashboard - it should be clean and organized!")
        print()
        print("🔄 If you need to restore the old dashboard:")
        print("   Copy ui-lovelace.yaml.backup to ui-lovelace.yaml")
        
    else:
        print("❌ Clean dashboard configuration not found")
        print("   Please run the clean dashboard setup script first")

if __name__ == "__main__":
    apply_clean_dashboard()
