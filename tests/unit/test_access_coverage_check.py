"""Tests for scripts/security/access-coverage-check.py.

`check()` tests monkeypatch `probe` with canned ProbeResults. `probe` itself
is exercised against a local http.server on 127.0.0.1, so the no-redirect
handler and the Location parsing run for real without touching the internet.
"""

import http.server
import importlib.util
import json
import threading
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


def gated(host="team.cloudflareaccess.com", scheme="https"):
    return mod.ProbeResult(status=302, location_host=host, location_scheme=scheme)


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


def run_wildcard(monkeypatch, tmp_path, sample_result):
    snapshot = write_snapshot(tmp_path, ["grafana.example.org", "*.example.org"])
    allowlist = write_allowlist(tmp_path, "")
    seen = []

    def fake_probe(h, timeout=mod.TIMEOUT):
        seen.append(h)
        return gated() if h == "grafana.example.org" else sample_result

    monkeypatch.setattr(mod, "probe", fake_probe)
    errors, notes = mod.check(str(snapshot), str(allowlist))
    samples = [h for h in seen if h != "grafana.example.org"]
    return errors, notes, samples


def test_wildcard_probes_a_random_subdomain_that_must_be_gated(monkeypatch, tmp_path):
    errors, notes, samples = run_wildcard(monkeypatch, tmp_path, gated())
    assert errors == []
    assert len(samples) == 1
    assert samples[0].startswith("access-check-")
    assert samples[0].endswith(".example.org")
    assert any(
        "*.example.org" in n and "redirects to Cloudflare Access" in n for n in notes
    )


def test_wildcard_with_public_random_subdomain_fails(monkeypatch, tmp_path):
    errors, _, _ = run_wildcard(monkeypatch, tmp_path, plain())
    assert len(errors) == 1
    assert errors[0].startswith("*.example.org: unlisted subdomain")


def test_wildcard_network_error_is_a_failure(monkeypatch, tmp_path):
    errors, _, _ = run_wildcard(monkeypatch, tmp_path, errored())
    assert len(errors) == 1
    assert "network error" in errors[0]


class _Handler(http.server.BaseHTTPRequestHandler):
    routes = {}

    def do_GET(self):
        status, location = self.routes[self.path]
        self.send_response(status)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def local_server(monkeypatch):
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(mod, "SCHEME", "http")
    yield f"127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_probe_does_not_follow_the_access_redirect(local_server):
    _Handler.routes = {
        "/": (302, "https://team.cloudflareaccess.com/cdn-cgi/access/login/x?kid=1")
    }
    result = mod.probe(local_server, timeout=5)
    assert result.error is None
    assert result.status == 302
    assert result.location_host == "team.cloudflareaccess.com"
    assert result.gated


def test_probe_non_https_location_to_access_host_is_not_gated(local_server):
    _Handler.routes = {
        "/": (302, "ftp://team.cloudflareaccess.com/cdn-cgi/access/login/x")
    }
    result = mod.probe(local_server, timeout=5)
    assert result.status == 302
    assert result.location_host == "team.cloudflareaccess.com"
    assert not result.gated


def test_probe_redirect_to_lookalike_host_is_not_gated(local_server):
    _Handler.routes = {"/": (302, "https://cloudflareaccess.com.evil.example/login")}
    result = mod.probe(local_server, timeout=5)
    assert result.status == 302
    assert not result.gated


def test_probe_plain_200_is_not_gated(local_server):
    _Handler.routes = {"/": (200, None)}
    result = mod.probe(local_server, timeout=5)
    assert result.error is None
    assert result.status == 200
    assert not result.gated


def test_probe_connection_refused_is_an_error(monkeypatch):
    monkeypatch.setattr(mod, "SCHEME", "http")
    sock_server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    port = sock_server.server_address[1]
    sock_server.server_close()  # nothing listens on this port now
    result = mod.probe(f"127.0.0.1:{port}", timeout=5)
    assert result.error is not None
    assert not result.gated


def test_hostless_catch_all_rule_is_never_probed(monkeypatch, tmp_path):
    # write_snapshot always appends the hostless 404 rule; probes has no entry
    # for it, so this would KeyError if the loader mistakenly yielded it.
    errors, _ = run(monkeypatch, tmp_path, [], "", {})
    assert errors == []


def test_non_https_redirect_to_access_host_does_not_count_as_gated(
    monkeypatch, tmp_path
):
    """A matching cloudflareaccess.com host behind a non-https Location (ftp://,
    or a scheme urlparse could not determine) is not a real Access redirect."""
    errors, _ = run(
        monkeypatch,
        tmp_path,
        ["open.example.org"],
        "",
        {"open.example.org": gated(scheme="ftp")},
    )
    assert len(errors) == 1
    assert "not allowlisted" in errors[0]


def test_snapshot_with_missing_ingress_fails_closed(monkeypatch, tmp_path):
    path = tmp_path / "edge-snapshot.json"
    path.write_text(json.dumps({"tunnel": "homelab"}))
    allowlist = write_allowlist(tmp_path, "")
    errors, _ = mod.check(str(path), str(allowlist))
    assert len(errors) == 1
    assert "failing closed" in errors[0]


def test_snapshot_with_non_list_ingress_fails_closed(monkeypatch, tmp_path):
    path = tmp_path / "edge-snapshot.json"
    path.write_text(json.dumps({"tunnel": "homelab", "ingress": "not-a-list"}))
    allowlist = write_allowlist(tmp_path, "")
    errors, _ = mod.check(str(path), str(allowlist))
    assert len(errors) == 1
    assert "failing closed" in errors[0]


def test_snapshot_with_non_object_root_fails_closed_without_crashing(
    monkeypatch, tmp_path
):
    """A root that is a list or null has no `.get()`; the fail-closed check
    must catch this before it crashes with an AttributeError."""
    allowlist = write_allowlist(tmp_path, "")
    for root in ("[]", "null", '"just a string"'):
        path = tmp_path / "edge-snapshot.json"
        path.write_text(root)
        errors, _ = mod.check(str(path), str(allowlist))
        assert len(errors) == 1
        assert "failing closed" in errors[0]


def test_snapshot_with_non_object_ingress_rule_fails_closed(monkeypatch, tmp_path):
    """A malformed rule like `null` must not be silently treated as the
    harmless hostless catch-all: that would let a snapshot pass coverage
    with zero probes."""
    path = tmp_path / "edge-snapshot.json"
    path.write_text(json.dumps({"tunnel": "homelab", "ingress": [None]}))
    allowlist = write_allowlist(tmp_path, "")
    errors, _ = mod.check(str(path), str(allowlist))
    assert len(errors) == 1
    assert "non-object rule" in errors[0]
    assert "failing closed" in errors[0]


def test_snapshot_with_empty_ingress_fails_closed(monkeypatch, tmp_path):
    path = tmp_path / "edge-snapshot.json"
    path.write_text(json.dumps({"tunnel": "homelab", "ingress": []}))
    allowlist = write_allowlist(tmp_path, "")
    errors, _ = mod.check(str(path), str(allowlist))
    assert len(errors) == 1
    assert "failing closed" in errors[0]


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
    "status,location_host,location_scheme,expected",
    [
        (302, "team.cloudflareaccess.com", "https", True),
        (303, "team.cloudflareaccess.com", "https", True),
        (301, "team.cloudflareaccess.com", "https", False),  # only 302/303 count
        (302, None, "https", False),  # no Location header
        (200, None, None, False),
        (None, None, None, False),  # error case handled separately, gated must be False
        (302, "team.cloudflareaccess.com", "ftp", False),  # non-https Location
        (302, "team.cloudflareaccess.com", None, False),  # scheme not captured
    ],
)
def test_probe_result_gated_property(status, location_host, location_scheme, expected):
    result = mod.ProbeResult(
        status=status, location_host=location_host, location_scheme=location_scheme
    )
    assert result.gated is expected
