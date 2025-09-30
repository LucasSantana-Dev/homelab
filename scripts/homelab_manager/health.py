#!/usr/bin/env python3
"""
Homelab Health Monitor
Python-based health monitoring for homelab services
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import docker
import psutil
import requests
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Initialize console
console = Console()


class HomelabHealthMonitor:
    """Health monitoring for homelab services"""

    def __init__(self, homelab_dir: Optional[str] = None):
        self.homelab_dir = (
            Path(homelab_dir) if homelab_dir else Path(__file__).parent.parent.parent
        )
        self.log_dir = self.homelab_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)

        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
        except docker.errors.DockerException:
            console.print("❌ Docker is not running or not accessible", style="red")
            sys.exit(1)

        # Services to monitor
        self.services = [
            ("Homepage", "http://localhost:3000"),
            ("Home Assistant", "http://localhost:8123"),
            ("Grafana", "http://localhost:3002"),
            ("Portainer", "http://localhost:9000"),
        ]

    def check_service_health(self, name: str, url: str) -> Tuple[bool, str]:
        """Check if a service is healthy"""
        try:
            response = requests.get(url, timeout=5)
            if response.status_code < 500:
                return True, f"Status {response.status_code}"
            else:
                return False, f"Status {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, str(e)

    def check_system_resources(self) -> Dict[str, float]:
        """Check system resource usage"""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        }

    def check_docker_containers(self) -> List[Dict]:
        """Check Docker container status"""
        containers = []

        try:
            for container in self.docker_client.containers.list():
                # Get port information safely
                ports = []
                if container.ports:
                    for port_info in container.ports.values():
                        if port_info:  # Check if port_info is not None
                            for port in port_info:
                                host_port = port.get("HostPort", "unknown")
                                private_port = port.get(
                                    "PrivatePort", port.get("TargetPort", "unknown")
                                )
                                ports.append(f"{host_port}:{private_port}")

                containers.append(
                    {
                        "name": container.name,
                        "status": container.status,
                        "image": (
                            container.image.tags[0]
                            if container.image.tags
                            else "unknown"
                        ),
                        "ports": ports,
                    }
                )
        except Exception as e:
            console.print(f"⚠️ Error checking containers: {e}", style="yellow")

        return containers

    def run_health_check(self):
        """Run comprehensive health check"""
        console.print(Panel.fit("🏠 Homelab Health Check", style="blue"))
        console.print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print()

        # Check system resources
        console.print("📊 System Resources", style="blue")
        resources = self.check_system_resources()

        resource_table = Table(show_header=True, header_style="bold blue")
        resource_table.add_column("Resource", style="cyan")
        resource_table.add_column("Usage", style="green")
        resource_table.add_column("Status", style="yellow")

        for resource, value in resources.items():
            status = (
                "✅ Good" if value < 80 else "⚠️ High" if value < 90 else "❌ Critical"
            )
            color = "green" if value < 80 else "yellow" if value < 90 else "red"
            resource_table.add_row(
                resource.replace("_", " ").title(),
                f"{value:.1f}%",
                f"[{color}]{status}[/{color}]",
            )

        console.print(resource_table)
        console.print()

        # Check Docker containers
        console.print("🐳 Docker Containers", style="blue")
        containers = self.check_docker_containers()

        if containers:
            container_table = Table(show_header=True, header_style="bold blue")
            container_table.add_column("Name", style="cyan")
            container_table.add_column("Status", style="green")
            container_table.add_column("Image", style="blue")
            container_table.add_column("Ports", style="yellow")

            for container in containers:
                status_color = "green" if container["status"] == "running" else "red"
                container_table.add_row(
                    container["name"],
                    f"[{status_color}]{container['status']}[/{status_color}]",
                    container["image"],
                    ", ".join(container["ports"]) if container["ports"] else "No ports",
                )

            console.print(container_table)
        else:
            console.print("⚠️ No containers found", style="yellow")

        console.print()

        # Check services
        console.print("🌐 Service Health", style="blue")
        service_table = Table(show_header=True, header_style="bold blue")
        service_table.add_column("Service", style="cyan")
        service_table.add_column("URL", style="blue")
        service_table.add_column("Status", style="green")
        service_table.add_column("Details", style="yellow")

        healthy_count = 0

        for name, url in self.services:
            is_healthy, details = self.check_service_health(name, url)
            if is_healthy:
                healthy_count += 1
                status = "[green]✅ Healthy[/green]"
            else:
                status = "[red]❌ Unhealthy[/red]"

            service_table.add_row(name, url, status, details)

        console.print(service_table)
        console.print()

        # Summary
        total_services = len(self.services)
        console.print("📊 Health Summary", style="blue")
        console.print(f"Healthy services: {healthy_count}/{total_services}")

        if healthy_count == total_services:
            console.print("🎉 All services are healthy!", style="green")
        else:
            console.print("⚠️ Some services are not responding", style="yellow")

    def quick_status(self):
        """Show quick status overview"""
        console.print(Panel.fit("🏠 Homelab Quick Status", style="blue"))

        # Quick container check
        console.print("\n🐳 Containers:", style="yellow")
        try:
            containers = self.docker_client.containers.list()
            for container in containers[:5]:  # Show first 5
                status_color = "green" if container.status == "running" else "red"
                console.print(
                    f"  [{status_color}]{container.name}[/{status_color}]: {container.status}"
                )
        except Exception as e:
            console.print(f"  ⚠️ Error: {e}", style="yellow")

        # Quick resource check
        console.print("\n💾 Resources:", style="yellow")
        resources = self.check_system_resources()
        console.print(f"  Memory: {resources['memory_percent']:.1f}%")
        console.print(f"  Disk: {resources['disk_percent']:.1f}%")
        console.print(f"  CPU: {resources['cpu_percent']:.1f}%")

        # Quick service check
        console.print("\n🌐 Services:", style="yellow")
        for name, url in self.services[:3]:  # Check first 3 services
            is_healthy, _ = self.check_service_health(name, url)
            status = "✅" if is_healthy else "❌"
            console.print(f"  {status} {name}")

    def monitor_continuous(self, interval: int = 60):
        """Run continuous monitoring"""
        console.print(Panel.fit("📊 Continuous Monitoring", style="blue"))
        console.print(f"Checking every {interval} seconds. Press Ctrl+C to stop.")
        console.print()

        try:
            while True:
                # Clear screen
                subprocess.run(["clear" if os.name == "posix" else "cls"], check=False)

                # Run health check
                self.run_health_check()

                console.print(f"\nNext check in {interval} seconds...")
                time.sleep(interval)

        except KeyboardInterrupt:
            console.print("\n🛑 Monitoring stopped", style="yellow")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Homelab Health Monitor")
    parser.add_argument(
        "action", choices=["check", "status", "monitor"], help="Action to perform"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Monitoring interval in seconds (default: 60)",
    )

    args = parser.parse_args()

    monitor = HomelabHealthMonitor()

    if args.action == "check":
        monitor.run_health_check()
    elif args.action == "status":
        monitor.quick_status()
    elif args.action == "monitor":
        monitor.monitor_continuous(args.interval)


if __name__ == "__main__":
    main()
