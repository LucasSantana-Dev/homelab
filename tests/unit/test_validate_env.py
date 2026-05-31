"""Tests for scripts/security/validate-env.sh compose-completeness gate.

The gate derives required variables from ${VAR} references in compose/*.yml and
fails the deploy if any (without a :-default) is missing from .env. This is the
guard that would have caught the kopia backup running credential-less.
"""

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "security" / "validate-env.sh"

# Curated REQUIRED_VARS the script checks independently of compose — set them so
# the compose-completeness assertions are isolated. None contain placeholder
# substrings (YOUR_, example, changeme, ...).
_BASE_ENV = (
    "TAILSCALE_IP=100.64.1.1\nDOMAIN=homelab.lan\nPUID=1000\nPGID=1000\nTIMEZONE=UTC\n"
)


def _run(env_file: Path, compose_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            **os.environ,
            "HOMELAB_ENV_FILE": str(env_file),
            "HOMELAB_COMPOSE_DIR": str(compose_dir),
        },
        capture_output=True,
        text=True,
    )


def _compose(compose_dir: Path, body: str) -> None:
    compose_dir.mkdir(exist_ok=True)
    (compose_dir / "svc.yml").write_text(body)


def test_gate_fails_on_missing_compose_required_var(tmp_path):
    env = tmp_path / ".env"
    env.write_text(_BASE_ENV)
    _compose(
        tmp_path / "compose",
        "services:\n  s:\n    environment:\n      - SECRET=${ACME_SECRET}\n",
    )
    result = _run(env, tmp_path / "compose")
    assert result.returncode == 1, result.stdout
    assert "ACME_SECRET" in result.stdout
    assert "COMPOSE-REQUIRED" in result.stdout


def test_gate_passes_when_compose_var_present(tmp_path):
    env = tmp_path / ".env"
    env.write_text(_BASE_ENV + "ACME_SECRET=s3cret-value\n")
    _compose(
        tmp_path / "compose",
        "services:\n  s:\n    environment:\n      - SECRET=${ACME_SECRET}\n",
    )
    result = _run(env, tmp_path / "compose")
    assert result.returncode == 0, result.stdout


def test_var_with_default_is_not_required(tmp_path):
    env = tmp_path / ".env"
    env.write_text(_BASE_ENV)
    _compose(
        tmp_path / "compose",
        "services:\n  s:\n    ports:\n      - ${ACME_PORT:-8080}:80\n",
    )
    result = _run(env, tmp_path / "compose")
    assert result.returncode == 0, result.stdout


def test_placeholder_value_fails(tmp_path):
    env = tmp_path / ".env"
    env.write_text(_BASE_ENV + "ACME_SECRET=CHANGE_ME\n")
    _compose(
        tmp_path / "compose",
        "services:\n  s:\n    environment:\n      - SECRET=${ACME_SECRET}\n",
    )
    result = _run(env, tmp_path / "compose")
    assert result.returncode == 1, result.stdout
    assert "placeholder" in result.stdout.lower()


def test_comment_referenced_var_not_required(tmp_path):
    """A ${VAR} that appears only in a YAML comment must NOT become required."""
    env = tmp_path / ".env"
    env.write_text(_BASE_ENV)
    _compose(
        tmp_path / "compose",
        "services:\n  s:\n    # ${COMMENTED_ONLY} is documented here, not used\n    image: nginx\n",
    )
    result = _run(env, tmp_path / "compose")
    assert result.returncode == 0, result.stdout
    assert "COMMENTED_ONLY" not in result.stdout
