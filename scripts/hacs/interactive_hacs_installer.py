#!/usr/bin/env python3
"""
Interactive HACS Add-on Installer using Selenium
This script will guide you through installing HACS add-ons with browser automation
"""

import getpass
import os
import time

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

HA_URL = os.environ.get(
    "HA_URL", f"http://{os.environ.get('TAILSCALE_IP', 'localhost')}:8123"
)

# HACS Add-ons to install
ADDONS = {
    "integrations": [
        {"name": "Adaptive Lighting", "repo": "basnijholt/adaptive-lighting"},
        {"name": "Auto-entities", "repo": "thomasloven/lovelace-auto-entities"},
    ],
    "plugins": [
        {"name": "Card Mod", "repo": "thomasloven/lovelace-card-mod"},
        {"name": "Mini Graph Card", "repo": "kalkih/mini-graph-card"},
        {"name": "Mushroom Cards", "repo": "piitaya/lovelace-mushroom"},
        {"name": "Layout Card", "repo": "thomasloven/lovelace-layout-card"},
        {"name": "State Switch", "repo": "thomasloven/lovelace-state-switch"},
        {"name": "Button Card", "repo": "custom-cards/button-card"},
    ],
}


def setup_browser(headless=False):
    """Setup Chrome browser"""
    options = Options()
    if not headless:
        options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)
        return driver
    except Exception as e:
        print(f"Error setting up browser: {e}")
        print("\nPlease install Chrome and ChromeDriver:")
        print("  sudo apt-get install chromium-browser chromium-chromedriver")
        return None


def login_to_ha(driver, username, password):
    """Login to Home Assistant"""
    print(f"\nNavigating to {HA_URL}...")
    driver.get(HA_URL)
    time.sleep(2)

    # Check if already logged in
    if "lovelace" in driver.current_url or "dashboard" in driver.current_url:
        print("✓ Already logged in!")
        return True

    try:
        print("Logging in...")
        # Find username field
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='text'], input[name='username']")
            )
        )
        username_field.clear()
        username_field.send_keys(username)

        # Find password field
        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        password_field.clear()
        password_field.send_keys(password)

        # Click login
        login_btn = driver.find_element(
            By.CSS_SELECTOR, "button[type='submit'], button:contains('Log in')"
        )
        login_btn.click()

        time.sleep(5)

        if "lovelace" in driver.current_url or "dashboard" in driver.current_url:
            print("✓ Login successful!")
            return True
        else:
            print("✗ Login failed")
            return False
    except Exception as e:
        print(f"✗ Login error: {e}")
        return False


def navigate_to_hacs(driver):
    """Navigate to HACS"""
    print("\nNavigating to HACS...")
    hacs_url = f"{HA_URL}/hacs"
    driver.get(hacs_url)
    time.sleep(3)

    if "hacs" in driver.current_url.lower():
        print("✓ HACS page loaded")
        return True

    # Try via sidebar
    try:
        driver.get(HA_URL)
        time.sleep(2)
        sidebar = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "ha-menu-button, button[aria-label*='menu']")
            )
        )
        sidebar.click()
        time.sleep(1)

        hacs_link = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    (
                        "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                        "'abcdefghijklmnopqrstuvwxyz'), 'hacs')]"
                    ),
                )
            )
        )
        hacs_link.click()
        time.sleep(3)
        print("✓ Navigated to HACS")
        return True
    except Exception:
        print("✗ Could not navigate to HACS")
        return False


def install_addon_via_repo(driver, addon_name, repo):
    """Install addon by adding repository"""
    print(f"\n  Installing {addon_name}...")

    try:
        # Go to HACS
        driver.get(f"{HA_URL}/hacs")
        time.sleep(2)

        # Click on "Custom Repositories" or "Add Repository"
        try:
            add_repo_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//*[contains(text(), 'Custom') or contains(text(), 'Repository') or contains(text(), 'Add')]",
                    )
                )
            )
            add_repo_btn.click()
            time.sleep(2)
        except Exception:
            # Try three dots menu
            try:
                menu_btn = driver.find_element(
                    By.CSS_SELECTOR, "ha-icon-button, button[aria-label*='menu']"
                )
                menu_btn.click()
                time.sleep(1)
                add_repo = driver.find_element(
                    By.XPATH, "//*[contains(text(), 'Repository')]"
                )
                add_repo.click()
                time.sleep(2)
            except Exception:
                print(f"    ⚠ Could not find 'Add Repository' button")
                return False

        # Enter repository URL
        repo_url = f"https://github.com/{repo}"
        try:
            repo_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "input[type='url'], input[placeholder*='repository'], input[placeholder*='URL'], ha-textfield",
                    )
                )
            )
            repo_input.clear()
            repo_input.send_keys(repo_url)
            time.sleep(1)

            # Select category (Integration or Plugin)
            category = (
                "Integration"
                if "adaptive" in repo.lower() or "auto" in repo.lower()
                else "Plugin"
            )
            try:
                category_dropdown = driver.find_element(
                    By.CSS_SELECTOR, "ha-select, select"
                )
                category_dropdown.click()
                time.sleep(1)
                category_option = driver.find_element(
                    By.XPATH, f"//*[contains(text(), '{category}')]"
                )
                category_option.click()
                time.sleep(1)
            except Exception as e:
                print(f"    ⚠ Could not select category automatically: {e}")

            # Submit
            submit_btn = driver.find_element(
                By.XPATH,
                "//button[contains(text(), 'Add') or contains(text(), 'Install') or contains(text(), 'Save')]",
            )
            submit_btn.click()
            time.sleep(3)

            print(f"    ✓ Repository added: {repo_url}")

            # Now install the addon
            driver.get(f"{HA_URL}/hacs")
            time.sleep(2)

            # Search for the addon
            try:
                search_box = driver.find_element(
                    By.CSS_SELECTOR,
                    "input[type='search'], input[placeholder*='search']",
                )
                search_box.clear()
                search_box.send_keys(addon_name)
                time.sleep(2)
            except Exception as e:
                print(f"    ⚠ Search box unavailable, continuing without search: {e}")

            # Find and click the addon
            try:
                addon_card = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, f"//*[contains(text(), '{addon_name}')]")
                    )
                )
                addon_card.click()
                time.sleep(2)

                # Click Download/Install
                install_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//button[contains(text(), 'Download') or contains(text(), 'Install')]",
                        )
                    )
                )
                install_btn.click()
                time.sleep(5)

                print(f"    ✓ {addon_name} installed successfully!")
                return True
            except Exception:
                print(
                    f"    ⚠ {addon_name} may already be installed or installation button not found"
                )
                return True

        except Exception as e:
            print(f"    ✗ Error: {e}")
            return False

    except Exception as e:
        print(f"    ✗ Failed to install {addon_name}: {e}")
        return False


def main():
    print("=" * 60)
    print("Home Assistant HACS Add-on Installer")
    print("=" * 60)

    # Get credentials
    username = input("\nHome Assistant Username: ")
    password = getpass.getpass("Home Assistant Password: ")
    headless = input("Run in headless mode? (y/N): ").lower() == "y"

    # Setup browser
    driver = setup_browser(headless)
    if not driver:
        return

    try:
        # Login
        if not login_to_ha(driver, username, password):
            print("\n✗ Could not login. Please check your credentials.")
            return

        # Navigate to HACS
        if not navigate_to_hacs(driver):
            print(
                "\n✗ Could not access HACS. Make sure HACS is installed in Home Assistant."
            )
            print("  Install HACS first: https://hacs.xyz/docs/setup/download")
            return

        # Install addons
        print("\n" + "=" * 60)
        print("Installing HACS Add-ons")
        print("=" * 60)

        total = sum(len(addons) for addons in ADDONS.values())
        installed = 0

        # Install integrations
        print("\n📦 Installing Integrations...")
        for addon in ADDONS["integrations"]:
            if install_addon_via_repo(driver, addon["name"], addon["repo"]):
                installed += 1
            time.sleep(2)

        # Install plugins
        print("\n🎨 Installing Frontend Plugins...")
        for addon in ADDONS["plugins"]:
            if install_addon_via_repo(driver, addon["name"], addon["repo"]):
                installed += 1
            time.sleep(2)

        print("\n" + "=" * 60)
        print(f"Installation Complete: {installed}/{total} add-ons installed")
        print("=" * 60)
        print("\n⚠ Remember to:")
        print("  1. Restart Home Assistant after installing integrations")
        print("  2. Refresh browser (Ctrl+F5) after installing plugins")
        print("  3. Configure the add-ons in Home Assistant settings")

    finally:
        if not headless:
            input("\nPress Enter to close the browser...")
        driver.quit()


if __name__ == "__main__":
    main()
