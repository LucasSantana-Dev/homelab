#!/usr/bin/env python3
"""Fail when a public Caddy site block has no auth gate and is not allowlisted.

Guards the Caddyfile before any wildcard hostname reaches Caddy: every public
site block must gate ALL of its requests through tinyauth, or be listed with a
reason in config/caddy/public-no-auth.txt. It also requires exactly one
hostless `:80` catch-all that answers 404 (or aborts) to every request.

Rules lean to failing closed: a gate only counts when it is a top-level
`import protected` or an unmatched `forward_auth` to tinyauth. A gate scoped by
a matcher or nested in handle/route leaves other paths open, so such a block
must be allowlisted and explain itself.

Usage: caddy-auth-lint.py [Caddyfile] [allowlist]
"""

import re
import sys

CADDYFILE = "config/caddy/Caddyfile"
ALLOWLIST = "config/caddy/public-no-auth.txt"
TINYAUTH = "127.0.0.1:3030"
HEREDOC = re.compile(r"<<([A-Za-z_][A-Za-z0-9_]*)\s*$")


def strip_heredocs(text):
    """Blank heredoc bodies; the closing line keeps what follows the marker."""
    lines, marker = text.split("\n"), None
    for n, line in enumerate(lines):
        if marker:
            first, _, rest = line.strip().partition(" ")
            if first == marker:
                lines[n], marker = " " + rest, None
            else:
                lines[n] = ""
            continue
        m = HEREDOC.search(line)
        if m:
            marker, lines[n] = m.group(1), line[: m.start()]
    return "\n".join(lines)


def strip_code(text):
    """Blank out comments, quoted/backtick strings and heredocs, keeping lines."""
    out, quote, comment = [], None, False
    text = strip_heredocs(text)
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
    """Yield (line, addresses, body) per top-level block; body is (depth, tokens)."""
    depth, start, pending, body = 0, 0, [], []
    for n, line in enumerate(strip_code(text).split("\n"), 1):
        s = line.strip()
        if depth == 0:
            if not s:
                continue
            pending.append(s)
            if s.endswith("{"):
                start, body = n, []
                addr = " ".join(pending)[:-1]
                pending = []
        elif s and s != "}":
            body.append((depth, s.rstrip("{").split()))
        depth += s.count("{") - s.count("}")
        if depth == 0 and start:
            yield start, addr.strip(), body
            start = 0


def host_of(address):
    a = address.split("://", 1)[-1]
    return a.rsplit(":", 1)[0] if ":" in a else a


def is_lan(host):
    return host == "home" or host.endswith(".home")


def is_matcher(token):
    return token.startswith(("@", "/", "*"))


def gates_everything(body):
    """True when a top-level, unmatched directive sends every request to tinyauth."""
    for depth, tok in body:
        if depth != 1 or not tok:
            continue
        if tok == ["import", "protected"]:
            return True
        if tok[0] == "forward_auth" and len(tok) > 1:
            if not is_matcher(tok[1]) and tok[1] == TINYAUTH:
                return True
    return False


def answers_404_only(body):
    """Every directive in the catch-all is an unmatched `respond ... 404` or abort."""
    if not body:
        return False
    for depth, tok in body:
        if depth != 1:
            return False
        if tok == ["abort"]:
            continue
        if tok[0] == "respond" and tok[-1] == "404" and not is_matcher(tok[1]):
            continue
        return False
    return True


def load_allowlist(path, errors):
    hosts = {}
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        entry, _, reason = line.partition("#")
        entry = entry.strip()
        if not entry:
            continue
        if not reason.strip():
            errors.append(
                f"{path}:{n}: {entry} has no reason; add `# <what authenticates>`"
            )
        hosts[entry] = n
    return hosts


def lint(caddyfile, allowlist):
    text = open(caddyfile, encoding="utf-8").read()
    errors = []
    allowed = load_allowlist(allowlist, errors)
    public_open, catch_alls = set(), []
    for line, addr, body in site_blocks(text):
        if not addr or addr.startswith("("):
            continue  # global options or a snippet
        addresses = [a.strip() for a in addr.split(",") if a.strip()]
        if addresses == [":80"]:
            catch_alls.append((line, answers_404_only(body)))
            continue
        gated = gates_everything(body)
        for host in (host_of(a) for a in addresses):
            if is_lan(host) or gated:
                continue
            public_open.add(host)
            if host not in allowed:
                errors.append(
                    f"{caddyfile}:{line}: {host} is public with no auth gate on every request; "
                    f"add a top-level `import protected` or list it in {allowlist} with a reason"
                )
    for host, n in sorted(allowed.items(), key=lambda kv: kv[1]):
        if host not in public_open:
            errors.append(
                f"{allowlist}:{n}: {host} is not an ungated public block; remove it"
            )
    if len(catch_alls) != 1 or not catch_alls[0][1]:
        errors.append(
            f"{caddyfile}: need exactly one `:80` catch-all whose every directive is "
            f"an unmatched `respond ... 404` or `abort` (found {len(catch_alls)})"
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
