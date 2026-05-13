#!/usr/bin/env python3
"""Tests for homelab_manager.core.config module"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from homelab_manager.core.config import HomelabConfig


def make_config(tmp_dir=None):
    """Create a HomelabConfig with mocked ServiceRegistry"""
    with patch("homelab_manager.core.config.ServiceRegistry"):
        return HomelabConfig(tmp_dir)


class TestHomelabConfigInit:
    """Tests for HomelabConfig initialization"""

    def test_init_with_default_path(self):
        """Test initialization with default path"""
        with patch("homelab_manager.core.config.ServiceRegistry"):
            config = HomelabConfig()
            assert config.homelab_dir == Path(__file__).parent.parent.parent
            assert config.env_file == config.homelab_dir / ".env"
            assert config.env_example == config.homelab_dir / ".env.example"

    def test_init_with_custom_path(self):
        """Test initialization with custom path"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("homelab_manager.core.config.ServiceRegistry"):
                config = HomelabConfig(tmp_dir)
                assert config.homelab_dir == Path(tmp_dir)
                assert config.env_file == Path(tmp_dir) / ".env"
                assert config.env_example == Path(tmp_dir) / ".env.example"

    def test_required_vars_defined(self):
        """Test that all expected required variables are defined"""
        with patch("homelab_manager.core.config.ServiceRegistry"):
            config = HomelabConfig()
            for var in ["DOMAIN", "TIMEZONE", "PUID", "PGID", "TAILSCALE_IP"]:
                assert var in config.required_vars
                assert config.required_vars[var]  # Pattern must not be empty

    def test_optional_vars_defined(self):
        """Test that all expected optional variables are defined"""
        with patch("homelab_manager.core.config.ServiceRegistry"):
            config = HomelabConfig()
            for var in [
                "CF_API_TOKEN",
                "CF_TUNNEL_ID",
                "PIHOLE_WEB_PASSWORD",
                "GRAFANA_PASSWORD",
                "HOMEASSISTANT_KEY",
            ]:
                assert var in config.optional_vars
                assert config.optional_vars[var]  # Pattern must not be empty


class TestLoadEnv:
    """Tests for HomelabConfig.load_env()"""

    def test_load_env_returns_empty_when_file_missing(self):
        """Test load_env returns empty dict when .env does not exist"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            result = config.load_env()
            assert result == {}

    def test_load_env_reads_key_value_pairs(self):
        """Test load_env parses KEY=VALUE lines"""
        env_content = "DOMAIN=example.com\nTIMEZONE=UTC\nPUID=1000\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            Path(tmp_dir, ".env").write_text(env_content)

            result = config.load_env()

            assert result["DOMAIN"] == "example.com"
            assert result["TIMEZONE"] == "UTC"
            assert result["PUID"] == "1000"

    def test_load_env_skips_comment_lines(self):
        """Test load_env ignores lines starting with #"""
        env_content = "# This is a comment\nDOMAIN=example.com\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            Path(tmp_dir, ".env").write_text(env_content)

            result = config.load_env()

            assert "DOMAIN" in result
            assert len(result) == 1

    def test_load_env_skips_lines_without_equals(self):
        """Test load_env silently skips malformed lines"""
        env_content = "DOMAIN=example.com\nINVALID_LINE\nTIMEZONE=UTC\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            Path(tmp_dir, ".env").write_text(env_content)

            result = config.load_env()

            assert "DOMAIN" in result
            assert "TIMEZONE" in result
            assert "INVALID_LINE" not in result

    def test_load_env_preserves_value_with_equals(self):
        """Test load_env handles values that contain = signs"""
        env_content = "TOKEN=abc=xyz=123\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            Path(tmp_dir, ".env").write_text(env_content)

            result = config.load_env()

            assert result["TOKEN"] == "abc=xyz=123"


class TestValidateConfig:
    """Tests for HomelabConfig.validate_config()"""

    def test_validate_config_returns_dict_of_bools(self):
        """Test validate_config returns Dict[str, bool]"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            result = config.validate_config()

            assert isinstance(result, dict)
            for k, v in result.items():
                assert isinstance(k, str)
                assert isinstance(v, bool)

    def test_validate_config_valid_required_vars(self):
        """Test validate_config marks valid required vars as True"""
        env_content = (
            "DOMAIN=example.com\n"
            "TIMEZONE=UTC\n"
            "PUID=1000\n"
            "PGID=1000\n"
            "TAILSCALE_IP=192.168.1.100\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            Path(tmp_dir, ".env").write_text(env_content)

            result = config.validate_config()

            assert result["DOMAIN"] is True
            assert result["TIMEZONE"] is True
            assert result["PUID"] is True
            assert result["PGID"] is True
            assert result["TAILSCALE_IP"] is True

    def test_validate_config_marks_missing_required_as_false(self):
        """Test validate_config marks missing required vars as False"""
        env_content = "DOMAIN=example.com\nTIMEZONE=UTC\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            Path(tmp_dir, ".env").write_text(env_content)

            result = config.validate_config()

            assert result["PUID"] is False
            assert result["PGID"] is False
            assert result["TAILSCALE_IP"] is False

    def test_validate_config_all_false_with_empty_env(self):
        """Test validate_config marks all vars False when .env is absent"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            result = config.validate_config()

            assert all(v is False for v in result.values())

    def test_validate_config_includes_optional_vars(self):
        """Test validate_config result includes optional variables"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            result = config.validate_config()

            for var in ["CF_API_TOKEN", "CF_TUNNEL_ID", "PIHOLE_WEB_PASSWORD"]:
                assert var in result

    def test_validate_config_valid_optional_cf_api_token(self):
        """Test CF_API_TOKEN validates with alphanumeric token"""
        env_content = (
            "DOMAIN=example.com\nTIMEZONE=UTC\nPUID=1000\nPGID=1000\n"
            "TAILSCALE_IP=192.168.1.100\n"
            "CF_API_TOKEN=abc123def456\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            Path(tmp_dir, ".env").write_text(env_content)

            result = config.validate_config()

            assert result["CF_API_TOKEN"] is True


class TestGetConfigSummary:
    """Tests for HomelabConfig.get_config_summary()"""

    def test_get_config_summary_returns_dict(self):
        """Test get_config_summary returns a dict"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            summary = config.get_config_summary()
            assert isinstance(summary, dict)

    def test_get_config_summary_includes_all_required_vars(self):
        """Test summary includes all required variables"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            summary = config.get_config_summary()

            for var in ["DOMAIN", "TIMEZONE", "PUID", "PGID", "TAILSCALE_IP"]:
                assert var in summary

    def test_get_config_summary_entry_structure(self):
        """Test each summary entry has value, valid, and required keys"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            summary = config.get_config_summary()

            for var, info in summary.items():
                assert "value" in info
                assert "valid" in info
                assert "required" in info
                assert isinstance(info["valid"], bool)
                assert isinstance(info["required"], bool)

    def test_get_config_summary_required_flag_true_for_required_vars(self):
        """Test required=True for required variables"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            summary = config.get_config_summary()

            for var in ["DOMAIN", "TIMEZONE", "PUID", "PGID", "TAILSCALE_IP"]:
                assert summary[var]["required"] is True

    def test_get_config_summary_required_flag_false_for_optional_vars(self):
        """Test required=False for optional variables"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            summary = config.get_config_summary()

            for var in ["CF_API_TOKEN", "CF_TUNNEL_ID"]:
                assert summary[var]["required"] is False


class TestGetMissingConfig:
    """Tests for HomelabConfig.get_missing_config()"""

    def test_get_missing_config_returns_list(self):
        """Test get_missing_config returns a list"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            result = config.get_missing_config()
            assert isinstance(result, list)

    def test_get_missing_config_lists_required_vars_when_env_empty(self):
        """Test all required vars appear in missing list when .env is absent"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            missing = config.get_missing_config()

            for var in ["DOMAIN", "TIMEZONE", "PUID", "PGID", "TAILSCALE_IP"]:
                assert var in missing

    def test_get_missing_config_empty_when_all_valid(self):
        """Test missing list is shorter when required vars are set"""
        env_content = (
            "DOMAIN=example.com\n"
            "TIMEZONE=UTC\n"
            "PUID=1000\n"
            "PGID=1000\n"
            "TAILSCALE_IP=192.168.1.100\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            Path(tmp_dir, ".env").write_text(env_content)

            missing = config.get_missing_config()

            for var in ["DOMAIN", "TIMEZONE", "PUID", "PGID", "TAILSCALE_IP"]:
                assert var not in missing
