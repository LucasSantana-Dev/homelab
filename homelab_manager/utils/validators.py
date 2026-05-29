#!/usr/bin/env python3
"""
Configuration Validators — thin shim over HomelabConfig.

Validation patterns and logic now live in HomelabConfig.validate_value(),
get_validation_errors(), and is_configured(). This module exists for
backwards-compatible imports only.

INTENTIONALLY RETAINED (per ADR-0007): this is a deliberate compat shim, and
it is exercised by tests (tests/unit/test_automation.py::TestConfigValidator).
It is NOT dead code — do not flag for deletion in audits.
"""

from ..core.config import HomelabConfig as _HomelabConfig

_cfg = _HomelabConfig()


class ConfigValidator:
    """Thin shim — delegates to HomelabConfig methods."""

    PATTERNS = {**_cfg.required_vars, **_cfg.optional_vars}

    @classmethod
    def validate_config_value(cls, key: str, value: str) -> bool:
        return _cfg.validate_value(key, value)

    @classmethod
    def get_validation_errors(cls, config: dict) -> list:
        return _cfg.get_validation_errors(config)

    @classmethod
    def is_configured(cls, value: str) -> bool:
        return _HomelabConfig.is_configured(value)

    @classmethod
    def validate_domain(cls, domain: str) -> bool:
        return cls.validate_config_value("DOMAIN", domain)

    @classmethod
    def validate_ip(cls, ip: str) -> bool:
        return cls.validate_config_value("TAILSCALE_IP", ip)

    @classmethod
    def validate_uuid(cls, uuid: str) -> bool:
        return cls.validate_config_value("CF_TUNNEL_ID", uuid)

    @classmethod
    def validate_password(cls, password: str, min_length: int = 8) -> bool:
        return len(password) >= min_length
