#!/usr/bin/env python3
"""
Tests for homelab_manager.config module
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from homelab_manager.config import HomelabConfig


class TestHomelabConfig:
    """Test cases for HomelabConfig class"""

    def test_init_with_default_path(self):
        """Test initialization with default path"""
        config = HomelabConfig()
        assert config.homelab_dir == Path(__file__).parent.parent.parent
        assert config.env_file == config.homelab_dir / ".env"
        assert config.env_example == config.homelab_dir / ".env.example"

    def test_init_with_custom_path(self):
        """Test initialization with custom path"""
        custom_path = "/custom/homelab"
        config = HomelabConfig(custom_path)
        assert config.homelab_dir == Path(custom_path)
        assert config.env_file == Path(custom_path) / ".env"
        assert config.env_example == Path(custom_path) / ".env.example"

    def test_required_vars_defined(self):
        """Test that required variables are properly defined"""
        config = HomelabConfig()

        expected_vars = [
            "DOMAIN",
            "TIMEZONE",
            "PUID",
            "PGID",
            "TAILSCALE_IP",
            "CF_API_TOKEN",
            "CF_TUNNEL_ID",
            "PIHOLE_WEB_PASSWORD",
            "PIHOLE_LOCAL_IPV4",
            "GRAFANA_PASSWORD",
            "HOMEASSISTANT_KEY",
            "LUKBOT_SENTRY_DSN",
            "LUKBOT_SENTRY_ORG_SLUG",
            "LUKBOT_SENTRY_PROJECT_SLUG",
            "LUKBOT_SENTRY_AUTH_TOKEN",
            "WUD_DISCORD_WEBHOOK_URL",
            "WUD_SMTP_PASS",
        ]

        for var in expected_vars:
            assert var in config.required_vars
            assert config.required_vars[var]  # Pattern should not be empty

    def test_optional_vars_defined(self):
        """Test that optional variables are properly defined"""
        config = HomelabConfig()

        expected_vars = [
            "WUD_SMTP_HOST",
            "WUD_SMTP_PORT",
            "WUD_SMTP_USER",
            "WUD_SMTP_FROM",
            "WUD_SMTP_TO",
            "MEDIA_PATH",
            "USER_HOME",
        ]

        for var in expected_vars:
            assert var in config.optional_vars
            assert config.optional_vars[var]  # Pattern should not be empty

    def test_load_environment_file_not_found(self):
        """Test loading environment when .env file doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)

            with patch("rich.console.Console.print") as mock_print:
                result = config.load_environment()

                assert result == {}
                mock_print.assert_called_with("❌ .env file not found", style="red")

    def test_load_environment_success(self):
        """Test successful environment loading"""
        env_content = """# Test environment file
DOMAIN=example.com
TIMEZONE=UTC
PUID=1000
PGID=1000
# Comment line
TAILSCALE_IP=192.168.1.100
CF_API_TOKEN=test_token_123
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            with open(env_file, "w") as f:
                f.write(env_content)

            with patch("rich.console.Console.print") as mock_print:
                result = config.load_environment()

                expected_vars = {
                    "DOMAIN": "example.com",
                    "TIMEZONE": "UTC",
                    "PUID": "1000",
                    "PGID": "1000",
                    "TAILSCALE_IP": "192.168.1.100",
                    "CF_API_TOKEN": "test_token_123",
                }

                assert result == expected_vars
                mock_print.assert_called_with(
                    "✅ Environment variables loaded successfully", style="green"
                )

    def test_load_environment_with_quotes(self):
        """Test loading environment with quoted values"""
        env_content = """# Test environment file
DOMAIN="example.com"
TIMEZONE='UTC'
PUID="1000"
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            with open(env_file, "w") as f:
                f.write(env_content)

            result = config.load_environment()

            expected_vars = {"DOMAIN": "example.com", "TIMEZONE": "UTC", "PUID": "1000"}

            assert result == expected_vars

    def test_load_environment_invalid_line(self):
        """Test loading environment with invalid lines"""
        env_content = """# Test environment file
DOMAIN=example.com
INVALID_LINE_NO_EQUALS
TIMEZONE=UTC
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            with open(env_file, "w") as f:
                f.write(env_content)

            with patch("rich.console.Console.print") as mock_print:
                result = config.load_environment()

                expected_vars = {"DOMAIN": "example.com", "TIMEZONE": "UTC"}

                assert result == expected_vars
                # Should print warning for invalid line
                mock_print.assert_any_call(
                    "⚠️ Invalid line 3: INVALID_LINE_NO_EQUALS", style="yellow"
                )

    def test_load_environment_file_error(self):
        """Test loading environment with file read error"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            # Create a file that will cause read error
            with open(env_file, "w") as f:
                f.write("test")

            with patch("builtins.open", side_effect=IOError("Read error")):
                with patch("rich.console.Console.print") as mock_print:
                    result = config.load_environment()

                    assert result == {}
                    mock_print.assert_called_with(
                        "❌ Error loading environment: Read error", style="red"
                    )

    def test_validate_environment_success(self):
        """Test successful environment validation"""
        env_content = """# Valid environment file
DOMAIN=example.com
TIMEZONE=UTC
PUID=1000
PGID=1000
TAILSCALE_IP=192.168.1.100
CF_API_TOKEN=test_token_123456789012345678901234567890
CF_TUNNEL_ID=12345678-1234-1234-1234-123456789012
PIHOLE_WEB_PASSWORD=strongpassword123
PIHOLE_LOCAL_IPV4=192.168.1.1
GRAFANA_PASSWORD=strongpassword123
HOMEASSISTANT_KEY=test.key.test
LUKBOT_SENTRY_DSN=https://test@sentry.io/123456
LUKBOT_SENTRY_ORG_SLUG=test-org
LUKBOT_SENTRY_PROJECT_SLUG=test-project
LUKBOT_SENTRY_AUTH_TOKEN=test_auth_token_123
WUD_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/REDACTED/REDACTED
WUD_SMTP_PASS=strongpassword123
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            with open(env_file, "w") as f:
                f.write(env_content)

            with patch("rich.console.Console.print") as mock_print:
                is_valid, errors = config.validate_environment()

                assert is_valid is True
                assert errors == []

    def test_validate_environment_missing_required(self):
        """Test validation with missing required variables"""
        env_content = """# Missing required variables
DOMAIN=example.com
TIMEZONE=UTC
# PUID missing
PGID=1000
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            with open(env_file, "w") as f:
                f.write(env_content)

            with patch("rich.console.Console.print") as mock_print:
                is_valid, errors = config.validate_environment()

                assert is_valid is False
                assert "PUID is not set" in errors

    def test_validate_environment_invalid_format(self):
        """Test validation with invalid format"""
        env_content = """# Invalid format
DOMAIN=invalid_domain_format
TIMEZONE=UTC
PUID=1000
PGID=1000
TAILSCALE_IP=invalid_ip
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            with open(env_file, "w") as f:
                f.write(env_content)

            with patch("rich.console.Console.print") as mock_print:
                is_valid, errors = config.validate_environment()

                assert is_valid is False
                assert any("has invalid format" in error for error in errors)

    def test_validate_environment_optional_vars(self):
        """Test validation with optional variables"""
        env_content = """# With optional variables
DOMAIN=example.com
TIMEZONE=UTC
PUID=1000
PGID=1000
TAILSCALE_IP=192.168.1.100
CF_API_TOKEN=test_token_123456789012345678901234567890
CF_TUNNEL_ID=12345678-1234-1234-1234-123456789012
PIHOLE_WEB_PASSWORD=strongpassword123
PIHOLE_LOCAL_IPV4=192.168.1.1
GRAFANA_PASSWORD=strongpassword123
HOMEASSISTANT_KEY=test.key.test
LUKBOT_SENTRY_DSN=https://test@sentry.io/123456
LUKBOT_SENTRY_ORG_SLUG=test-org
LUKBOT_SENTRY_PROJECT_SLUG=test-project
LUKBOT_SENTRY_AUTH_TOKEN=test_auth_token_123
WUD_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/REDACTED/REDACTED
WUD_SMTP_PASS=strongpassword123
WUD_SMTP_HOST=mail.example.com
WUD_SMTP_PORT=587
WUD_SMTP_USER=test@example.com
WUD_SMTP_FROM=test@example.com
WUD_SMTP_TO=admin@example.com
MEDIA_PATH=/media
USER_HOME=/home/user
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            with open(env_file, "w") as f:
                f.write(env_content)

            with patch("rich.console.Console.print") as mock_print:
                is_valid, errors = config.validate_environment()

                assert is_valid is True
                assert errors == []

    def test_security_checks_weak_password(self):
        """Test security checks with weak passwords"""
        env_content = """# Weak passwords
DOMAIN=example.com
TIMEZONE=UTC
PUID=1000
PGID=1000
TAILSCALE_IP=192.168.1.100
CF_API_TOKEN=test_token_123456789012345678901234567890
CF_TUNNEL_ID=12345678-1234-1234-1234-123456789012
PIHOLE_WEB_PASSWORD=password
PIHOLE_LOCAL_IPV4=192.168.1.1
GRAFANA_PASSWORD=123456
HOMEASSISTANT_KEY=test.key.test
LUKBOT_SENTRY_DSN=https://test@sentry.io/123456
LUKBOT_SENTRY_ORG_SLUG=test-org
LUKBOT_SENTRY_PROJECT_SLUG=test-project
LUKBOT_SENTRY_AUTH_TOKEN=test_auth_token_123
WUD_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/REDACTED/REDACTED
WUD_SMTP_PASS=admin
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            with open(env_file, "w") as f:
                f.write(env_content)

            with patch("rich.console.Console.print") as mock_print:
                is_valid, errors = config.validate_environment()

                assert is_valid is False
                assert any("is too weak" in error for error in errors)

    def test_security_checks_short_password(self):
        """Test security checks with short passwords"""
        env_content = """# Short passwords
DOMAIN=example.com
TIMEZONE=UTC
PUID=1000
PGID=1000
TAILSCALE_IP=192.168.1.100
CF_API_TOKEN=test_token_123456789012345678901234567890
CF_TUNNEL_ID=12345678-1234-1234-1234-123456789012
PIHOLE_WEB_PASSWORD=123
PIHOLE_LOCAL_IPV4=192.168.1.1
GRAFANA_PASSWORD=abc
HOMEASSISTANT_KEY=test.key.test
LUKBOT_SENTRY_DSN=https://test@sentry.io/123456
LUKBOT_SENTRY_ORG_SLUG=test-org
LUKBOT_SENTRY_PROJECT_SLUG=test-project
LUKBOT_SENTRY_AUTH_TOKEN=test_auth_token_123
WUD_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/REDACTED/REDACTED
WUD_SMTP_PASS=xyz
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            with open(env_file, "w") as f:
                f.write(env_content)

            with patch("rich.console.Console.print") as mock_print:
                is_valid, errors = config.validate_environment()

                assert is_valid is False
                assert any(
                    "should be at least 8 characters" in error for error in errors
                )

    def test_create_env_example_success(self):
        """Test successful creation of .env.example file"""
        env_content = """# Test environment file
DOMAIN=example.com
TIMEZONE=UTC
PUID=1000
PGID=1000
TAILSCALE_IP=192.168.1.100
CF_API_TOKEN=test_token_123456789012345678901234567890
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"
            example_file = Path(temp_dir) / ".env.example"

            with open(env_file, "w") as f:
                f.write(env_content)

            with patch("rich.console.Console.print") as mock_print:
                result = config.create_env_example()

                assert result is True
                assert example_file.exists()

                # Check that values were replaced with placeholders
                with open(example_file, "r") as f:
                    example_content = f.read()

                assert "your_domain_here" in example_content
                assert "your_timezone_here" in example_content
                assert "your_puid_here" in example_content
                mock_print.assert_called_with(
                    f"✅ Created {example_file}", style="green"
                )

    def test_create_env_example_file_not_found(self):
        """Test creating .env.example when .env file doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)

            with patch("rich.console.Console.print") as mock_print:
                result = config.create_env_example()

                assert result is False
                mock_print.assert_called_with("❌ .env file not found", style="red")

    def test_create_env_example_error(self):
        """Test creating .env.example with file error"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            with open(env_file, "w") as f:
                f.write("test")

            with patch("builtins.open", side_effect=IOError("Write error")):
                with patch("rich.console.Console.print") as mock_print:
                    result = config.create_env_example()

                    assert result is False
                    mock_print.assert_called_with(
                        "❌ Error creating example file: Write error", style="red"
                    )

    def test_show_config_summary(self):
        """Test showing configuration summary"""
        env_content = """# Test environment file
DOMAIN=example.com
TIMEZONE=UTC
PUID=1000
PGID=1000
TAILSCALE_IP=192.168.1.100
CF_API_TOKEN=test_token_123456789012345678901234567890
CF_TUNNEL_ID=12345678-1234-1234-1234-123456789012
PIHOLE_WEB_PASSWORD=strongpassword123
PIHOLE_LOCAL_IPV4=192.168.1.1
GRAFANA_PASSWORD=strongpassword123
HOMEASSISTANT_KEY=test.key.test
LUKBOT_SENTRY_DSN=https://test@sentry.io/123456
LUKBOT_SENTRY_ORG_SLUG=test-org
LUKBOT_SENTRY_PROJECT_SLUG=test-project
LUKBOT_SENTRY_AUTH_TOKEN=test_auth_token_123
WUD_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/REDACTED/REDACTED
WUD_SMTP_PASS=strongpassword123
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            config = HomelabConfig(temp_dir)
            env_file = Path(temp_dir) / ".env"

            with open(env_file, "w") as f:
                f.write(env_content)

            with patch("rich.console.Console.print") as mock_print:
                config.show_config_summary()

                # Should print panel and table
                assert mock_print.call_count >= 1

    def test_main_function_load(self):
        """Test main function with load action"""
        with patch("homelab_manager.config.HomelabConfig") as mock_config_class:
            mock_config = Mock()
            mock_config_class.return_value = mock_config

            with patch("argparse.ArgumentParser") as mock_parser:
                mock_args = Mock()
                mock_args.action = "load"
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.config import main

                main()

                mock_config.load_environment.assert_called_once()

    def test_main_function_validate(self):
        """Test main function with validate action"""
        with patch("homelab_manager.config.HomelabConfig") as mock_config_class:
            mock_config = Mock()
            mock_config_class.return_value = mock_config

            with patch("argparse.ArgumentParser") as mock_parser:
                mock_args = Mock()
                mock_args.action = "validate"
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.config import main

                main()

                mock_config.validate_environment.assert_called_once()

    def test_main_function_summary(self):
        """Test main function with summary action"""
        with patch("homelab_manager.config.HomelabConfig") as mock_config_class:
            mock_config = Mock()
            mock_config_class.return_value = mock_config

            with patch("argparse.ArgumentParser") as mock_parser:
                mock_args = Mock()
                mock_args.action = "summary"
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.config import main

                main()

                mock_config.show_config_summary.assert_called_once()

    def test_main_function_create_example(self):
        """Test main function with create-example action"""
        with patch("homelab_manager.config.HomelabConfig") as mock_config_class:
            mock_config = Mock()
            mock_config_class.return_value = mock_config

            with patch("argparse.ArgumentParser") as mock_parser:
                mock_args = Mock()
                mock_args.action = "create-example"
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.config import main

                main()

                mock_config.create_env_example.assert_called_once()
