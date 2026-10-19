#!/usr/bin/env python3
"""Merge gate and issue picker for the autonomous agent loop (stdlib only).

Subcommands (JSON on stdin, JSON on stdout):
  score   {"pr": <gh pr view json>, "issue": <gh issue view json> | null}
          -> {"pillars": {size, impact, value, security}, "reasons": [...], "decision": ...}
  select  {"issues": [<gh issue list json>], "open_prs": [<gh pr list json, all open PRs>]}
          -> {"issue": <number> | null, "skipped": {number: reason}}
  merge-check  {"pr": <gh pr view json + reviewThreads>, "issues": [<gh issue view json>]}
               (needs --repo)
          -> {"ok": bool, "reasons": [...]}: may pr-automerge queue this PR?
  open-threads  {"pr": ...} (needs --repo) -> [open threads with id, bot_only, comments]
  thread-replies  {"pr": ..., "issues": [...], "replies": [<session's replies file>]}
               (needs --repo)
          -> {"ok": bool, "reasons": [...], "actions": [{id, reply, resolve}],
              "skipped": {id: reason}}: what pr-automerge may post and resolve

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
# Subcommands pr-automerge runs on a PR: each needs an allowlisted --repo.
PR_COMMANDS = ("merge-check", "open-threads", "thread-replies")


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


def _bot_only_thread(thread, cfg):
    """True only when the thread has comments and every author is a listed bot. A
    thread with no comments has no author to vouch for it: never the agent's to fix."""
    authors = _thread_authors(thread)
    if not authors:
        return False
    return all(thread_author_kind(a, cfg) == "bot" for a in authors)


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
    # A test file must gain lines; editing or deleting tests only does not count.
    adds_test = any(
        _match(f["path"], cfg["test_paths"]) and (f.get("additions") or 0) > 0
        for f in pr.get("files", [])
    )
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


def merge_check(pr, cfg, issues):
    """Reasons pr-automerge must not queue an auto-merge for this PR ([] means it may).

    issues: the issues the PR closes (None when they could not be loaded). Fails closed:
    a missing field counts against the PR. CI is not checked here: the base ruleset
    holds a queued merge until the required checks pass.
    """
    reasons = []
    if issues is None:
        reasons.append("linked issues not loaded")
    if pr.get("state") != "OPEN":
        reasons.append("not open")
    if pr.get("isDraft") is not False:
        reasons.append("draft")
    if pr.get("isCrossRepository") is not False:
        reasons.append("head branch is in a fork")
    base = cfg.get("base")
    if not base or pr.get("baseRefName") != base:
        reasons.append(f"base is {pr.get('baseRefName')}, must be {base}")
    if any(foreign_activity(pr, issue, cfg) for issue in [None, *(issues or [])]):
        reasons.append("another human authored, commented on or pushed to it")
    if threads_truncated(pr) or "reviewThreads" not in pr:
        reasons.append("review threads not fully loaded")
    if open_threads(pr):
        reasons.append(f"{len(open_threads(pr))} unresolved review thread(s)")
    paths = [f["path"] for f in pr.get("files", [])]
    if not paths or pr.get("changedFiles") != len(paths):
        reasons.append("file list missing or truncated")
    owner_paths = (
        cfg["high_impact_paths"]
        + cfg["sensitive_paths"]
        + cfg["dependency_files"]
        + cfg["merge_block_paths"]
        + cfg.get("repo_merge_block_paths", [])
    )
    blocked = [p for p in paths if _match(p, owner_paths)]
    if blocked:
        reasons.append("owner-review paths: " + ", ".join(blocked[:3]))
    return reasons


def list_open_threads(pr, cfg):
    """Open review threads for the session to answer; it cannot read thread ids itself.
    bot_only marks the threads a replies file may answer."""
    return [
        {
            "id": t.get("id"),
            "path": t.get("path"),
            "line": t.get("line"),
            "bot_only": _bot_only_thread(t, cfg),
            "comments": [
                {
                    "author": (c.get("author") or {}).get("login"),
                    "body": (c.get("body") or "")[:2000],
                }
                for c in (t.get("comments") or {}).get("nodes", [])
            ],
        }
        for t in open_threads(pr)
    ]


def _fixed_after_review(thread, pr):
    """True when the PR head has a commit after every comment of the thread: a fix
    the reply claims must already be pushed. Unknown commits fail closed."""
    commits = [c.get("oid") for c in pr.get("commits", [])]
    if not commits or commits[-1] != pr.get("headRefOid"):
        return False
    seen = [
        (c.get("originalCommit") or {}).get("oid")
        for c in (thread.get("comments") or {}).get("nodes", [])
    ]
    if not seen or any(oid not in commits for oid in seen):
        return False
    return max(commits.index(oid) for oid in seen) < len(commits) - 1


# Posted as the owner, "@claude ..." or "/review" in a reply would start bots or workflows
# with owner trust; bot text the session read could steer it into writing one.
MENTION_OR_COMMAND = re.compile(r"@[A-Za-z0-9]|(^|\n)\s*/[A-Za-z]")


def thread_replies(pr, cfg, issues, replies):
    """Plan which replies pr-automerge posts as the owner and which threads it resolves.

    replies: the session's file, [{"id", "fixed", "reply"}]. Returns (reasons, actions,
    skipped): reasons non-empty means nothing is posted. Only open threads where every
    comment is a listed bot are answered; "fixed" resolves the thread and needs a commit
    pushed after its last comment, else the entry is skipped, so the owner never reads a
    reply about a fix GitHub does not have. A thread named twice, or a reply with an
    @mention or a slash command, is skipped.
    """
    reasons = []
    if issues is None:
        reasons.append("linked issues not loaded")
    if pr.get("state") != "OPEN":
        reasons.append("not open")
    if pr.get("isCrossRepository") is not False:
        reasons.append("head branch is in a fork")
    if any(foreign_activity(pr, issue, cfg) for issue in [None, *(issues or [])]):
        reasons.append("another human authored, commented on or pushed to it")
    if threads_truncated(pr) or "reviewThreads" not in pr:
        reasons.append("review threads not fully loaded")
    if not isinstance(replies, list):
        reasons.append("replies file is not a JSON array")
    if reasons:
        return reasons, [], {}
    by_id = {t.get("id"): t for t in open_threads(pr)}
    actions, skipped = [], {}
    for i, r in enumerate(replies):
        tid = r.get("id") if isinstance(r, dict) else None
        if not isinstance(tid, str) or not re.fullmatch(r"[A-Za-z0-9_=-]+", tid):
            skipped[f"#{i}"] = "no valid thread id"
        elif tid in skipped or any(a["id"] == tid for a in actions):
            skipped[tid] = "named twice"
            actions = [a for a in actions if a["id"] != tid]
        elif not isinstance(r.get("reply"), str) or not r["reply"].strip():
            skipped[tid] = "empty reply"
        elif tid not in by_id:
            skipped[tid] = "not an open thread of this PR"
        elif not _bot_only_thread(by_id[tid], cfg):
            skipped[tid] = "not a bot-only thread, the owner answers it"
        elif MENTION_OR_COMMAND.search(r["reply"]):
            skipped[tid] = "mentions or slash commands would trigger bots as the owner"
        elif r.get("fixed") is True and not _fixed_after_review(by_id[tid], pr):
            skipped[tid] = "fixed, but no commit pushed after the review: push first"
        else:
            reply = re.sub(" ?[\u2013\u2014]", ",", r["reply"][:2000])
            actions.append(
                {"id": tid, "reply": reply, "resolve": r.get("fixed") is True}
            )
    return [], actions, skipped


def _auto_merge_ok(pillars, cfg):
    """auto_merge: true merges only four greens; "no-red" also takes yellow pillars."""
    mode = cfg["auto_merge"]
    if mode is True:
        return all(g == "green" for g in pillars.values())
    if mode == "no-red":
        return "red" not in pillars.values()
    return False


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
    bot_only = bool(threads) and all(_bot_only_thread(t, cfg) for t in threads)
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
    elif _auto_merge_ok(pillars, cfg) and not (
        blocked := merge_check(pr, cfg, [issue])
    ):
        decision = "auto-merge"
    else:
        decision = "owner-review"
        if _auto_merge_ok(pillars, cfg):
            reasons.append("merge check: " + "; ".join(blocked))
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
        return "open PR already claims it"
    return None


def _same_repo(ref, repo):
    """A closing reference counts only for `repo`; refs without repo data count."""
    r = ref.get("repository") or {}
    name, owner = r.get("name"), (r.get("owner") or {}).get("login")
    if not repo or not (name and owner):
        return True
    return f"{owner}/{name}".lower() == repo.lower()


def select(issues, open_prs, cfg, repo=None):
    taken = {
        ref["number"]
        for pr in open_prs
        for ref in pr.get("closingIssuesReferences", [])
        if _same_repo(ref, repo)
    }
    for pr in open_prs:
        m = re.fullmatch(r"(?:fix|agent)/issue-(\d+)", pr.get("headRefName", ""))
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
    ap.add_argument(
        "command",
        choices=["score", "select", "get", *PR_COMMANDS],
    )
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--repo", help="owner/name; merges repos.<repo> over the defaults")
    ap.add_argument("--key", help="for get: config key to print")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.command in PR_COMMANDS and args.repo not in cfg.get("repos", {}):
        ap.error(f"{args.command} needs --repo from the allowlist, got: {args.repo}")
    if args.repo:
        cfg = {**cfg, **cfg.get("repos", {}).get(args.repo, {})}
    if args.command == "get":
        if not args.key:
            ap.error("get needs --key")
        if args.key not in cfg:
            ap.error(f"unknown config key: {args.key}")
        val = cfg[args.key]
        print(json.dumps(val) if isinstance(val, (dict, list, bool)) else val)
        return 0
    data = json.load(sys.stdin)
    if args.command == "score":
        out = score(data["pr"], data.get("issue"), cfg)
    elif args.command == "merge-check":
        reasons = merge_check(data["pr"], cfg, data.get("issues"))
        out = {"ok": not reasons, "reasons": reasons}
    elif args.command == "open-threads":
        out = list_open_threads(data["pr"], cfg)
    elif args.command == "thread-replies":
        reasons, actions, skipped = thread_replies(
            data["pr"], cfg, data.get("issues"), data.get("replies")
        )
        out = {
            "ok": not reasons,
            "reasons": reasons,
            "actions": actions,
            "skipped": skipped,
        }
    else:
        out = select(data.get("issues", []), data.get("open_prs", []), cfg, args.repo)
    json.dump(out, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
