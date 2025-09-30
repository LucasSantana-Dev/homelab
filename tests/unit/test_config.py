"""
Unit tests for configuration management
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from homelab_manager.config import HomelabConfig


class TestHomelabConfig:
    """Test cases for HomelabConfig class"""

    def test_init(self, temp_homelab_dir):
        """Test HomelabConfig initialization"""
        config = HomelabConfig()

        assert config.homelab_dir == temp_homelab_dir
        assert config.env_file == temp_homelab_dir / ".env"
        assert config.env_example == temp_homelab_dir / ".env.example"

    def test_load_environment_success(self, temp_homelab_dir):
        """Test successful environment loading"""
        config = HomelabConfig()
        env_vars = config.load_environment()

        assert "DOMAIN" in env_vars
        assert env_vars["DOMAIN"] == "test.example.com"
        assert "TIMEZONE" in env_vars
        assert env_vars["TIMEZONE"] == "UTC"

    def test_load_environment_missing_file(self, temp_homelab_dir):
        """Test environment loading with missing .env file"""
        # Remove .env file
        (temp_homelab_dir / ".env").unlink()

        config = HomelabConfig()
        env_vars = config.load_environment()

        assert env_vars == {}

    def test_validate_environment_success(self, temp_homelab_dir):
        """Test successful environment validation"""
        config = HomelabConfig()
        is_valid, errors = config.validate_environment()

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_environment_missing_required(self, temp_homelab_dir):
        """Test environment validation with missing required variables"""
        # Create .env with missing required variables
        env_file = temp_homelab_dir / ".env"
        env_file.write_text(
            """
DOMAIN=test.example.com
# Missing other required variables
"""
        )

        config = HomelabConfig()
        is_valid, errors = config.validate_environment()

        assert is_valid is False
        assert len(errors) > 0
        assert any("is not set" in error for error in errors)

    def test_validate_environment_invalid_format(self, temp_homelab_dir):
        """Test environment validation with invalid format"""
        # Create .env with invalid format
        env_file = temp_homelab_dir / ".env"
        env_file.write_text(
            """
DOMAIN=invalid_domain
TIMEZONE=invalid/timezone
PUID=not_a_number
PGID=not_a_number
TAILSCALE_IP=invalid_ip
CF_API_TOKEN=test_token
CF_TUNNEL_ID=test-tunnel-id
PIHOLE_WEB_PASSWORD=test_password
PIHOLE_LOCAL_IPV4=invalid_ip
GRAFANA_PASSWORD=test_password
HOMEASSISTANT_KEY=test_key
LUKBOT_SENTRY_DSN=https://test@sentry.io/test
LUKBOT_SENTRY_ORG_SLUG=test-org
LUKBOT_SENTRY_PROJECT_SLUG=test-project
LUKBOT_SENTRY_AUTH_TOKEN=test_token
WUD_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/REDACTED/REDACTED
WUD_SMTP_PASS=test_password
"""
        )

        config = HomelabConfig()
        is_valid, errors = config.validate_environment()

        assert is_valid is False
        assert len(errors) > 0
        assert any("invalid format" in error for error in errors)

    def test_create_env_example(self, temp_homelab_dir):
        """Test creating .env.example file"""
        config = HomelabConfig()
        success = config.create_env_example()

        assert success is True
        assert config.env_example.exists()

        # Check that example file contains placeholders
        example_content = config.env_example.read_text()
        assert "your_domain_here" in example_content
        assert "your_timezone_here" in example_content

    def test_show_config_summary(self, temp_homelab_dir, capsys):
        """Test configuration summary display"""
        config = HomelabConfig()
        config.show_config_summary()

        captured = capsys.readouterr()
        assert "Configuration Summary" in captured.out
        assert "DOMAIN" in captured.out
