#!/usr/bin/env python3
"""Fail when a public Caddy site block has no auth gate and is not allowlisted.

Guards the Caddyfile before any wildcard hostname reaches Caddy: every public
site block must import the tinyauth snippet (or call forward_auth itself), or
be listed with a reason in config/caddy/public-no-auth.txt. It also requires
the hostless catch-all block to answer 404 so unknown hosts reach no backend.

Usage: caddy-auth-lint.py [Caddyfile] [allowlist]
"""

import sys

CADDYFILE = "config/caddy/Caddyfile"
ALLOWLIST = "config/caddy/public-no-auth.txt"
AUTH_DIRECTIVES = ("import protected", "forward_auth")


def strip_code(text):
    """Blank out comments and quoted/backtick strings, keeping line numbers."""
    out, quote, comment = [], None, False
    for i, ch in enumerate(text):
        if ch == "\n":
            comment = False
            if quote == '"':
                quote = None
            out.append(ch)
        elif comment:
            out.append(" ")
        elif quote:
            if ch == quote and text[i - 1] != "\\":
                quote = None
            out.append(" ")
        elif ch in '`"':
            quote = ch
            out.append(" ")
        elif ch == "#" and (i == 0 or text[i - 1] in " \t\n"):
            comment = True
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def site_blocks(text):
    """Yield (line, addresses, body_lines) for each top-level block."""
    depth, start, addr, body = 0, 0, "", []
    for n, line in enumerate(strip_code(text).split("\n"), 1):
        s = line.strip()
        if depth == 0 and s.endswith("{"):
            start, addr, body = n, s[:-1].strip(), []
        elif depth >= 1:
            body.append(s)
        depth += s.count("{") - s.count("}")
        if depth == 0 and start:
            yield start, addr, body
            start = 0


def host_of(address):
    a = address.split("://", 1)[-1]
    return a.rsplit(":", 1)[0] if ":" in a else a


def is_lan(host):
    return host == "home" or host.endswith(".home")


def load_allowlist(path):
    hosts = {}
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        entry = line.split("#", 1)[0].strip()
        if entry:
            hosts[entry] = n
    return hosts


def lint(caddyfile, allowlist):
    text = open(caddyfile, encoding="utf-8").read()
    allowed = load_allowlist(allowlist)
    errors, public_open, catch_all_ok = [], set(), False
    for line, addr, body in site_blocks(text):
        if not addr or addr.startswith("("):
            continue  # global options or a snippet
        addresses = [a.strip() for a in addr.split(",") if a.strip()]
        if addresses == [":80"]:
            answers_404 = any(
                b.startswith("abort")
                or (b.startswith("respond") and b.split()[-1] == "404")
                for b in body
            )
            catch_all_ok = answers_404 and not any(
                b.startswith("reverse_proxy") for b in body
            )
            continue
        gated = any(b.startswith(AUTH_DIRECTIVES) for b in body)
        for host in (host_of(a) for a in addresses):
            if is_lan(host) or gated:
                continue
            public_open.add(host)
            if host not in allowed:
                errors.append(
                    f"{caddyfile}:{line}: {host} is public with no auth gate; "
                    f"add `import protected` or list it in {allowlist} with a reason"
                )
    for host, n in sorted(allowed.items(), key=lambda kv: kv[1]):
        if host not in public_open:
            errors.append(
                f"{allowlist}:{n}: {host} is not an ungated public block; remove it"
            )
    if not catch_all_ok:
        errors.append(
            f"{caddyfile}: no `:80` catch-all answering 404 (or abort) without a backend"
        )
    return errors


def main():
    caddyfile = sys.argv[1] if len(sys.argv) > 1 else CADDYFILE
    allowlist = sys.argv[2] if len(sys.argv) > 2 else ALLOWLIST
    errors = lint(caddyfile, allowlist)
    for e in errors:
        print(e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
