#!/usr/bin/env python3
"""
Health Monitoring Service
Monitor health and status of homelab services
"""

import time
from typing import Dict, List, Optional
import requests
from rich.console import Console
from rich.table import Table

# Initialize console
console = Console()


class HealthMonitor:
    """Monitor health of homelab services"""

    def __init__(self):
        self.services = {
            "homepage": "http://localhost:3000",
            "stremio": "http://localhost:8080",
            "homeassistant": "http://localhost:8123",
            "portainer": "http://localhost:9000",
            "pihole": "http://localhost:8054",
            "grafana": "http://localhost:3002",
            "uptime-kuma": "http://localhost:3001",
            "whats-up-docker": "http://localhost:3003"
        }
        self.timeout = 5

    def check_service(self, service_name: str, url: str) -> Dict:
        """Check health of a single service"""
        start_time = time.time()

        try:
            response = requests.get(url, timeout=self.timeout)
            response_time = (time.time() - start_time) * 1000

            return {
                "healthy": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": response_time,
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": None
            }

        except requests.exceptions.RequestException as e:
            return {
                "healthy": False,
                "status_code": None,
                "response_time": None,
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(e)
            }

    def check_all_services(self) -> Dict[str, Dict]:
        """Check health of all services"""
        results = {}

        for service_name, url in self.services.items():
            results[service_name] = self.check_service(service_name, url)

        return results

    def get_health_summary(self) -> Dict:
        """Get summary of health status"""
        health_status = self.check_all_services()

        total_services = len(health_status)
        healthy_services = sum(1 for status in health_status.values() if status["healthy"])
        unhealthy_services = total_services - healthy_services

        return {
            "total_services": total_services,
            "healthy_services": healthy_services,
            "unhealthy_services": unhealthy_services,
            "health_percentage": (healthy_services / total_services) * 100 if total_services > 0 else 0,
            "services": health_status
        }

    def get_unhealthy_services(self) -> List[str]:
        """Get list of unhealthy services"""
        health_status = self.check_all_services()
        return [service for service, status in health_status.items() if not status["healthy"]]
