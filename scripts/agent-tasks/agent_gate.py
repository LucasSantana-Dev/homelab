#!/usr/bin/env python3
"""Merge gate and issue picker for the autonomous agent loop (stdlib only).

Subcommands (JSON on stdin, JSON on stdout):
  score   {"pr": <gh pr view json>, "issue": <gh issue view json> | null}
          -> {"pillars": {size, impact, value, security}, "reasons": [...], "decision": ...}
  select  {"issues": [<gh issue list json>], "open_prs": [<gh pr list json>]}
          -> {"issue": <number> | null, "skipped": {number: reason}}

Grades are green < yellow < red. Mechanical signals only: diff size, paths,
labels, checks, review threads (pr.reviewThreads, the GraphQL connection).
Thresholds live in config/agent-box/agent-gate.json.
"""

import argparse
import json
import re
import sys
from fnmatch import fnmatch
from pathlib import Path

DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[2] / "config" / "agent-box" / "agent-gate.json"
)
RANK = {"green": 0, "yellow": 1, "red": 2}


def load_config(path):
    return json.loads(Path(path).read_text())


def _match(path, patterns):
    p = path.lower()
    return any(fnmatch(p, pat.lower()) for pat in patterns)


def _labels(obj):
    return {lbl["name"] for lbl in (obj or {}).get("labels", [])}


def is_human_foreign(login, cfg):
    # A missing login is a deleted ("ghost") account: fail closed, treat as human.
    if not login:
        return True
    if login == cfg["owner"]:
        return False
    if login.endswith("[bot]") or login.startswith("app/"):
        return False
    return login not in cfg["bots"]


def _threads(pr):
    return (pr.get("reviewThreads") or {}).get("nodes", [])


def _thread_authors(thread):
    return [
        c.get("author") or {} for c in (thread.get("comments") or {}).get("nodes", [])
    ]


def thread_author_kind(author, cfg):
    """'bot', 'app', 'owner' or 'human'. Thread authors carry __typename, so only a
    real GitHub App counts as a bot: a user account named like a bot is a human. An
    App outside cfg["bots"] is not human, but its threads are not the agent's to fix."""
    if author.get("__typename") == "Bot":
        login = author.get("login") or ""
        listed = login in cfg["bots"] or login.removesuffix("[bot]") in cfg["bots"]
        return "bot" if listed else "app"
    login = author.get("login")
    return "owner" if login and login == cfg["owner"] else "human"


def threads_truncated(pr):
    """A page we did not fetch could hold a human reply: callers must fail closed."""
    conn = pr.get("reviewThreads") or {}
    if (conn.get("pageInfo") or {}).get("hasNextPage"):
        return True
    for t in conn.get("nodes", []):
        comments = t.get("comments") or {}
        if comments.get("totalCount", 0) > len(comments.get("nodes", [])):
            return True
    return False


def open_threads(pr):
    return [t for t in _threads(pr) if not t.get("isResolved")]


def foreign_activity(pr, issue, cfg):
    """Hard rule: never act on a PR (or its issue) another human authored,
    commented on or pushed to."""
    if (pr.get("author") or {}).get("login") != cfg["owner"]:
        return True
    if issue and is_human_foreign((issue.get("author") or {}).get("login"), cfg):
        return True
    items = (
        pr.get("comments", [])
        + pr.get("reviews", [])
        + (issue or {}).get("comments", [])
    )
    logins = [(item.get("author") or {}).get("login") for item in items]
    # Commit authors: a human push without a comment must halt too.
    logins += [
        a.get("login") for c in pr.get("commits", []) for a in c.get("authors", [])
    ]
    if any(
        thread_author_kind(a, cfg) == "human"
        for t in _threads(pr)
        for a in _thread_authors(t)
    ):
        return True
    return any(is_human_foreign(login, cfg) for login in logins)


def checks_state(pr):
    """Return 'failing', 'pending' or 'passing' from statusCheckRollup.

    No checks at all counts as pending: a fresh PR must never grade as passing.
    """
    rollup = pr.get("statusCheckRollup") or []
    pending = not rollup
    for c in rollup:
        result = (c.get("conclusion") or c.get("state") or "").upper()
        status = (c.get("status") or "").upper()
        if result in (
            "FAILURE",
            "ERROR",
            "TIMED_OUT",
            "CANCELLED",
            "ACTION_REQUIRED",
            "STARTUP_FAILURE",
        ):
            return "failing"
        if status in ("QUEUED", "IN_PROGRESS", "PENDING", "WAITING") or result in (
            "PENDING",
            "EXPECTED",
        ):
            pending = True
    return "pending" if pending else "passing"


def grade_size(pr, cfg):
    s = cfg["size"]
    lines = pr.get("additions", 0) + pr.get("deletions", 0)
    files = len(pr.get("files", []))
    why = f"{lines} lines, {files} files"
    if lines <= s["green_lines"] and files <= s["green_files"]:
        return "green", why
    if lines <= s["yellow_lines"] and files <= s["yellow_files"]:
        return "yellow", why
    return "red", why + " (split it)"


def _module(path):
    parts = path.split("/")
    return (
        "/".join(parts[:2]) if len(parts) > 2 else parts[0] if len(parts) > 1 else "."
    )


def grade_impact(pr, cfg):
    paths = [f["path"] for f in pr.get("files", [])]
    high = [p for p in paths if _match(p, cfg["high_impact_paths"])]
    if high:
        return "red", "high-impact paths: " + ", ".join(high[:3])
    modules = {_module(p) for p in paths}
    if len(modules) > cfg["max_modules"]:
        return "red", f"touches {len(modules)} modules"
    if paths and all(_match(p, cfg["low_impact_paths"]) for p in paths):
        return "green", "docs/tests/lint only"
    return "yellow", "runtime code"


def grade_value(pr, issue, cfg):
    if not pr.get("closingIssuesReferences") or not issue:
        return "red", "no linked issue"
    if (issue.get("author") or {}).get("login") != cfg["owner"]:
        return "red", "issue not authored by owner"
    labels = _labels(issue)
    if "ready-for-agent" not in labels:
        return "red", "issue not ready-for-agent"
    adds_test = any(_match(f["path"], cfg["test_paths"]) for f in pr.get("files", []))
    if labels & set(cfg["value_green_labels"]) and adds_test:
        return "green", "P1/bug with test"
    return "yellow", "linked issue" + ("" if adds_test else ", no new test")


def grade_security(pr, cfg, checks):
    paths = [f["path"] for f in pr.get("files", [])]
    hits = [p for p in paths if _match(p, cfg["sensitive_paths"])]
    if hits:
        return "red", "sensitive paths: " + ", ".join(hits[:3])
    if checks == "failing":
        return "yellow", "failing checks"
    if checks == "pending":
        return "yellow", "checks pending"
    if any(_match(p, cfg["dependency_files"]) for p in paths):
        return "yellow", "dependency manifest changed"
    return "green", "clean"


def score(pr, issue, cfg):
    if foreign_activity(pr, issue, cfg):
        return {
            "decision": "halt",
            "pillars": {},
            "reasons": ["another human authored or commented"],
        }
    if threads_truncated(pr):
        return {
            "decision": "halt",
            "pillars": {},
            "reasons": ["too many review threads or replies to check for humans"],
        }
    checks = checks_state(pr)
    graded = {
        "size": grade_size(pr, cfg),
        "impact": grade_impact(pr, cfg),
        "value": grade_value(pr, issue, cfg),
        "security": grade_security(pr, cfg, checks),
    }
    pillars = {k: g for k, (g, _) in graded.items()}
    reasons = [f"{k}: {why}" for k, (_, why) in graded.items()]
    threads = open_threads(pr)
    # Bot-only threads are the agent's to fix; one the owner joined waits for the owner.
    bot_only = bool(threads) and all(
        _thread_authors(t)
        and all(thread_author_kind(a, cfg) == "bot" for a in _thread_authors(t))
        for t in threads
    )
    if threads:
        reasons.append(
            f"review: {len(threads)} unresolved thread(s)"
            + ("" if bot_only else ", owner involved")
        )
    fix = None
    # Pillars first: a sensitive, oversized or pointless PR never gets an autofix run.
    if pillars["value"] == "red":
        decision = "close"
    elif "red" in (pillars["security"], pillars["impact"]):
        decision = "needs-human"
    elif pillars["size"] == "red":
        decision = "split"
    elif checks == "failing":
        decision, fix = "autofix", "ci"
    elif checks == "pending":
        decision = "wait"
    elif bot_only:
        decision, fix = "autofix", "threads"
    elif threads:
        decision = "owner-review"
    elif all(g == "green" for g in pillars.values()) and cfg["auto_merge"] is True:
        decision = "auto-merge"
    else:
        decision = "owner-review"
    out = {
        "decision": decision,
        "pillars": pillars,
        "reasons": reasons,
        "checks": checks,
    }
    if fix:
        out["fix"] = fix
    return out


def _issue_skip_reason(issue, taken, cfg):
    labels = _labels(issue)
    if (issue.get("author") or {}).get("login") != cfg["owner"]:
        return "not owner-authored"
    if "ready-for-agent" not in labels:
        return "not ready-for-agent"
    if not labels & set(cfg["required_effort"]):
        return "effort not allowed"
    if labels & set(cfg["issue_skip_labels"]):
        return "skip label"
    text = (issue.get("title", "") + " " + " ".join(labels)).lower()
    word = next((w for w in cfg["issue_skip_words"] if w in text), None)
    if word:
        return f"sensitive topic: {word}"
    if any(
        is_human_foreign((c.get("author") or {}).get("login"), cfg)
        for c in issue.get("comments", [])
    ):
        return "foreign comment"
    if issue["number"] in taken:
        return "agent PR already open"
    return None


def select(issues, open_prs, cfg):
    taken = {
        ref["number"]
        for pr in open_prs
        for ref in pr.get("closingIssuesReferences", [])
    }
    for pr in open_prs:
        m = re.fullmatch(r"agent/issue-(\d+)", pr.get("headRefName", ""))
        if m:
            taken.add(int(m.group(1)))
    skipped, eligible = {}, []
    for issue in issues:
        reason = _issue_skip_reason(issue, taken, cfg)
        if reason:
            skipped[str(issue["number"])] = reason
        else:
            eligible.append(issue)
    first = set(cfg["rank_first"])
    eligible.sort(
        key=lambda i: (
            not (_labels(i) & first),
            "P1" not in _labels(i),
            i.get("createdAt", ""),
        )
    )
    return {"issue": eligible[0]["number"] if eligible else None, "skipped": skipped}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["score", "select", "get"])
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--repo", help="owner/name; merges repos.<repo> over the defaults")
    ap.add_argument("--key", help="for get: config key to print")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.repo:
        cfg = {**cfg, **cfg.get("repos", {}).get(args.repo, {})}
    if args.command == "get":
        print(
            cfg[args.key]
            if not isinstance(cfg[args.key], (dict, list, bool))
            else json.dumps(cfg[args.key])
        )
        return 0
    data = json.load(sys.stdin)
    if args.command == "score":
        out = score(data["pr"], data.get("issue"), cfg)
    else:
        out = select(data.get("issues", []), data.get("open_prs", []), cfg)
    json.dump(out, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
