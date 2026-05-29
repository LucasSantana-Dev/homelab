#!/usr/bin/env python3
"""Unit tests for homelab_manager.clients.compose_cli (R1 Phase D).

Covers the H6 allowlist + M1 stderr-scrub hardening that previously lived
inline in services/status.py:get_service_logs. These tests are the contract
that the refactor preserves the security behaviour.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from homelab_manager.clients.compose_cli import MAX_LOG_LINES, ComposeCLI, clamp_lines
from homelab_manager.core.errors import scrub_subprocess_error


class TestScrubSubprocessError:
    def test_includes_type_and_context_when_provided(self):
        exc = subprocess.CalledProcessError(1, [], stderr="leaky-token")
        msg = scrub_subprocess_error(exc, context="logs for grafana")
        assert "CalledProcessError" in msg
        assert "logs for grafana" in msg
        assert "leaky-token" not in msg

    def test_type_only_when_no_context(self):
        msg = scrub_subprocess_error(RuntimeError("don't leak"))
        assert "RuntimeError" in msg
        assert "don't leak" not in msg


# ---------------------------------------------------------------------------
# clamp_lines
# ---------------------------------------------------------------------------


class TestClampLines:
    def test_in_range_returns_as_is(self):
        assert clamp_lines(50) == 50

    def test_zero_clamps_up_to_one(self):
        assert clamp_lines(0) == 1

    def test_negative_clamps_up_to_one(self):
        assert clamp_lines(-100) == 1

    def test_huge_clamps_down_to_max(self):
        assert clamp_lines(10**9) == MAX_LOG_LINES

    def test_string_numeric_coerces(self):
        assert clamp_lines("200") == 200

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError):
            clamp_lines("not-a-number")

    def test_none_raises(self):
        with pytest.raises(TypeError):
            clamp_lines(None)


# ---------------------------------------------------------------------------
# ComposeCLI.run
# ---------------------------------------------------------------------------


class TestComposeCLIRun:
    def test_passes_list_form_with_compose_prefix(self):
        cli = ComposeCLI()
        with patch("homelab_manager.clients.compose_cli.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            cli.run(["ps"])
            assert mock_run.call_args.args[0] == ["docker", "compose", "ps"]

    def test_respects_check_kwarg(self):
        cli = ComposeCLI()
        with patch("homelab_manager.clients.compose_cli.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            cli.run(["up"], check=False)
            assert mock_run.call_args.kwargs["check"] is False


# ---------------------------------------------------------------------------
# ComposeCLI.logs — H6 (allowlist) + M1 (stderr scrub) contract
# ---------------------------------------------------------------------------


def _registry_allowing(name):
    r = MagicMock()
    r.get_service_by_container.side_effect = lambda n: object() if n == name else None
    r.get_service.side_effect = lambda n: object() if n == name else None
    return r


class TestComposeCLILogs:
    def test_no_registry_skips_allowlist(self):
        """Without a registry, ComposeCLI does not gate service_name."""
        cli = ComposeCLI()
        with patch("homelab_manager.clients.compose_cli.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="ok\n", stderr=""
            )
            out = cli.logs("anything")
            assert out == "ok\n"

    def test_unknown_service_rejected(self):
        cli = ComposeCLI(registry=_registry_allowing("grafana"))
        with patch("homelab_manager.clients.compose_cli.subprocess.run") as mock_run:
            out = cli.logs("ghost")
            assert "unknown service 'ghost'" in out
            mock_run.assert_not_called()

    def test_known_service_passes_allowlist(self):
        cli = ComposeCLI(registry=_registry_allowing("grafana"))
        with patch("homelab_manager.clients.compose_cli.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="log\n", stderr=""
            )
            assert cli.logs("grafana") == "log\n"

    def test_negative_lines_clamped_to_one(self):
        cli = ComposeCLI(registry=_registry_allowing("grafana"))
        with patch("homelab_manager.clients.compose_cli.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            cli.logs("grafana", lines=-5)
            cmd = mock_run.call_args.args[0]
            assert cmd[cmd.index("--tail") + 1] == "1"

    def test_huge_lines_capped(self):
        cli = ComposeCLI(registry=_registry_allowing("grafana"))
        with patch("homelab_manager.clients.compose_cli.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            cli.logs("grafana", lines=999_999)
            cmd = mock_run.call_args.args[0]
            assert cmd[cmd.index("--tail") + 1] == str(MAX_LOG_LINES)

    def test_non_integer_lines_rejected(self):
        cli = ComposeCLI(registry=_registry_allowing("grafana"))
        assert "must be a positive integer" in cli.logs("grafana", lines="not-a-number")

    def test_default_tail_is_50(self):
        cli = ComposeCLI(registry=_registry_allowing("grafana"))
        with patch("homelab_manager.clients.compose_cli.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            cli.logs("grafana")
            cmd = mock_run.call_args.args[0]
            assert cmd[cmd.index("--tail") + 1] == "50"

    def test_stderr_never_echoed_on_called_process_error(self):
        cli = ComposeCLI(registry=_registry_allowing("grafana"))
        with patch(
            "homelab_manager.clients.compose_cli.subprocess.run",
            side_effect=subprocess.CalledProcessError(
                returncode=1,
                cmd=[],
                stderr="auth-token=super-secret-leak",
            ),
        ):
            out = cli.logs("grafana")
            assert "super-secret-leak" not in out
            assert "grafana" in out
            assert "CalledProcessError" in out

    def test_generic_exception_returns_type_only(self):
        cli = ComposeCLI(registry=_registry_allowing("grafana"))
        with patch(
            "homelab_manager.clients.compose_cli.subprocess.run",
            side_effect=FileNotFoundError("missing docker"),
        ):
            out = cli.logs("grafana")
            assert "missing docker" not in out
            assert "FileNotFoundError" in out


# ---------------------------------------------------------------------------
# ComposeCLI.scrub_error — M1 stderr-scrub contract for callers
# ---------------------------------------------------------------------------


class TestComposeCLIScrubError:
    def test_scrubs_called_process_error_with_context(self):
        cli = ComposeCLI()
        exc = subprocess.CalledProcessError(
            1, ["docker", "compose", "up"], stderr="auth-token=secret"
        )
        msg = cli.scrub_error(exc, context="deployment failed")
        assert "CalledProcessError" in msg
        assert "deployment failed" in msg
        assert "secret" not in msg

    def test_scrubs_other_exceptions_with_context(self):
        cli = ComposeCLI()
        exc = RuntimeError("don't leak")
        msg = cli.scrub_error(exc, context="process error")
        assert "RuntimeError" in msg
        assert "process error" in msg
        assert "don't leak" not in msg

    def test_scrubs_without_context(self):
        cli = ComposeCLI()
        exc = subprocess.CalledProcessError(1, ["cmd"], stderr="leaked")
        msg = cli.scrub_error(exc)
        assert "CalledProcessError" in msg
        assert "leaked" not in msg
