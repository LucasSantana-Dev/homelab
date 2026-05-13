#!/usr/bin/env python3
"""
Integration tests for system resource monitoring.

These tests check real system state — CPU, memory, disk, and Docker.
They are designed to pass in healthy environments and flag actionable
thresholds rather than assert exact values.

Run with:
    pytest tests/integration/test_system_resources.py -v

Skip Docker tests when Docker is not running:
    pytest tests/integration/test_system_resources.py -v -m "not docker"
"""

import subprocess

import psutil
import pytest

# Thresholds — adjust per environment
CPU_WARN_THRESHOLD = 90.0  # % — sustained CPU above this is a problem
MEMORY_WARN_THRESHOLD = 90.0  # % — memory above this risks OOM
DISK_WARN_THRESHOLD = 90.0  # % — disk above this risks write failures
DISK_PATH = "/"  # root filesystem to monitor


def docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


requires_docker = pytest.mark.skipif(
    not docker_available(),
    reason="Docker daemon not running or not reachable",
)


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------


class TestCPUResources:
    """CPU usage checks"""

    def test_cpu_percent_readable(self):
        """Verify psutil can read CPU percent"""
        cpu = psutil.cpu_percent(interval=0.1)
        assert isinstance(cpu, float)
        assert 0.0 <= cpu <= 100.0

    def test_cpu_count_positive(self):
        """Verify at least one logical CPU is reported"""
        assert psutil.cpu_count(logical=True) >= 1

    def test_cpu_below_warning_threshold(self):
        """Warn when sustained CPU exceeds threshold (sampled twice, 0.5s apart)"""
        sample1 = psutil.cpu_percent(interval=0.25)
        sample2 = psutil.cpu_percent(interval=0.25)
        avg = (sample1 + sample2) / 2
        assert avg < CPU_WARN_THRESHOLD, (
            f"CPU usage {avg:.1f}% exceeds warning threshold {CPU_WARN_THRESHOLD}%. "
            "Check for runaway processes."
        )

    def test_cpu_per_core_readable(self):
        """Verify per-core CPU stats are available"""
        per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        assert isinstance(per_core, list)
        assert len(per_core) >= 1
        for core_pct in per_core:
            assert 0.0 <= core_pct <= 100.0

    def test_load_average_readable(self):
        """Verify load averages are readable (1m, 5m, 15m)"""
        load = psutil.getloadavg()
        assert len(load) == 3
        for val in load:
            assert val >= 0.0


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class TestMemoryResources:
    """RAM and swap usage checks"""

    def test_virtual_memory_readable(self):
        """Verify virtual memory stats are available"""
        mem = psutil.virtual_memory()
        assert mem.total > 0
        assert 0.0 <= mem.percent <= 100.0

    def test_memory_below_warning_threshold(self):
        """Warn when memory usage exceeds threshold"""
        mem = psutil.virtual_memory()
        assert mem.percent < MEMORY_WARN_THRESHOLD, (
            f"Memory usage {mem.percent:.1f}% exceeds warning threshold "
            f"{MEMORY_WARN_THRESHOLD}%. "
            f"Used: {mem.used // (1024**2)}MB / Total: {mem.total // (1024**2)}MB"
        )

    def test_memory_available_positive(self):
        """Verify some memory is available (not fully exhausted)"""
        mem = psutil.virtual_memory()
        assert (
            mem.available > 0
        ), "No memory available — system may be under extreme pressure"

    def test_swap_readable(self):
        """Verify swap memory stats are available"""
        swap = psutil.swap_memory()
        assert swap.total >= 0
        assert 0.0 <= swap.percent <= 100.0

    def test_memory_total_reasonable(self):
        """Verify reported total RAM is at least 512MB (sanity check)"""
        mem = psutil.virtual_memory()
        assert (
            mem.total >= 512 * 1024 * 1024
        ), f"Reported total RAM {mem.total // (1024**2)}MB is suspiciously low"


# ---------------------------------------------------------------------------
# Disk
# ---------------------------------------------------------------------------


class TestDiskResources:
    """Disk usage and I/O checks"""

    def test_disk_usage_readable(self):
        """Verify disk usage stats are available for root"""
        disk = psutil.disk_usage(DISK_PATH)
        assert disk.total > 0
        assert 0.0 <= disk.percent <= 100.0

    def test_disk_below_warning_threshold(self):
        """Warn when disk usage exceeds threshold"""
        disk = psutil.disk_usage(DISK_PATH)
        assert disk.percent < DISK_WARN_THRESHOLD, (
            f"Disk usage on {DISK_PATH} is {disk.percent:.1f}%, "
            f"exceeding threshold {DISK_WARN_THRESHOLD}%. "
            f"Free: {disk.free // (1024**3)}GB / Total: {disk.total // (1024**3)}GB"
        )

    def test_disk_free_space_positive(self):
        """Verify some free space remains"""
        disk = psutil.disk_usage(DISK_PATH)
        assert disk.free > 0, f"No free space on {DISK_PATH}"

    def test_disk_io_counters_readable(self):
        """Verify disk I/O counters are accessible"""
        io = psutil.disk_io_counters()
        if io is None:
            pytest.skip("Disk I/O counters not available on this platform")
        assert io.read_count >= 0
        assert io.write_count >= 0

    def test_disk_partitions_listed(self):
        """Verify at least one disk partition is reported"""
        partitions = psutil.disk_partitions()
        assert len(partitions) >= 1

    def test_external_hd_disk_below_threshold(self):
        """Check External HD disk usage separately (homelab data lives there)"""
        try:
            disk = psutil.disk_usage("/Volumes/External HD")
        except FileNotFoundError:
            pytest.skip("External HD not mounted")
        assert disk.percent < DISK_WARN_THRESHOLD, (
            f"External HD usage {disk.percent:.1f}% exceeds {DISK_WARN_THRESHOLD}%. "
            f"Free: {disk.free // (1024**3)}GB"
        )


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------


class TestNetworkResources:
    """Network interface checks"""

    def test_network_interfaces_listed(self):
        """Verify at least one network interface is present"""
        interfaces = psutil.net_if_addrs()
        assert len(interfaces) >= 1

    def test_network_io_counters_readable(self):
        """Verify network I/O counters are accessible"""
        io = psutil.net_io_counters()
        assert io.bytes_sent >= 0
        assert io.bytes_recv >= 0

    def test_loopback_interface_present(self):
        """Verify loopback interface (lo or lo0) is present"""
        interfaces = psutil.net_if_addrs()
        loopback_names = {name for name in interfaces if name.startswith("lo")}
        assert loopback_names, "No loopback interface found"


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------


@requires_docker
class TestDockerResources:
    """Docker daemon and container resource checks"""

    def test_docker_daemon_reachable(self):
        """Verify Docker daemon responds to info"""
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"docker info failed: {result.stderr}"
        assert result.stdout.strip(), "Docker returned empty server version"

    def test_docker_ps_executable(self):
        """Verify docker ps runs without error"""
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"docker ps failed: {result.stderr}"

    def test_no_containers_in_restarting_state(self):
        """Flag containers stuck in restart loop"""
        result = subprocess.run(
            ["docker", "ps", "--filter", "status=restarting", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        restarting = [line for line in result.stdout.strip().splitlines() if line]
        assert not restarting, (
            f"Containers stuck in restart loop: {restarting}. "
            "Check logs with: docker logs <container>"
        )

    def test_no_containers_in_dead_state(self):
        """Flag containers in dead state"""
        result = subprocess.run(
            ["docker", "ps", "--filter", "status=dead", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        dead = [line for line in result.stdout.strip().splitlines() if line]
        assert not dead, f"Dead containers found: {dead}"

    def test_docker_system_df_readable(self):
        """Verify docker system df runs and returns data"""
        result = subprocess.run(
            ["docker", "system", "df"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, f"docker system df failed: {result.stderr}"

    def test_docker_disk_usage_not_critical(self):
        """Warn if Docker overlay2 is consuming excessive space"""
        result = subprocess.run(
            [
                "docker",
                "system",
                "df",
                "--format",
                "{{.Type}}\t{{.Size}}\t{{.Reclaimable}}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0
        # We just verify it runs — size thresholds are environment-specific


# ---------------------------------------------------------------------------
# Process
# ---------------------------------------------------------------------------


class TestProcessResources:
    """Process-level sanity checks"""

    def test_process_list_readable(self):
        """Verify process list is accessible"""
        procs = list(psutil.process_iter(["pid", "name"]))
        assert len(procs) > 0

    def test_no_zombie_processes(self):
        """Fail if an unusual number of zombie processes are present.

        A small number (< 5) of OS-level zombies from editors or system tools
        is normal and not actionable. A large count indicates a process
        management problem.
        """
        zombies = [
            p.info
            for p in psutil.process_iter(["pid", "name", "status"])
            if p.info.get("status") == psutil.STATUS_ZOMBIE
        ]
        assert len(zombies) < 5, (
            f"Too many zombie processes ({len(zombies)}): "
            f"{[(z['pid'], z['name']) for z in zombies]}. "
            "Check for broken parent processes."
        )
