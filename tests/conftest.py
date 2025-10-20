"""
Pytest configuration and fixtures for Homelab Manager tests
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from docker import DockerClient


@pytest.fixture
def temp_homelab_dir():
    """Create a temporary homelab directory for testing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        homelab_dir = Path(temp_dir) / "homelab"
        homelab_dir.mkdir()

        # Create subdirectories
        (homelab_dir / "logs").mkdir()
        (homelab_dir / "backups").mkdir()
        (homelab_dir / "appdata").mkdir()

        # Create .env file
        env_file = homelab_dir / ".env"
        env_file.write_text(
            """
# Test environment variables
DOMAIN=test.example.com
TIMEZONE=UTC
PUID=1000
PGID=1000
TAILSCALE_IP=100.64.1.1
CF_API_TOKEN=test_token_123
CF_TUNNEL_ID=12345678-1234-1234-1234-123456789012
PIHOLE_WEB_PASSWORD=test_password_123
PIHOLE_LOCAL_IPV4=100.64.1.1
GRAFANA_PASSWORD=test_password_123
HOMEASSISTANT_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ0ZXN0IiwiaWF0IjoxNjQwOTk1MjAwLCJleHAiOjE2NDA5OTg4MDAsIm5iZiI6MTY0MDk5NTIwMCwiZXhwIjoxNjQwOTk4ODAwfQ.test_signature
LUKBOT_SENTRY_DSN=https://test123@sentry.io/123456
LUKBOT_SENTRY_ORG_SLUG=test-org
LUKBOT_SENTRY_PROJECT_SLUG=test-project
LUKBOT_SENTRY_AUTH_TOKEN=test_token_123
WUD_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/REDACTED/REDACTED
WUD_SMTP_PASS=test_password_123
"""
        )

        yield homelab_dir


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing"""
    mock_client = Mock(spec=DockerClient)

    # Mock containers
    mock_container = Mock()
    mock_container.name = "test-container"
    mock_container.status = "running"
    mock_container.image.tags = ["test/image:latest"]
    mock_container.ports = {
        "80/tcp": [{"HostPort": "8080", "PrivatePort": "80"}],
        "443/tcp": [{"HostPort": "8443", "PrivatePort": "443"}],
    }

    mock_client.containers.list.return_value = [mock_container]
    mock_client.ping.return_value = True

    # Mock networks
    mock_network = Mock()
    mock_network.name = "test-network"
    mock_client.networks.get.return_value = mock_network
    mock_client.networks.create.return_value = mock_network

    return mock_client


@pytest.fixture
def mock_requests():
    """Mock requests library for HTTP testing"""
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for command execution testing"""
    with patch("subprocess.run") as mock_run:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_psutil():
    """Mock psutil for system resource testing"""
    with patch("psutil.cpu_percent", return_value=25.0), patch(
        "psutil.virtual_memory"
    ) as mock_memory, patch("psutil.disk_usage") as mock_disk:
        mock_memory.return_value.percent = 50.0
        mock_disk.return_value.percent = 30.0

        yield


@pytest.fixture(autouse=True)
def setup_test_environment(temp_homelab_dir):
    """Setup test environment for all tests"""
    # Change to test directory
    original_cwd = os.getcwd()
    os.chdir(temp_homelab_dir)

    yield

    # Restore original directory
    os.chdir(original_cwd)
