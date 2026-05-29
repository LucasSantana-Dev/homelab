#!/usr/bin/env python3
"""
Unit tests for homelab_manager.utils.command_sequence (audit-deep H5).

Covers happy path, mid-sequence failure, exception path, cwd inheritance,
and the check=False option.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from homelab_manager.utils.command_sequence import CommandSequence, Step


class TestStep:
    def test_step_defaults(self):
        s = Step(cmd=["echo", "hi"], label="say hi")
        assert s.cmd == ["echo", "hi"]
        assert s.label == "say hi"
        assert s.check is True
        assert s.cwd is None

    def test_step_with_cwd(self, tmp_path):
        s = Step(cmd=["ls"], label="list", cwd=tmp_path)
        assert s.cwd == tmp_path


class TestCommandSequenceRun:
    def test_empty_sequence_succeeds(self):
        result = CommandSequence([]).run()
        assert result == {"success": True}

    def test_single_step_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["true"], returncode=0, stdout="", stderr=""
            )
            result = CommandSequence([Step(["true"], "ok")]).run()
            assert result == {"success": True}
            mock_run.assert_called_once()

    def test_multiple_steps_all_succeed(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["true"], returncode=0, stdout="", stderr=""
            )
            steps = [
                Step(["true"], "step1"),
                Step(["true"], "step2"),
                Step(["true"], "step3"),
            ]
            result = CommandSequence(steps).run()
            assert result == {"success": True}
            assert mock_run.call_count == 3

    def test_first_step_failure_returns_error(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["false"], stderr="boom"
            )
            result = CommandSequence([Step(["false"], "first")]).run()
            assert result["success"] is False
            assert "first failed" in result["error"]
            # Verify error is scrubbed (contains exception type, no raw stderr)
            assert "CalledProcessError" in result["error"]
            assert "boom" not in result["error"]

    def test_mid_sequence_failure_short_circuits(self):
        """A failure on step 2 must prevent step 3 from running."""
        call_count = {"n": 0}

        def fake_run(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise subprocess.CalledProcessError(
                    returncode=1, cmd=args[0], stderr="step2 broke"
                )
            return subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout="", stderr=""
            )

        with patch("subprocess.run", side_effect=fake_run):
            result = CommandSequence(
                [
                    Step(["true"], "alpha"),
                    Step(["false"], "beta"),
                    Step(["true"], "gamma"),
                ]
            ).run()
            assert result["success"] is False
            assert "beta failed" in result["error"]
            # Verify error is scrubbed (contains exception type, no raw stderr)
            assert "CalledProcessError" in result["error"]
            assert "step2 broke" not in result["error"]
            assert call_count["n"] == 2  # gamma never ran

    def test_generic_exception_path(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("no such cmd")):
            result = CommandSequence([Step(["ghost"], "phantom")]).run()
            assert result["success"] is False
            assert "phantom failed" in result["error"]
            # Verify error is scrubbed (contains exception type, no raw message)
            assert "FileNotFoundError" in result["error"]
            assert "no such cmd" not in result["error"]

    def test_sequence_cwd_applied_when_step_cwd_unset(self, tmp_path):
        captured = {}

        def fake_run(*args, **kwargs):
            captured["cwd"] = kwargs.get("cwd")
            return subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout="", stderr=""
            )

        with patch("subprocess.run", side_effect=fake_run):
            CommandSequence([Step(["true"], "x")], cwd=tmp_path).run()
            assert captured["cwd"] == tmp_path

    def test_step_cwd_overrides_sequence_cwd(self, tmp_path):
        seq_cwd = tmp_path / "seq"
        step_cwd = tmp_path / "step"
        seq_cwd.mkdir()
        step_cwd.mkdir()
        captured = {}

        def fake_run(*args, **kwargs):
            captured["cwd"] = kwargs.get("cwd")
            return subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout="", stderr=""
            )

        with patch("subprocess.run", side_effect=fake_run):
            CommandSequence([Step(["true"], "x", cwd=step_cwd)], cwd=seq_cwd).run()
            assert captured["cwd"] == step_cwd

    def test_check_false_does_not_raise(self):
        """When check=False, subprocess.run does NOT raise CalledProcessError
        even on non-zero exit. The sequence treats it as success."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["false"], returncode=1, stdout="", stderr=""
            )
            result = CommandSequence([Step(["false"], "noisy", check=False)]).run()
            # check=False means subprocess.run won't raise -> sequence sees success
            assert result == {"success": True}
            # Verify check kwarg was passed correctly
            assert mock_run.call_args.kwargs["check"] is False

    def test_real_subprocess_success(self):
        """Smoke test against real subprocess (no mock)."""
        result = CommandSequence([Step(["true"], "real-true")]).run()
        assert result == {"success": True}

    def test_real_subprocess_failure(self):
        """Smoke test against real subprocess that actually fails."""
        result = CommandSequence([Step(["false"], "real-false")]).run()
        assert result["success"] is False
        assert "real-false failed" in result["error"]
        # Verify error is scrubbed (contains exception type)
        assert "CalledProcessError" in result["error"]
