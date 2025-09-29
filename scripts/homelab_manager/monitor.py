"""
Health Monitoring - Python replacement for service testing and monitoring
"""

import asyncio
import aiohttp
import time
import json
from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class HealthCheck:
    """Represents a health check result"""
    service_name: str
    url: str
    status_code: int
    response_time: float
    is_healthy: bool
    error_message: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class HealthMonitor:
    """Monitors homelab services health"""

    def __init__(self, config):
        self.config = config
        self.console = Console()
        self.health_history: List[HealthCheck] = []
        self.monitoring = False

    async def check_service_health(self, service) -> bool:
        """Check health of a specific service"""
        try:
            # Construct URL
            if service.subdomain:
                url = f"https://{service.subdomain}.{self.config.domain}{service.health_check}"
            else:
                url = f"https://{self.config.domain}{service.health_check}"

            start_time = time.time()

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(url) as response:
                    response_time = time.time() - start_time

                    health_check = HealthCheck(
                        service_name=service.name,
                        url=url,
                        status_code=response.status,
                        response_time=response_time,
                        is_healthy=response.status in [200, 301, 302, 307],
                        timestamp=datetime.now()
                    )

                    if not health_check.is_healthy:
                        health_check.error_message = f"HTTP {response.status}"

                    self.health_history.append(health_check)
                    return health_check.is_healthy

        except asyncio.TimeoutError:
            health_check = HealthCheck(
                service_name=service.name,
                url=url,
                status_code=0,
                response_time=10.0,
                is_healthy=False,
                error_message="Timeout",
                timestamp=datetime.now()
            )
            self.health_history.append(health_check)
            return False

        except Exception as e:
            health_check = HealthCheck(
                service_name=service.name,
                url=url,
                status_code=0,
                response_time=0.0,
                is_healthy=False,
                error_message=str(e),
                timestamp=datetime.now()
            )
            self.health_history.append(health_check)
            return False

    async def check_all_services(self) -> Dict[str, bool]:
        """Check health of all services"""
        self.console.print("[blue]🔍 Checking all services health...[/blue]")

        results = {}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:

            tasks = []
            for service in self.config.services:
                if service.enabled:
                    task = progress.add_task(f"Checking {service.name}...", total=None)
                    tasks.append((service, task))

            # Run health checks concurrently
            health_tasks = []
            for service, task in tasks:
                health_tasks.append(self.check_service_health(service))
                progress.update(task, description=f"✅ Checked {service.name}")

            health_results = await asyncio.gather(*health_tasks, return_exceptions=True)

            # Process results
            for i, (service, task) in enumerate(tasks):
                if isinstance(health_results[i], Exception):
                    results[service.name] = False
                    progress.update(task, description=f"❌ {service.name} - Error")
                else:
                    results[service.name] = health_results[i]
                    status = "✅" if health_results[i] else "❌"
                    progress.update(task, description=f"{status} {service.name}")

        return results

    def show_health_status(self):
        """Display current health status"""
        table = Table(title="🏥 Homelab Health Status")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Response Time", style="blue")
        table.add_column("Last Check", style="yellow")
        table.add_column("Error", style="red")

        # Get latest health check for each service
        service_checks = {}
        for check in reversed(self.health_history):
            if check.service_name not in service_checks:
                service_checks[check.service_name] = check

        for service in self.config.services:
            if not service.enabled:
                continue

            if service.name in service_checks:
                check = service_checks[service.name]
                status = "✅ Healthy" if check.is_healthy else "❌ Unhealthy"
                response_time = f"{check.response_time:.2f}s" if check.response_time > 0 else "N/A"
                last_check = check.timestamp.strftime("%H:%M:%S")
                error = check.error_message or ""
            else:
                status = "⏳ Not Checked"
                response_time = "N/A"
                last_check = "Never"
                error = ""

            table.add_row(
                service.name,
                status,
                response_time,
                last_check,
                error
            )

        self.console.print(table)

    def show_health_history(self, service_name: Optional[str] = None, hours: int = 24):
        """Show health check history"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        filtered_checks = [
            check for check in self.health_history
            if check.timestamp >= cutoff_time
            and (service_name is None or check.service_name == service_name)
        ]

        if not filtered_checks:
            self.console.print("[yellow]No health check history found[/yellow]")
            return

        table = Table(title=f"📊 Health History ({hours}h)")
        table.add_column("Service", style="cyan")
        table.add_column("Time", style="blue")
        table.add_column("Status", style="green")
        table.add_column("Response Time", style="yellow")
        table.add_column("Error", style="red")

        for check in filtered_checks[-50:]:  # Show last 50 checks
            status = "✅" if check.is_healthy else "❌"
            response_time = f"{check.response_time:.2f}s" if check.response_time > 0 else "N/A"
            error = check.error_message or ""

            table.add_row(
                check.service_name,
                check.timestamp.strftime("%H:%M:%S"),
                status,
                response_time,
                error
            )

        self.console.print(table)

    async def start_monitoring(self, interval: int = 60):
        """Start continuous monitoring"""
        self.console.print(f"[blue]📊 Starting continuous monitoring (every {interval}s)[/blue]")
        self.monitoring = True

        while self.monitoring:
            try:
                await self.check_all_services()

                # Show status
                self.console.clear()
                self.show_health_status()

                # Wait for next check
                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Monitoring stopped by user[/yellow]")
                break
            except Exception as e:
                self.console.print(f"[red]Monitoring error: {e}[/red]")
                await asyncio.sleep(interval)

    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.monitoring = False
        self.console.print("[yellow]Stopping monitoring...[/yellow]")

    def verify_deployment(self):
        """Verify that deployment is working correctly"""
        self.console.print("[blue]🔍 Verifying deployment...[/blue]")

        # Run health checks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            results = loop.run_until_complete(self.check_all_services())

            # Show results
            healthy_services = sum(1 for healthy in results.values() if healthy)
            total_services = len(results)

            if healthy_services == total_services:
                self.console.print(f"[green]✅ All {total_services} services are healthy![/green]")
                return True
            else:
                self.console.print(f"[yellow]⚠️  {healthy_services}/{total_services} services are healthy[/yellow]")
                return False

        finally:
            loop.close()

    def get_service_metrics(self, service_name: str, hours: int = 24) -> Dict:
        """Get metrics for a specific service"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        service_checks = [
            check for check in self.health_history
            if check.service_name == service_name
            and check.timestamp >= cutoff_time
        ]

        if not service_checks:
            return {"error": "No data available"}

        healthy_checks = [check for check in service_checks if check.is_healthy]
        response_times = [check.response_time for check in healthy_checks if check.response_time > 0]

        return {
            "total_checks": len(service_checks),
            "healthy_checks": len(healthy_checks),
            "uptime_percentage": (len(healthy_checks) / len(service_checks)) * 100,
            "avg_response_time": sum(response_times) / len(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "last_check": service_checks[-1].timestamp.isoformat(),
            "last_status": "healthy" if service_checks[-1].is_healthy else "unhealthy"
        }

    def export_health_data(self, filename: str):
        """Export health data to JSON file"""
        data = {
            "export_time": datetime.now().isoformat(),
            "services": self.config.services,
            "health_checks": [
                {
                    "service_name": check.service_name,
                    "url": check.url,
                    "status_code": check.status_code,
                    "response_time": check.response_time,
                    "is_healthy": check.is_healthy,
                    "error_message": check.error_message,
                    "timestamp": check.timestamp.isoformat()
                }
                for check in self.health_history
            ]
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        self.console.print(f"[green]✅ Health data exported to {filename}[/green]")

    def clear_health_history(self):
        """Clear health check history"""
        self.health_history.clear()
        self.console.print("[green]✅ Health history cleared[/green]")
