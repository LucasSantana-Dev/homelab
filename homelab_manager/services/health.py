#!/usr/bin/env python3
"""
Health Monitoring Service
Monitor health and status of homelab services
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from typing import Dict, List, Optional

import requests
from rich.console import Console

from ..clients.docker_client import get_docker_client
from ..core.errors import scrub_subprocess_error
from ..core.log import trace_context
from ..models.service import ServiceRegistry

# Initialize console
console = Console()
logger = logging.getLogger(__name__)

# Per-check timeout in seconds
CHECK_TIMEOUT = 15


class HealthMonitor:
    """Monitor health of homelab services"""

    def __init__(self, registry: Optional[ServiceRegistry] = None):
        self.registry = registry or ServiceRegistry()
        self.timeout = 5
        # R1 Phase C: single owner for docker.from_env() lives in
        # homelab_manager.clients.docker_client; factory returns None on
        # daemon unreachable, matching the previous try/except fallback.
        self.docker_client = get_docker_client()

    def check_service(
        self,
        service_name: str,
        url: str,
        expected_statuses: Optional[List[int]] = None,
    ) -> Dict:
        """Check health of a single service over HTTP"""
        expected = expected_statuses or [200]
        start_time = time.time()

        try:
            response = requests.get(url, timeout=self.timeout)
            response_time = (time.time() - start_time) * 1000

            return {
                "healthy": response.status_code in expected,
                "status_code": response.status_code,
                "response_time": response_time,
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": None,
                "source": "http",
            }

        except requests.exceptions.RequestException as e:
            logger.debug("http check failed", exc_info=True)
            return {
                "healthy": False,
                "status_code": None,
                "response_time": None,
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": scrub_subprocess_error(e, context="HTTP check failed"),
                "source": "http",
            }

    def check_container_health(self, container_name: str) -> Dict:
        """Check service health using Docker container status and healthcheck state."""
        if self.docker_client is None:
            return {
                "healthy": False,
                "status_code": None,
                "response_time": None,
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": "Docker client is not available",
                "source": "docker",
            }

        try:
            container = self.docker_client.containers.get(container_name)
            state = container.attrs.get("State", {})
            container_status = state.get("Status", "unknown")
            health_data = state.get("Health")

            if health_data:
                health_status = health_data.get("Status", "unknown")
                last_log = ""
                health_log = health_data.get("Log", [])
                if health_log:
                    last_output = health_log[-1].get("Output", "")
                    last_log = last_output.strip()[:200]

                return {
                    "healthy": health_status == "healthy",
                    "status_code": None,
                    "response_time": None,
                    "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "error": (
                        None
                        if health_status == "healthy"
                        else last_log or health_status
                    ),
                    "source": "docker",
                }

            # No healthcheck configured: use running state as service health.
            return {
                "healthy": container_status == "running",
                "status_code": None,
                "response_time": None,
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": None if container_status == "running" else container_status,
                "source": "docker",
            }
        except Exception as e:
            logger.debug("docker check failed", exc_info=True)
            return {
                "healthy": False,
                "status_code": None,
                "response_time": None,
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": scrub_subprocess_error(e, context="Docker check failed"),
                "source": "docker",
            }

    def _check_service_by_policy(self, service) -> Dict:
        """Check service health according to service registry health policy."""
        mode = (service.health_mode or "docker").lower()

        if mode == "none":
            return {
                "healthy": True,
                "status_code": None,
                "response_time": None,
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": None,
                "source": "skipped",
            }

        if mode == "http":
            if not service.health_url:
                return {
                    "healthy": False,
                    "status_code": None,
                    "response_time": None,
                    "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "error": "HTTP health mode configured without health_url",
                    "source": "http",
                }
            return self.check_service(
                service.id,
                service.health_url,
                expected_statuses=service.expected_statuses,
            )

        # docker mode and auto both prefer Docker-first checks
        docker_result = self.check_container_health(service.container_name)
        if mode == "auto" and docker_result.get("error") and service.health_url:
            return self.check_service(
                service.id,
                service.health_url,
                expected_statuses=service.expected_statuses,
            )
        return docker_result

    def check_all_services(self) -> Dict[str, Dict]:
        """Check health of all services from the registry with per-service timeout."""
        services = [
            s
            for s in self.registry.get_services_with_ports()
            if (s.health_mode or "docker").lower() != "none"
        ]
        if not services:
            return {}

        def _check(service):
            # Tag every log line emitted while checking this service with its id,
            # so the interleaved output of the parallel sweep stays traceable.
            with trace_context(str(service.id)):
                return service.id, self._check_service_by_policy(service)

        results = {}
        with ThreadPoolExecutor(max_workers=min(len(services), 20)) as executor:
            # Submit all tasks
            futures = {
                executor.submit(_check, service): service for service in services
            }

            # Process results as they complete, with timeout for overall sweep
            try:
                for future in as_completed(futures, timeout=CHECK_TIMEOUT):
                    service = futures[future]
                    try:
                        service_id, result = future.result(timeout=1)
                        results[service_id] = result
                    except TimeoutError:
                        # Single check timed out; mark it as timeout and continue
                        logger.warning(
                            "Health check timeout for service %s", service.id
                        )
                        results[service.id] = {
                            "healthy": False,
                            "status_code": None,
                            "response_time": None,
                            "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "error": "Health check timed out",
                            "source": "timeout",
                        }
                    except Exception as e:
                        # Other exceptions during check execution
                        logger.error(
                            "Error during health check for service %s: %s",
                            service.id,
                            e,
                            exc_info=True,
                        )
                        results[service.id] = {
                            "healthy": False,
                            "status_code": None,
                            "response_time": None,
                            "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "error": "Health check failed: " + str(type(e).__name__),
                            "source": "error",
                        }
            except TimeoutError:
                # Overall sweep timeout - mark unfinished futures as timeout
                logger.warning("Overall health check sweep timeout")
                for future, service in futures.items():
                    if service.id not in results:
                        results[service.id] = {
                            "healthy": False,
                            "status_code": None,
                            "response_time": None,
                            "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "error": "Health check timed out",
                            "source": "timeout",
                        }

        return results

    def get_health_summary(self) -> Dict:
        """Get summary of health status"""
        health_status = self.check_all_services()

        total_services = len(health_status)
        healthy_services = sum(
            1 for status in health_status.values() if status["healthy"]
        )
        unhealthy_services = total_services - healthy_services

        return {
            "total_services": total_services,
            "healthy_services": healthy_services,
            "unhealthy_services": unhealthy_services,
            "health_percentage": (
                (healthy_services / total_services) * 100 if total_services > 0 else 0
            ),
            "services": health_status,
        }

    def get_unhealthy_services(self) -> List[str]:
        """Get list of unhealthy services"""
        health_status = self.check_all_services()
        return [
            service
            for service, status in health_status.items()
            if not status["healthy"]
        ]

    def check_service_by_id(self, service_id: str) -> Optional[Dict]:
        """Check health of a specific service by its ID"""
        service = self.registry.get_service(service_id)
        if not service:
            return None
        return self._check_service_by_policy(service)
