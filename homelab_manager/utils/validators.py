#!/usr/bin/env python3
"""
Configuration Validators
Validation utilities for homelab configuration
"""

import re
from typing import Dict, List, Optional


class ConfigValidator:
    """Validate homelab configuration"""

    # Validation patterns
    PATTERNS = {
        "DOMAIN": r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "TIMEZONE": r"^[A-Za-z_/]+$",
        "PUID": r"^[0-9]+$",
        "PGID": r"^[0-9]+$",
        "TAILSCALE_IP": r"^([0-9]{1,3}\.){3}[0-9]{1,3}$",
        "CF_API_TOKEN": r"^[a-zA-Z0-9_-]+$",
        "CF_TUNNEL_ID": r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        "PIHOLE_WEB_PASSWORD": r"^.{8,}$",
        "GRAFANA_PASSWORD": r"^.{8,}$",
        "HOMEASSISTANT_KEY": r"^[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$",
    }

    @classmethod
    def validate_domain(cls, domain: str) -> bool:
        """Validate domain format"""
        return bool(re.match(cls.PATTERNS["DOMAIN"], domain))

    @classmethod
    def validate_ip(cls, ip: str) -> bool:
        """Validate IP address format"""
        return bool(re.match(cls.PATTERNS["TAILSCALE_IP"], ip))

    @classmethod
    def validate_password(cls, password: str, min_length: int = 8) -> bool:
        """Validate password strength"""
        return len(password) >= min_length

    @classmethod
    def validate_uuid(cls, uuid: str) -> bool:
        """Validate UUID format"""
        return bool(re.match(cls.PATTERNS["CF_TUNNEL_ID"], uuid))

    @classmethod
    def validate_config_value(cls, key: str, value: str) -> bool:
        """Validate a configuration value"""
        if key not in cls.PATTERNS:
            return True  # Unknown key, assume valid

        pattern = cls.PATTERNS[key]
        return bool(re.match(pattern, value))

    @classmethod
    def get_validation_errors(cls, config: Dict[str, str]) -> List[str]:
        """Get list of validation errors"""
        errors = []

        for key, value in config.items():
            if not cls.validate_config_value(key, value):
                errors.append(f"Invalid value for {key}: {value}")

        return errors

    @classmethod
    def is_configured(cls, value: str) -> bool:
        """Check if a value is properly configured (not placeholder)"""
        if not value or value.startswith("your_") or value == "your-domain.com":
            return False
        return True
