"""Tests for scripts/security/access-coverage-check.py.

The HTTP layer (`probe`) is mocked throughout: no test makes a real network
call. `probe` is monkeypatched on the loaded module so `check()` exercises its
real allowlist/mismatch logic against canned ProbeResults.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "access_coverage_check", ROOT / "scripts/security/access-coverage-check.py"
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def write_snapshot(tmp_path, hostnames):
    ingress = [
        {"hostname": h, "service": "http://host.docker.internal:80"} for h in hostnames
    ]
    ingress.append({"service": "http_status:404"})  # the real catch-all has no hostname
    path = tmp_path / "edge-snapshot.json"
    path.write_text(json.dumps({"tunnel": "homelab", "ingress": ingress, "dns": {}}))
    return path


def write_allowlist(tmp_path, text):
    path = tmp_path / "access-allowlist.txt"
    path.write_text(text)
    return path


def gated(host="team.cloudflareaccess.com"):
    return mod.ProbeResult(status=302, location_host=host)


def plain(status=200):
    return mod.ProbeResult(status=status)


def errored(msg="timed out"):
    return mod.ProbeResult(error=msg)


def run(monkeypatch, tmp_path, hostnames, allow_text, probes):
    snapshot = write_snapshot(tmp_path, hostnames)
    allowlist = write_allowlist(tmp_path, allow_text)
    monkeypatch.setattr(mod, "probe", lambda h, timeout=mod.TIMEOUT: probes[h])
    return mod.check(str(snapshot), str(allowlist))


def test_gated_host_not_allowlisted_passes(monkeypatch, tmp_path):
    errors, notes = run(
        monkeypatch,
        tmp_path,
        ["grafana.example.org"],
        "",
        {"grafana.example.org": gated()},
    )
    assert errors == []


def test_public_host_not_allowlisted_fails(monkeypatch, tmp_path):
    errors, _ = run(
        monkeypatch, tmp_path, ["open.example.org"], "", {"open.example.org": plain()}
    )
    assert len(errors) == 1
    assert errors[0].partition(":")[0] == "open.example.org"
    assert "not allowlisted" in errors[0]


def test_allowlisted_public_host_passes(monkeypatch, tmp_path):
    errors, _ = run(
        monkeypatch,
        tmp_path,
        ["rclone.example.org"],
        "rclone.example.org  # Access bypass app\n",
        {"rclone.example.org": plain()},
    )
    assert errors == []


def test_allowlisted_host_needs_a_reason(monkeypatch, tmp_path):
    errors, _ = run(
        monkeypatch,
        tmp_path,
        ["rclone.example.org"],
        "rclone.example.org\n",
        {"rclone.example.org": plain()},
    )
    assert any("has no reason" in e for e in errors)


def test_allowlisted_host_that_is_actually_gated_fails(monkeypatch, tmp_path):
    """Allowlist says public, but the edge now redirects to Access: stale entry."""
    errors, _ = run(
        monkeypatch,
        tmp_path,
        ["grafana.example.org"],
        "grafana.example.org  # was public\n",
        {"grafana.example.org": gated()},
    )
    assert len(errors) == 1
    assert "stale" in errors[0]


def test_network_error_fails_even_when_allowlisted(monkeypatch, tmp_path):
    errors, _ = run(
        monkeypatch,
        tmp_path,
        ["flaky.example.org"],
        "flaky.example.org  # normally public\n",
        {"flaky.example.org": errored("Name or service not known")},
    )
    assert len(errors) == 1
    assert "network error" in errors[0]


def test_network_error_fails_when_not_allowlisted(monkeypatch, tmp_path):
    errors, _ = run(
        monkeypatch,
        tmp_path,
        ["flaky.example.org"],
        "",
        {"flaky.example.org": errored()},
    )
    assert len(errors) == 1
    assert "network error" in errors[0]


def test_stale_allowlist_entry_not_in_snapshot_fails(monkeypatch, tmp_path):
    errors, _ = run(
        monkeypatch,
        tmp_path,
        ["grafana.example.org"],
        "gone.example.org  # used to exist\n",
        {"grafana.example.org": gated()},
    )
    assert any("is not in" in e and e.split()[1] == "gone.example.org" for e in errors)


def test_wildcard_ingress_entry_is_skipped_and_noted(monkeypatch, tmp_path):
    errors, notes = run(
        monkeypatch,
        tmp_path,
        ["grafana.example.org", "*.example.org"],
        "",
        {"grafana.example.org": gated()},
    )
    assert errors == []
    assert any("*.example.org" in n and "skipping wildcard" in n for n in notes)


def test_hostless_catch_all_rule_is_never_probed(monkeypatch, tmp_path):
    # write_snapshot always appends the hostless 404 rule; probes has no entry
    # for it, so this would KeyError if the loader mistakenly yielded it.
    errors, _ = run(monkeypatch, tmp_path, [], "", {})
    assert errors == []


def test_redirect_to_a_lookalike_domain_does_not_count_as_gated(monkeypatch, tmp_path):
    """`notcloudflareaccess.com` must not satisfy the *.cloudflareaccess.com suffix."""
    errors, _ = run(
        monkeypatch,
        tmp_path,
        ["open.example.org"],
        "",
        {"open.example.org": gated(host="notcloudflareaccess.com")},
    )
    assert len(errors) == 1
    assert "not allowlisted" in errors[0]


def test_real_snapshot_and_allowlist_are_internally_consistent(monkeypatch, tmp_path):
    """Every real allowlist entry is a real ingress hostname (structure only, no network)."""
    snapshot = json.loads((ROOT / "config/cloudflared/edge-snapshot.json").read_text())
    hosts = {r["hostname"] for r in snapshot["ingress"] if r.get("hostname")}
    errors = []
    allowed = mod.load_allowlist(
        str(ROOT / "config/cloudflared/access-allowlist.txt"), errors
    )
    assert errors == []  # every entry has a reason
    assert set(allowed) <= hosts


@pytest.mark.parametrize(
    "status,location_host,expected",
    [
        (302, "team.cloudflareaccess.com", True),
        (303, "team.cloudflareaccess.com", True),
        (301, "team.cloudflareaccess.com", False),  # only 302/303 count
        (302, None, False),  # no Location header
        (200, None, False),
        (None, None, False),  # error case handled separately, but gated must be False
    ],
)
def test_probe_result_gated_property(status, location_host, expected):
    result = mod.ProbeResult(status=status, location_host=location_host)
    assert result.gated is expected
