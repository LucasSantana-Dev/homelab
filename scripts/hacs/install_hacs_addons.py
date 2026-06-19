#!/usr/bin/env python3
"""
Home Assistant HACS Add-on Installer
Uses Selenium to navigate HACS and install add-ons automatically
"""

import os
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# HACS Add-ons to install
HACS_ADDONS = [
    # Integrations
    {
        "type": "integration",
        "name": "Adaptive Lighting",
        "repository": "https://github.com/basnijholt/adaptive-lighting",
    },
    {
        "type": "integration",
        "name": "Auto-entities",
        "repository": "https://github.com/thomasloven/lovelace-auto-entities",
    },
    {
        "type": "plugin",
        "name": "Card Mod",
        "repository": "https://github.com/thomasloven/lovelace-card-mod",
    },
    {
        "type": "plugin",
        "name": "Mini Graph Card",
        "repository": "https://github.com/kalkih/mini-graph-card",
    },
    {
        "type": "plugin",
        "name": "Mushroom Cards",
        "repository": "https://github.com/piitaya/lovelace-mushroom",
    },
    {
        "type": "plugin",
        "name": "Layout Card",
        "repository": "https://github.com/thomasloven/lovelace-layout-card",
    },
    {
        "type": "plugin",
        "name": "State Switch",
        "repository": "https://github.com/thomasloven/lovelace-state-switch",
    },
    {
        "type": "plugin",
        "name": "Button Card",
        "repository": "https://github.com/custom-cards/button-card",
    },
]

# Home Assistant URL - loaded from environment variable
HA_URL = os.environ.get(
    "HA_URL", f"http://{os.environ.get('TAILSCALE_IP', 'localhost')}:8123"
)


class HACSInstaller:
    def __init__(self, username, password, headless=False):
        self.username = username
        self.password = password
        self.headless = headless
        self.driver = None
        self.wait = None

    def setup_driver(self):
        """Setup Chrome WebDriver"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        )

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 20)
            print("✓ Chrome WebDriver initialized")
            return True
        except Exception as e:
            print(f"✗ Failed to initialize WebDriver: {e}")
            print("Make sure Chrome and ChromeDriver are installed:")
            print("  sudo apt-get install chromium-browser chromium-chromedriver")
            return False

    def login(self):
        """Login to Home Assistant"""
        try:
            print(f"Navigating to {HA_URL}...")
            self.driver.get(HA_URL)
            time.sleep(2)

            # Check if already logged in
            if (
                "lovelace" in self.driver.current_url
                or "dashboard" in self.driver.current_url
            ):
                print("✓ Already logged in")
                return True

            # Find and fill username
            print("Entering credentials...")
            username_field = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[type='text'], input[name='username']")
                )
            )
            username_field.clear()
            username_field.send_keys(self.username)

            # Find and fill password
            password_field = self.driver.find_element(
                By.CSS_SELECTOR, "input[type='password']"
            )
            password_field.clear()
            password_field.send_keys(self.password)

            # Click login button
            login_button = self.driver.find_element(
                By.CSS_SELECTOR, "button[type='submit'], button:contains('Log in')"
            )
            login_button.click()

            # Wait for login to complete
            print("Waiting for login...")
            time.sleep(5)

            # Check if login was successful
            if (
                "lovelace" in self.driver.current_url
                or "dashboard" in self.driver.current_url
            ):
                print("✓ Login successful")
                return True
            else:
                print("✗ Login failed - check credentials")
                return False

        except TimeoutException:
            print("✗ Timeout waiting for login page")
            return False
        except Exception as e:
            print(f"✗ Login error: {e}")
            return False

    def navigate_to_hacs(self):
        """Navigate to HACS"""
        try:
            print("Navigating to HACS...")
            # Try direct URL first
            hacs_url = f"{HA_URL}/hacs"
            self.driver.get(hacs_url)
            time.sleep(3)

            # Check if HACS is accessible
            if "hacs" in self.driver.current_url.lower():
                print("✓ HACS page loaded")
                return True

            # Try via sidebar menu
            print("Trying to access HACS via sidebar...")
            self.driver.get(HA_URL)
            time.sleep(2)

            # Look for HACS in sidebar or menu
            try:
                # Try clicking on sidebar
                sidebar_button = self.wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.CSS_SELECTOR,
                            "ha-menu-button, button[aria-label*='menu'], .menu",
                        )
                    )
                )
                sidebar_button.click()
                time.sleep(1)

                # Look for HACS link
                hacs_link = self.wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//a[contains(text(), 'HACS') or contains(text(), 'hacs')]",
                        )
                    )
                )
                hacs_link.click()
                time.sleep(3)
                print("✓ Navigated to HACS via sidebar")
                return True
            except Exception as e:
                print(f"  ⚠ Sidebar navigation path failed, retrying direct URL: {e}")

            # Try direct navigation again
            self.driver.get(hacs_url)
            time.sleep(3)
            return "hacs" in self.driver.current_url.lower()

        except Exception as e:
            print(f"✗ Error navigating to HACS: {e}")
            return False

    def install_addon(self, addon):
        """Install a single HACS add-on"""
        try:
            print(f"\nInstalling {addon['name']} ({addon['type']})...")

            # Navigate to HACS store/frontend
            self.driver.get(f"{HA_URL}/hacs")
            time.sleep(2)

            # Click on the appropriate tab (Integrations, Frontend, etc.)
            tab_name = "Integrations" if addon["type"] == "integration" else "Frontend"
            try:
                tab = self.wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, f"//button[contains(text(), '{tab_name}')]")
                    )
                )
                tab.click()
                time.sleep(2)
            except Exception:
                print(f"  ⚠ Could not find {tab_name} tab, trying search...")

            # Search for the addon
            try:
                search_box = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "input[type='search'], input[placeholder*='search'], ha-textfield",
                )
                search_box.clear()
                search_box.send_keys(addon["name"])
                time.sleep(2)
            except Exception:
                print(f"  ⚠ Could not find search box")

            # Look for the addon card/button
            try:
                addon_element = self.wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, f"//*[contains(text(), '{addon['name']}')]")
                    )
                )
                addon_element.click()
                time.sleep(2)
            except Exception:
                # Try using repository URL
                print(f"  Trying to add via repository URL...")
                try:
                    # Look for "Add Repository" or "Custom Repository" button
                    add_repo_button = self.wait.until(
                        EC.element_to_be_clickable(
                            (
                                By.XPATH,
                                "//*[contains(text(), 'Add') or contains(text(), 'Repository')]",
                            )
                        )
                    )
                    add_repo_button.click()
                    time.sleep(1)

                    # Enter repository URL
                    repo_input = self.wait.until(
                        EC.presence_of_element_located(
                            (
                                By.CSS_SELECTOR,
                                "input[type='url'], input[placeholder*='repository'], input[placeholder*='URL']",
                            )
                        )
                    )
                    repo_input.clear()
                    repo_input.send_keys(addon["repository"])
                    time.sleep(1)

                    # Submit
                    submit_button = self.driver.find_element(
                        By.XPATH,
                        (
                            "//button[contains(text(), 'Add') or contains(text(), 'Install') "
                            "or contains(text(), 'Submit')]"
                        ),
                    )
                    submit_button.click()
                    time.sleep(3)
                except Exception as e:
                    print(f"  ✗ Could not add repository: {e}")
                    return False

            # Look for Install/Download button
            try:
                install_button = self.wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//button[contains(text(), 'Install') or contains(text(), 'Download')]",
                        )
                    )
                )
                install_button.click()
                time.sleep(2)

                # Confirm installation if needed
                try:
                    confirm_button = self.driver.find_element(
                        By.XPATH,
                        "//button[contains(text(), 'Install') or contains(text(), 'Confirm')]",
                    )
                    confirm_button.click()
                    time.sleep(3)
                except Exception as e:
                    print(f"  ⚠ Install confirmation prompt not shown: {e}")

                print(f"  ✓ {addon['name']} installation initiated")

                # Wait for installation to complete
                print(f"  Waiting for installation to complete...")
                time.sleep(10)

                return True
            except TimeoutException:
                print(f"  ⚠ Install button not found - addon may already be installed")
                return True
            except Exception as e:
                print(f"  ✗ Installation error: {e}")
                return False

        except Exception as e:
            print(f"  ✗ Error installing {addon['name']}: {e}")
            return False

    def install_all_addons(self):
        """Install all configured HACS add-ons"""
        if not self.setup_driver():
            return False

        try:
            if not self.login():
                return False

            if not self.navigate_to_hacs():
                print("✗ Could not access HACS. Make sure HACS is installed.")
                return False

            print(f"\nInstalling {len(HACS_ADDONS)} HACS add-ons...")
            success_count = 0

            for addon in HACS_ADDONS:
                if self.install_addon(addon):
                    success_count += 1
                time.sleep(2)  # Brief pause between installations

            print(
                f"\n✓ Installation complete: {success_count}/{len(HACS_ADDONS)} add-ons installed"
            )
            return success_count == len(HACS_ADDONS)

        finally:
            if self.driver:
                self.driver.quit()


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Install HACS add-ons via browser automation"
    )
    parser.add_argument("--username", required=True, help="Home Assistant username")
    parser.add_argument("--password", required=True, help="Home Assistant password")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")

    args = parser.parse_args()

    installer = HACSInstaller(args.username, args.password, args.headless)
    installer.install_all_addons()


if __name__ == "__main__":
    main()
