"""Tests for scripts/security/caddy-auth-lint.py."""

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "caddy_auth_lint", ROOT / "scripts/security/caddy-auth-lint.py"
)
lint_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint_mod)

CATCH_ALL = ':80 {\n\trespond "unknown host" 404\n}\n'
SNIPPET = "(protected) {\n\tforward_auth 127.0.0.1:3030 {\n\t\turi /x\n\t}\n}\n"
OPEN = "http://open.example.org {\n\treverse_proxy 127.0.0.1:1\n}\n"


def run(tmp_path, caddy, allow=""):
    cf, al = tmp_path / "Caddyfile", tmp_path / "allow.txt"
    cf.write_text(caddy)
    al.write_text(allow)
    return lint_mod.lint(str(cf), str(al))


def open_hosts(errors):
    """Hosts reported as public without a gate (parsed, not substring-matched)."""
    return {
        m.group(1)
        for e in errors
        if (m := re.search(r": (\S+) is public with no auth gate", e))
    }


def test_gated_blocks_and_lan_hosts_pass(tmp_path):
    caddy = (
        SNIPPET
        + "http://a.example.org {\n\timport protected\n\treverse_proxy 127.0.0.1:1\n}\n"
        + "http://b.example.org {\n\tforward_auth 127.0.0.1:3030 {\n\t\turi /z\n\t}\n}\n"
        + "http://svc.home, http://home {\n\treverse_proxy 127.0.0.1:2\n}\n"
        + CATCH_ALL
    )
    assert run(tmp_path, caddy) == []


def test_ungated_public_host_fails(tmp_path):
    errors = run(tmp_path, OPEN + CATCH_ALL)
    assert len(errors) == 1 and open_hosts(errors) == {"open.example.org"}


def test_allowlisted_host_needs_a_reason(tmp_path):
    assert run(tmp_path, OPEN + CATCH_ALL, "open.example.org  # own login\n") == []
    errors = run(tmp_path, OPEN + CATCH_ALL, "open.example.org\n")
    assert len(errors) == 1 and errors[0].endswith(
        "has no reason; add `# <what authenticates>`"
    )


def test_stale_allowlist_entry_fails(tmp_path):
    caddy = SNIPPET + "http://a.example.org {\n\timport protected\n}\n" + CATCH_ALL
    errors = run(tmp_path, caddy, "# comment\na.example.org # now gated\n")
    assert errors == [
        f"{tmp_path}/allow.txt:2: a.example.org is not an ungated public block; remove it"
    ]


@pytest.mark.parametrize(
    "block",
    [
        # snippet whose name only starts with "protected"
        "(protected_evil) {\n\trespond 200\n}\n"
        "http://open.example.org {\n\timport protected_evil\n\treverse_proxy 127.0.0.1:1\n}\n",
        # gate nested in one handle, sibling handle open
        "http://open.example.org {\n\thandle /admin* {\n\t\timport protected\n\t}\n"
        "\thandle {\n\t\treverse_proxy 127.0.0.1:1\n\t}\n}\n",
        # gate behind a matcher
        "http://open.example.org {\n\t@never path /nope\n"
        "\tforward_auth @never 127.0.0.1:3030 {\n\t\turi /x\n\t}\n\treverse_proxy 127.0.0.1:1\n}\n",
        # forward_auth to something that is not tinyauth
        "http://open.example.org {\n\tforward_auth 127.0.0.1:9999 {\n\t\turi /x\n\t}\n"
        "\treverse_proxy 127.0.0.1:1\n}\n",
        # gate text inside a heredoc is payload, not a directive
        "http://open.example.org {\n\trespond @never <<TXT\n\timport protected\n\tTXT 200\n"
        "\treverse_proxy 127.0.0.1:1\n}\n",
    ],
    ids=[
        "prefix-snippet",
        "handle-scoped",
        "matcher-scoped",
        "not-tinyauth",
        "heredoc",
    ],
)
def test_partial_or_fake_gates_do_not_count(tmp_path, block):
    assert open_hosts(run(tmp_path, SNIPPET + block + CATCH_ALL)) == {
        "open.example.org"
    }


@pytest.mark.parametrize(
    "opener",
    ["# see <<END\n", 'header X-Note "<<END"\n', "respond `<<END` 200\n"],
    ids=["comment", "quoted", "backtick"],
)
def test_heredoc_marker_outside_code_hides_nothing(tmp_path, opener):
    caddy = (
        "http://a.example.org {\n\timport protected\n\t"
        + opener
        + "}\n"
        + OPEN
        + "END\n"
        + CATCH_ALL
    )
    assert open_hosts(run(tmp_path, SNIPPET + caddy)) == {"open.example.org"}


def test_every_address_of_a_multiline_block_is_checked(tmp_path):
    caddy = (
        "http://open.example.org,\nhttp://ok.example.org {\n\treverse_proxy 127.0.0.1:1\n}\n"
        + CATCH_ALL
    )
    errors = run(tmp_path, caddy, "ok.example.org # has its own login\n")
    assert open_hosts(errors) == {"open.example.org"}


def test_braces_and_hashes_inside_strings_do_not_break_parsing(tmp_path):
    caddy = (
        "http://page.example.org {\n"
        '\theader Content-Type "text/html; charset=utf-8"\n'
        '\trespond `<style>body{color:#333}</style><a href="#top">{</a>` 200\n'
        "}\n" + OPEN + CATCH_ALL
    )
    errors = run(tmp_path, caddy, "page.example.org # static page\n")
    assert open_hosts(errors) == {"open.example.org"}


@pytest.mark.parametrize(
    "catch_all",
    [
        "",
        ":80 {\n\treverse_proxy 127.0.0.1:1\n}\n",
        ':80 {\n\trespond "hi" 200\n}\n',
        ':80 {\n\t@x path /y\n\trespond @x "no" 404\n\treverse_proxy 127.0.0.1:1\n}\n',
        ':80 {\n\trespond @x "no" 404\n}\n',
        CATCH_ALL + CATCH_ALL,
    ],
    ids=[
        "missing",
        "proxy",
        "200",
        "matcher-404-plus-proxy",
        "matcher-404",
        "duplicate",
    ],
)
def test_catch_all_must_answer_404_to_everything(tmp_path, catch_all):
    errors = run(tmp_path, SNIPPET + catch_all)
    assert len(errors) == 1 and "catch-all" in errors[0]


def test_abort_catch_all_passes(tmp_path):
    assert run(tmp_path, ":80 {\n\tabort\n}\n") == []


def test_real_caddyfile_passes_and_catches_a_removed_gate(tmp_path):
    real = (ROOT / "config/caddy/Caddyfile").read_text()
    allow = (ROOT / "config/caddy/public-no-auth.txt").read_text()
    assert run(tmp_path, real, allow) == []
    start = real.index("http://grafana.")
    gate = real.index("import protected", start)
    mutated = real[:gate] + "# gate removed" + real[gate + len("import protected") :]
    hosts = open_hosts(run(tmp_path, mutated, allow))
    assert len(hosts) == 1 and next(iter(hosts)).startswith("grafana.")
