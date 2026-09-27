"""Tests for scripts/security/caddy-auth-lint.py."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "caddy_auth_lint", ROOT / "scripts/security/caddy-auth-lint.py"
)
lint_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint_mod)

CATCH_ALL = ':80 {\n\trespond "unknown host" 404\n}\n'
SNIPPET = (
    "(protected) {\n\tforward_auth 127.0.0.1:3030 {\n\t\turi /api/auth/caddy\n\t}\n}\n"
)


def run(tmp_path, caddy, allow=""):
    cf, al = tmp_path / "Caddyfile", tmp_path / "allow.txt"
    cf.write_text(caddy)
    al.write_text(allow)
    return lint_mod.lint(str(cf), str(al))


def test_gated_blocks_and_lan_hosts_pass(tmp_path):
    caddy = (
        SNIPPET
        + "http://a.example.org {\n\timport protected\n\treverse_proxy 127.0.0.1:1\n}\n"
        + "http://b.example.org {\n\t@x path /y\n\tforward_auth @x 127.0.0.1:3030 {\n\t\turi /z\n\t}\n}\n"
        + "http://svc.home, http://home {\n\treverse_proxy 127.0.0.1:2\n}\n"
        + CATCH_ALL
    )
    assert run(tmp_path, caddy) == []


def test_ungated_public_host_fails(tmp_path):
    caddy = "http://open.example.org {\n\treverse_proxy 127.0.0.1:1\n}\n" + CATCH_ALL
    errors = run(tmp_path, caddy)
    assert (
        len(errors) == 1 and "open.example.org is public with no auth gate" in errors[0]
    )


def test_allowlisted_host_passes(tmp_path):
    caddy = "http://open.example.org {\n\treverse_proxy 127.0.0.1:1\n}\n" + CATCH_ALL
    assert run(tmp_path, caddy, "open.example.org  # own login\n") == []


def test_one_ungated_address_in_a_shared_block_fails(tmp_path):
    caddy = (
        "http://x.home, http://open.example.org {\n\treverse_proxy 127.0.0.1:1\n}\n"
        + CATCH_ALL
    )
    assert any("open.example.org" in e for e in run(tmp_path, caddy))


def test_stale_allowlist_entry_fails(tmp_path):
    caddy = SNIPPET + "http://a.example.org {\n\timport protected\n}\n" + CATCH_ALL
    errors = run(tmp_path, caddy, "# comment\na.example.org # now gated\n")
    assert (
        len(errors) == 1
        and "allow.txt:2: a.example.org is not an ungated public block" in errors[0]
    )


@pytest.mark.parametrize(
    "catch_all",
    ["", ":80 {\n\treverse_proxy 127.0.0.1:1\n}\n", ':80 {\n\trespond "hi" 200\n}\n'],
)
def test_catch_all_must_answer_404_without_backend(tmp_path, catch_all):
    errors = run(tmp_path, SNIPPET + catch_all)
    assert any("catch-all" in e for e in errors)


def test_abort_catch_all_passes(tmp_path):
    assert run(tmp_path, ":80 {\n\tabort\n}\n") == []


def test_braces_and_hashes_inside_strings_do_not_break_parsing(tmp_path):
    caddy = (
        "http://page.example.org {\n"
        '\theader Content-Type "text/html; charset=utf-8"\n'
        '\trespond `<style>body{color:#333}</style><a href="#top">{</a>` 200\n'
        "}\n"
        "http://open.example.org {\n\treverse_proxy 127.0.0.1:1\n}\n" + CATCH_ALL
    )
    errors = run(tmp_path, caddy, "page.example.org # static page\n")
    assert len(errors) == 1 and "open.example.org" in errors[0]


def test_real_caddyfile_passes_and_catches_a_removed_gate(tmp_path):
    real = (ROOT / "config/caddy/Caddyfile").read_text()
    allow = (ROOT / "config/caddy/public-no-auth.txt").read_text()
    assert run(tmp_path, real, allow) == []
    block = "http://grafana."
    start = real.index(block)
    gate = real.index("import protected", start)
    mutated = real[:gate] + "# gate removed" + real[gate + len("import protected") :]
    errors = run(tmp_path, mutated, allow)
    assert len(errors) == 1 and "grafana." in errors[0]
