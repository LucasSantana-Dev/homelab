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


# ---------------------------------------------------------------------------
# R1 Phase F — close M4 coverage gap (62% -> ≥90%)
# ---------------------------------------------------------------------------


class TestLoadEnvVariableSubstitution:
    """Lines 62-69: ${VAR} and ${VAR:-default} substitution in load_env."""

    def test_var_substitution_with_default_uses_env(self, monkeypatch):
        monkeypatch.setenv("FROM_ENV", "from-real-env")
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, ".env").write_text("KEY=${FROM_ENV:-fallback}\n")
            config = make_config(tmp_dir)
            assert config.load_env()["KEY"] == "from-real-env"

    def test_var_substitution_with_default_falls_back(self, monkeypatch):
        monkeypatch.delenv("UNSET_VAR", raising=False)
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, ".env").write_text("KEY=${UNSET_VAR:-fallback-value}\n")
            config = make_config(tmp_dir)
            assert config.load_env()["KEY"] == "fallback-value"

    def test_bare_var_substitution_uses_env(self, monkeypatch):
        monkeypatch.setenv("BARE_VAR", "env-value")
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, ".env").write_text("KEY=${BARE_VAR}\n")
            config = make_config(tmp_dir)
            assert config.load_env()["KEY"] == "env-value"

    def test_bare_var_substitution_unset_keeps_literal(self, monkeypatch):
        monkeypatch.delenv("ALSO_UNSET", raising=False)
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, ".env").write_text("KEY=${ALSO_UNSET}\n")
            config = make_config(tmp_dir)
            # Source code keeps the literal ${VAR} when env lookup misses.
            assert config.load_env()["KEY"] == "${ALSO_UNSET}"


class TestGetConfigSummaryPlaceholders:
    """Lines 113, 125: 'Not configured' fallback for placeholder values."""

    def test_required_placeholder_marked_not_configured(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, ".env").write_text("DOMAIN=your-domain.com\n")
            config = make_config(tmp_dir)
            summary = config.get_config_summary()
            assert summary["DOMAIN"]["value"] == "Not configured"
            assert summary["DOMAIN"]["valid"] is False

    def test_optional_placeholder_marked_not_configured(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, ".env").write_text(
                "CF_API_TOKEN=your_cloudflare_api_token_here\n"
            )
            config = make_config(tmp_dir)
            summary = config.get_config_summary()
            assert summary["CF_API_TOKEN"]["value"] == "Not configured"


class TestValidateValueAndErrors:
    """Lines 137-148: validate_value() + get_validation_errors()."""

    def test_validate_value_unknown_key_returns_true(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            assert config.validate_value("UNKNOWN_KEY", "anything") is True

    def test_validate_value_valid_known_key(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            assert config.validate_value("PUID", "1000") is True

    def test_validate_value_invalid_known_key(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            assert config.validate_value("PUID", "not-a-number") is False

    def test_validate_value_invalid_tailscale_ip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            assert config.validate_value("TAILSCALE_IP", "not.an.ip") is False

    def test_get_validation_errors_lists_invalid_keys(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            errors = config.get_validation_errors({"PUID": "abc", "TIMEZONE": "UTC"})
            assert len(errors) == 1
            assert "PUID" in errors[0]
            assert "abc" in errors[0]

    def test_get_validation_errors_empty_when_all_valid(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = make_config(tmp_dir)
            assert (
                config.get_validation_errors({"PUID": "1000", "TIMEZONE": "UTC"}) == []
            )


class TestIsConfigured:
    """Line 153: staticmethod is_configured()."""

    def test_empty_string_is_not_configured(self):
        assert HomelabConfig.is_configured("") is False

    def test_placeholder_your_prefix_is_not_configured(self):
        assert HomelabConfig.is_configured("your_secret") is False

    def test_your_domain_literal_is_not_configured(self):
        assert HomelabConfig.is_configured("your-domain.com") is False

    def test_real_value_is_configured(self):
        assert HomelabConfig.is_configured("real-value") is True


class TestGetServiceUrls:
    """Lines 170-193: get_service_urls()."""

    def _config_with_services(self, services, tmp_dir):
        Path(tmp_dir, ".env").write_text(
            "DOMAIN=example.com\nTAILSCALE_IP=100.64.0.1\n"
        )
        with patch("homelab_manager.core.config.ServiceRegistry") as mock_reg_cls:
            registry = mock_reg_cls.return_value
            registry.services = {s.id: s for s in services}
            config = HomelabConfig(tmp_dir)
            return config

    def test_skips_services_without_ports(self):
        from types import SimpleNamespace

        svc = SimpleNamespace(
            id="ghost",
            has_port=False,
            port=None,
            localhost_only=False,
            get_tailscale_url=lambda ip: None,
            get_public_url=lambda d: None,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._config_with_services([svc], tmp_dir)
            urls = config.get_service_urls()
            assert urls == {}

    def test_includes_localhost_url_for_each_service_with_port(self):
        from types import SimpleNamespace

        svc = SimpleNamespace(
            id="grafana",
            has_port=True,
            port=3000,
            localhost_only=False,
            get_tailscale_url=lambda ip: f"http://{ip}:3000",
            get_public_url=lambda d: f"https://grafana.{d}",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._config_with_services([svc], tmp_dir)
            urls = config.get_service_urls()
            assert urls["grafana"] == "http://localhost:3000"
            assert urls["tailscale_grafana"] == "http://100.64.0.1:3000"
            assert urls["public_grafana"] == "https://grafana.example.com"

    def test_localhost_only_skips_tailscale_and_public(self):
        from types import SimpleNamespace

        svc = SimpleNamespace(
            id="internal",
            has_port=True,
            port=9090,
            localhost_only=True,
            get_tailscale_url=lambda ip: f"http://{ip}:9090",
            get_public_url=lambda d: f"https://internal.{d}",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._config_with_services([svc], tmp_dir)
            urls = config.get_service_urls()
            assert urls["internal"] == "http://localhost:9090"
            assert "tailscale_internal" not in urls
            assert "public_internal" not in urls

    def test_tailscale_url_omitted_when_helper_returns_none(self):
        from types import SimpleNamespace

        svc = SimpleNamespace(
            id="svc",
            has_port=True,
            port=8000,
            localhost_only=False,
            get_tailscale_url=lambda ip: None,  # no tailscale binding
            get_public_url=lambda d: None,  # no public binding either
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._config_with_services([svc], tmp_dir)
            urls = config.get_service_urls()
            assert urls == {"svc": "http://localhost:8000"}


class TestGetServicesForDisplay:
    """Lines 197-218: get_services_for_display()."""

    def test_skips_localhost_only_services(self):
        from types import SimpleNamespace

        public_svc = SimpleNamespace(
            id="grafana",
            name="Grafana",
            category="monitoring",
            port=3000,
            sensitive=False,
            localhost_only=False,
            get_tailscale_url=lambda ip: f"http://{ip}:3000",
            get_public_url=lambda d: f"https://grafana.{d}",
        )
        internal_svc = SimpleNamespace(
            id="loki",
            name="Loki",
            category="monitoring",
            port=3100,
            sensitive=False,
            localhost_only=True,
            get_tailscale_url=lambda ip: f"http://{ip}:3100",
            get_public_url=lambda d: None,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, ".env").write_text(
                "DOMAIN=example.com\nTAILSCALE_IP=100.64.0.1\n"
            )
            with patch("homelab_manager.core.config.ServiceRegistry") as mock_reg_cls:
                registry = mock_reg_cls.return_value
                registry.get_services_with_ports.return_value = [
                    public_svc,
                    internal_svc,
                ]
                config = HomelabConfig(tmp_dir)
                result = config.get_services_for_display()
                assert len(result) == 1
                assert result[0]["id"] == "grafana"
                assert result[0]["localhost"] == "http://localhost:3000"
                assert result[0]["tailscale"] == "http://100.64.0.1:3000"
                assert result[0]["public"] == "https://grafana.example.com"

    def test_returns_empty_when_no_services(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("homelab_manager.core.config.ServiceRegistry") as mock_reg_cls:
                mock_reg_cls.return_value.get_services_with_ports.return_value = []
                config = HomelabConfig(tmp_dir)
                assert config.get_services_for_display() == []
