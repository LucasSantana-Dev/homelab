"""Tests for scripts/agent-tasks/agent_gate.py: the 4-pillar merge gate
(size, impact, value, security) and the issue picker for the agent loop."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "agent-tasks" / "agent_gate.py"
CONFIG = REPO / "config" / "agent-box" / "agent-gate.json"

_spec = importlib.util.spec_from_file_location("agent_gate", SCRIPT)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

OWNER = "LucasSantana-Dev"
SCRATCH = "/tmp/agent-run.Ab3dEf9h"


@pytest.fixture
def cfg():
    # Pin Phase 1 so scoring tests do not follow the live auto_merge flag.
    c = gate.load_config(CONFIG)
    c = {**c, **c["repos"]["LucasSantana-Dev/Lucky"]}
    c["auto_merge"] = False
    return c


def make_pr(
    files,
    lines=None,
    author=OWNER,
    comments=(),
    reviews=(),
    checks="SUCCESS",
    closes=(1,),
):
    lines = lines if lines is not None else 10 * len(files)
    return {
        "author": {"login": author},
        "files": [{"path": p, "additions": 10, "deletions": 0} for p in files],
        "additions": lines,
        "deletions": 0,
        "closingIssuesReferences": [{"number": n} for n in closes],
        "statusCheckRollup": [{"conclusion": checks, "status": "COMPLETED"}],
        "comments": [{"author": {"login": c}} for c in comments],
        "reviews": [{"author": {"login": r}} for r in reviews],
        "state": "OPEN",
        "isDraft": False,
        "isCrossRepository": False,
        "baseRefName": "main",
        "changedFiles": len(files),
        "reviewThreads": {"pageInfo": {"hasNextPage": False}, "nodes": []},
    }


def make_issue(
    labels=("ready-for-agent", "cat:bug", "effort:s"),
    author=OWNER,
    number=1,
    title="fix: thing",
    comments=(),
    created="2026-10-01T00:00:00Z",
):
    return {
        "number": number,
        "title": title,
        "author": {"login": author},
        "labels": [{"name": n} for n in labels],
        "comments": [{"author": {"login": c}} for c in comments],
        "createdAt": created,
    }


# --- pillar: size ---------------------------------------------------------


@pytest.mark.parametrize(
    "lines,files,expected",
    [
        (150, 5, "green"),
        (151, 5, "yellow"),
        (400, 12, "yellow"),
        (401, 3, "red"),
        (10, 13, "red"),
    ],
)
def test_size_grades(cfg, lines, files, expected):
    pr = make_pr([f"docs/f{i}.md" for i in range(files)], lines=lines)
    assert gate.grade_size(pr, cfg)[0] == expected


# --- pillar: impact -------------------------------------------------------


@pytest.mark.parametrize(
    "files,expected",
    [
        (["README.md", "packages/bot/src/foo.test.ts"], "green"),
        (["packages/bot/src/commands/play.ts"], "yellow"),
        ([".github/workflows/ci.yml"], "red"),
        (["packages/db/prisma/migrations/001/migration.sql"], "red"),
        (["a/x/1.ts", "b/y/2.ts", "c/z/3.ts"], "red"),
    ],
)
def test_impact_grades(cfg, files, expected):
    assert gate.grade_impact(make_pr(files), cfg)[0] == expected


def test_latest_is_not_mistaken_for_a_test_file(cfg):
    assert (
        gate.grade_impact(make_pr(["packages/bot/src/latest.ts"]), cfg)[0] == "yellow"
    )


# --- pillar: value --------------------------------------------------------


def test_value_green_for_p1_bug_with_test(cfg):
    pr = make_pr(["packages/bot/src/x.ts", "packages/bot/src/x.test.ts"])
    assert gate.grade_value(pr, make_issue(), cfg)[0] == "green"


def test_value_yellow_when_test_file_only_loses_lines(cfg):
    pr = make_pr(["packages/bot/src/x.ts", "packages/bot/src/x.test.ts"])
    pr["files"][1].update(additions=0, deletions=12)
    assert gate.grade_value(pr, make_issue(), cfg)[0] == "yellow"


def test_value_yellow_for_bug_without_test(cfg):
    assert (
        gate.grade_value(make_pr(["packages/bot/src/x.ts"]), make_issue(), cfg)[0]
        == "yellow"
    )


def test_value_yellow_for_docs_issue(cfg):
    issue = make_issue(labels=("ready-for-agent", "cat:docs", "effort:s"))
    assert gate.grade_value(make_pr(["README.md"]), issue, cfg)[0] == "yellow"


@pytest.mark.parametrize(
    "pr_kwargs,issue",
    [
        ({"closes": ()}, make_issue()),
        ({}, None),
        ({}, make_issue(author="stranger")),
        ({}, make_issue(labels=("cat:bug",))),
    ],
)
def test_value_red(cfg, pr_kwargs, issue):
    assert gate.grade_value(make_pr(["x.ts"], **pr_kwargs), issue, cfg)[0] == "red"


# --- pillar: security -----------------------------------------------------


@pytest.mark.parametrize(
    "files,checks,expected",
    [
        (["packages/bot/src/x.ts"], "SUCCESS", "green"),
        (["packages/bot/package.json"], "SUCCESS", "yellow"),
        (["packages/bot/src/x.ts"], "PENDING", "yellow"),
        (["packages/backend/src/auth/session.ts"], "SUCCESS", "red"),
        (["packages/backend/src/oauthState.ts"], "SUCCESS", "red"),
        ([".env.example"], "SUCCESS", "red"),
        (["packages/bot/src/x.ts"], "FAILURE", "yellow"),
    ],
)
def test_security_grades(cfg, files, checks, expected):
    pr = make_pr(files, checks=checks)
    assert gate.grade_security(pr, cfg, gate.checks_state(pr))[0] == expected


# --- decision -------------------------------------------------------------


def test_four_greens_waits_for_owner_while_auto_merge_is_off(cfg):
    pr = make_pr(["docs/a.md", "packages/bot/src/x.test.ts"])
    out = gate.score(pr, make_issue(), cfg)
    assert out["pillars"] == {
        "size": "green",
        "impact": "green",
        "value": "green",
        "security": "green",
    }
    assert out["decision"] == "owner-review"


def test_four_greens_auto_merges_after_graduation(cfg):
    cfg["auto_merge"] = True
    out = gate.score(
        make_pr(["docs/a.md", "packages/bot/src/x.test.ts"]), make_issue(), cfg
    )
    assert out["decision"] == "auto-merge"


def test_one_yellow_never_auto_merges(cfg):
    cfg["auto_merge"] = True
    out = gate.score(
        make_pr(["packages/bot/src/x.ts", "packages/bot/src/x.test.ts"]),
        make_issue(),
        cfg,
    )
    assert out["decision"] == "owner-review"


@pytest.mark.parametrize(
    "pr,issue,decision",
    [
        (make_pr(["packages/backend/src/auth/a.ts"]), make_issue(), "needs-human"),
        (make_pr([".github/workflows/ci.yml"]), make_issue(), "needs-human"),
        (make_pr(["x.ts"], closes=()), make_issue(), "close"),
        (make_pr(["docs/a.md"], lines=900), make_issue(), "split"),
        (make_pr(["x.ts"], checks="FAILURE"), make_issue(), "autofix"),
        (make_pr(["x.ts"], checks="IN_PROGRESS"), make_issue(), "wait"),
    ],
)
def test_decisions(cfg, pr, issue, decision):
    if decision == "wait":
        pr["statusCheckRollup"] = [{"status": "IN_PROGRESS", "conclusion": None}]
    assert gate.score(pr, issue, cfg)["decision"] == decision


@pytest.mark.parametrize(
    "pr",
    [
        make_pr(["docs/a.md"], author="stranger"),
        make_pr(["docs/a.md"], comments=("someone",)),
        make_pr(["docs/a.md"], reviews=("someone",)),
    ],
)
def test_halt_on_foreign_human_activity(cfg, pr):
    assert gate.score(pr, make_issue(), cfg)["decision"] == "halt"


def test_bots_do_not_trigger_halt(cfg):
    pr = make_pr(
        ["docs/a.md"], comments=("sonarqubecloud", "github-actions[bot]", OWNER)
    )
    assert gate.score(pr, make_issue(), cfg)["decision"] != "halt"


def test_review_bots_without_bot_suffix_do_not_trigger_halt(cfg):
    # gh pr view strips "[bot]" from app logins (Lucky#2779 halted on this).
    pr = make_pr(["docs/a.md"], reviews=("graphify-labs", "cubic-dev-ai"))
    assert gate.score(pr, make_issue(), cfg)["decision"] != "halt"


# --- issue selection ------------------------------------------------------


def test_select_ranks_bug_then_p1_then_oldest(cfg):
    issues = [
        make_issue(
            number=10,
            labels=("ready-for-agent", "effort:s", "cat:feature", "P1"),
            created="2026-01-01",
        ),
        make_issue(
            number=11,
            labels=("ready-for-agent", "effort:s", "cat:bug"),
            created="2026-09-01",
        ),
        make_issue(
            number=12,
            labels=("ready-for-agent", "effort:s", "cat:bug", "P1"),
            created="2026-09-02",
        ),
    ]
    assert gate.select(issues, [], cfg)["issue"] == 12


@pytest.mark.parametrize(
    "issue,reason",
    [
        (make_issue(author="stranger"), "not owner-authored"),
        (
            make_issue(labels=("ready-for-agent", "effort:m", "cat:bug")),
            "effort not allowed",
        ),
        (make_issue(labels=("ready-for-agent", "cat:bug")), "effort not allowed"),
        (make_issue(labels=("ready-for-agent", "effort:s", "blocked")), "skip label"),
        (
            make_issue(title="ci(deploy): skip unchanged image"),
            "sensitive topic: deploy",
        ),
        (
            make_issue(title="feat: landing page with OAuth state"),
            "sensitive topic: auth",
        ),
        (make_issue(comments=("someone",)), "foreign comment"),
    ],
)
def test_select_skips(cfg, issue, reason):
    out = gate.select([issue], [], cfg)
    assert out["issue"] is None
    assert out["skipped"]["1"] == reason


def test_select_skips_issue_with_open_agent_pr(cfg):
    out = gate.select(
        [make_issue(number=7)], [{"closingIssuesReferences": [{"number": 7}]}], cfg
    )
    assert out == {"issue": None, "skipped": {"7": "open PR already claims it"}}


def _closing_ref(number, owner="LucasSantana-Dev", name="Lucky"):
    return {"number": number, "repository": {"name": name, "owner": {"login": owner}}}


def test_select_skips_issue_closed_by_non_agent_open_pr(cfg):
    owner_pr = {
        "number": 2784,
        "headRefName": "fix/hand-made",
        "labels": [],
        "closingIssuesReferences": [_closing_ref(2780)],
    }
    out = gate.select(
        [make_issue(number=2780)], [owner_pr], cfg, "LucasSantana-Dev/Lucky"
    )
    assert out == {"issue": None, "skipped": {"2780": "open PR already claims it"}}


def test_select_ignores_closing_ref_to_another_repo(cfg):
    pr = {
        "headRefName": "fix/x",
        "closingIssuesReferences": [_closing_ref(5, name="cojam")],
    }
    out = gate.select([make_issue(number=5)], [pr], cfg, "LucasSantana-Dev/Lucky")
    assert out["issue"] == 5


# --- CLI ------------------------------------------------------------------


def _cli(*args, stdin=""):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
    )


def test_cli_score_roundtrip():
    payload = {"pr": make_pr(["docs/a.md", "x.test.ts"]), "issue": make_issue()}
    out = json.loads(_cli("score", stdin=json.dumps(payload)).stdout)
    live = gate.load_config(CONFIG)
    assert (
        out["decision"] == gate.score(payload["pr"], payload["issue"], live)["decision"]
    )


def _cli_raw(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )


def test_cli_get_without_key_is_a_usage_error():
    res = _cli_raw("get")
    assert res.returncode == 2
    assert "get needs --key" in res.stderr
    assert "Traceback" not in res.stderr


def test_cli_get_unknown_key_is_a_usage_error():
    res = _cli_raw("get", "--key", "no_such_key")
    assert res.returncode == 2
    assert "unknown config key: no_such_key" in res.stderr
    assert "Traceback" not in res.stderr


def test_cli_get_merges_repo_overrides():
    assert (
        _cli(
            "get", "--repo", "LucasSantana-Dev/homelab", "--key", "base"
        ).stdout.strip()
        == "release"
    )
    live = str(gate.load_config(CONFIG)["auto_merge"]).lower()
    assert _cli("get", "--key", "auto_merge").stdout.strip() == live


# --- critic fixes (T2 review) ---------------------------------------------


def test_ghost_comment_halts(cfg):
    pr = make_pr(["docs/a.md"])
    pr["comments"] = [{"author": None}]
    assert gate.score(pr, make_issue(), cfg)["decision"] == "halt"


def test_foreign_comment_on_linked_issue_halts(cfg):
    out = gate.score(make_pr(["docs/a.md"]), make_issue(comments=("someone",)), cfg)
    assert out["decision"] == "halt"


def test_no_checks_yet_waits_and_never_merges(cfg):
    cfg["auto_merge"] = True
    pr = make_pr(["docs/a.md", "x.test.ts"])
    pr["statusCheckRollup"] = []
    assert gate.score(pr, make_issue(), cfg)["decision"] == "wait"


def test_auto_merge_flag_must_be_real_true(cfg):
    cfg["auto_merge"] = "false"
    out = gate.score(make_pr(["docs/a.md", "x.test.ts"]), make_issue(), cfg)
    assert out["decision"] == "owner-review"


@pytest.mark.parametrize(
    "files,decision",
    [
        (["packages/backend/src/auth/a.ts"], "needs-human"),
        ([".github/workflows/ci.yml"], "needs-human"),
        (["docs/a.md"], "autofix"),
    ],
)
def test_pillars_outrank_autofix(cfg, files, decision):
    pr = make_pr(files, checks="FAILURE")
    assert gate.score(pr, make_issue(), cfg)["decision"] == decision


def test_red_value_closes_even_with_failing_ci(cfg):
    pr = make_pr(["x.ts"], checks="FAILURE", closes=())
    assert gate.score(pr, make_issue(), cfg)["decision"] == "close"


@pytest.mark.parametrize(
    "path",
    [
        "CLAUDE.md",
        "packages/bot/AGENTS.md",
        ".claude/settings.json",
        ".github/actions/setup/action.yml",
        ".github/CODEOWNERS",
        "docker-compose.prod.yml",
        "config/agent-box/agent-gate.json",
        "scripts/agent-tasks/agent_gate.py",
    ],
)
def test_agent_rules_and_infra_are_high_impact(cfg, path):
    assert gate.grade_impact(make_pr([path]), cfg)[0] == "red"


@pytest.mark.parametrize("branch", ["fix/issue-9", "agent/issue-9"])
def test_select_counts_issue_branch_without_closing_ref(cfg, branch):
    out = gate.select([make_issue(number=9)], [{"headRefName": branch}], cfg)
    assert out["skipped"] == {"9": "open PR already claims it"}


@pytest.mark.parametrize("branch", ["fix/issue-9-x", "feat/issue-9", "fix/issue-"])
def test_select_ignores_other_branch_shapes(cfg, branch):
    out = gate.select([make_issue(number=9)], [{"headRefName": branch}], cfg)
    assert "9" not in out["skipped"]


def test_only_agent_prs_needs_registry_for_fix_branches(tmp_path):
    lib = REPO / "scripts" / "agent-tasks" / "agent-loop-lib.sh"
    prs = [
        {"number": 1, "headRefName": "fix/issue-1", "labels": []},
        {"number": 2, "headRefName": "agent/issue-2", "labels": []},
        {"number": 3, "headRefName": "other", "labels": [{"name": "agent"}]},
        {"number": 4, "headRefName": "fix/typo", "labels": []},
        {"number": 5, "headRefName": "fix/issue-5", "labels": []},
    ]
    script = (
        f'source "{lib}"; AGENT_STATE_DIR="{tmp_path}"; AGENT_DRY_RUN=0; '
        "register_pr o/r 5; register_pr o/other 1; only_agent_prs o/r"
    )
    out = subprocess.run(
        ["bash", "-c", script],
        input=json.dumps(prs),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    # 1: hand-opened fix/issue-1 (only registered in another repo) is not tracked.
    assert [p["number"] for p in json.loads(out)] == [2, 3, 5]


# --- cubic review fixes ---------------------------------------------------


def test_human_push_without_comment_halts(cfg):
    pr = make_pr(["docs/a.md"])
    pr["commits"] = [
        {"authors": [{"login": OWNER}]},
        {"authors": [{"login": "someone"}]},
    ]
    assert gate.score(pr, make_issue(), cfg)["decision"] == "halt"


def test_owner_commits_do_not_halt(cfg):
    pr = make_pr(["docs/a.md", "x.test.ts"])
    pr["commits"] = [{"authors": [{"login": OWNER}]}]
    assert gate.score(pr, make_issue(), cfg)["decision"] == "owner-review"


def test_human_authored_issue_halts_instead_of_closing(cfg):
    out = gate.score(make_pr(["docs/a.md"]), make_issue(author="stranger"), cfg)
    assert out["decision"] == "halt"


def test_nested_systemd_units_are_high_impact(cfg):
    assert gate.grade_impact(make_pr(["scripts/systemd/x.service"]), cfg)[0] == "red"


def test_nested_requirements_is_a_dependency_change(cfg):
    pr = make_pr(["scripts/hacs/requirements-hacs-installer.txt"])
    assert gate.grade_security(pr, cfg, "passing")[0] == "yellow"


def test_claude_cmd_pins_permissions_and_feeds_prompt_on_stdin():
    lib = REPO / "scripts" / "agent-tasks" / "agent-loop-lib.sh"
    out = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{lib}"; claude_cmd LucasSantana-Dev/Lucky /w "fix it; rm -rf /" agent/issue-7 {SCRATCH}',
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "--permission-mode dontAsk" in out
    assert "--allowedTools" in out and "--disallowedTools" in out
    assert "Bash\\(gh\\ pr\\ merge\\*\\)" in out
    assert "-u ANTHROPIC_API_KEY" in out
    # The prompt is one quoted printf argument, never bare shell.
    assert "printf '%s' fix\\ it\\;\\ rm\\ -rf\\ /" in out
    # Push is pinned to the exact branch: no glob that admits refspecs or flags.
    assert "Bash\\(git\\ push\\ origin\\ agent/issue-7\\)" in out
    assert "Bash\\(git\\ push\\ -u\\ origin\\ agent/issue-7\\)" in out
    assert "agent/\\*" not in out
    assert "fix/\\*" not in out
    assert f"--add-dir {SCRATCH}" in out


def test_claude_cmd_accepts_new_and_legacy_prefix():
    lib = REPO / "scripts" / "agent-tasks" / "agent-loop-lib.sh"
    for branch in ("fix/issue-7", "agent/issue-7"):
        res = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{lib}"; claude_cmd LucasSantana-Dev/Lucky /w p {branch} {SCRATCH}',
            ],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, branch
        assert f"git\\ push\\ origin\\ {branch}" in res.stdout


def test_notify_once_dedups_per_sha(tmp_path):
    lib = REPO / "scripts" / "agent-tasks" / "agent-loop-lib.sh"
    script = (
        f'source "{lib}"; AGENT_STATE_DIR="{tmp_path}"; AGENT_DRY_RUN=0; '
        'notify() { echo "N $*"; }; notify_once o/r 5 abc wait t b warn; notify_once o/r 5 abc wait t b warn; '
        "notify_once o/r 5 abc close t b warn; notify_once o/r 5 def wait t b warn"
    )
    out = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=True
    ).stdout
    assert out.count("N --title t") == 3
    assert sorted(p.name for p in (tmp_path / "notified").iterdir()) == [
        "o_r-5-abc-close",
        "o_r-5-abc-wait",
        "o_r-5-def-wait",
    ]


@pytest.mark.parametrize(
    "branch",
    [
        "",
        "main",
        "release",
        "agent/x:main",
        "agent/+x",
        "agent/x y",
        "fix/x:main",
        "feat/x",
    ],
)
def test_claude_cmd_refuses_non_agent_branch(branch):
    lib = REPO / "scripts" / "agent-tasks" / "agent-loop-lib.sh"
    res = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{lib}"; claude_cmd LucasSantana-Dev/Lucky /w p "$1" {SCRATCH}',
            "_",
            branch,
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1
    assert res.stdout == ""


def test_gate_denies_push_variants_and_workflow_edits(cfg):
    denied = cfg["claude_disallowed_tools"]
    for rule in (
        "Bash(git push*--force*)",
        "Bash(git push*--delete*)",
        "Bash(git push*+*)",
        # Literal colon: a trailing ":*" is the prefix syntax and would never match.
        "Bash(git push*:**)",
        # Edit rules also cover Write; Write(path) rules are never consulted.
        "Edit(/.github/**)",
    ):
        assert rule in denied
    assert not any(t.startswith("Bash(git push") for t in cfg["claude_allowed_tools"])


# --- review threads -------------------------------------------------------


BOT_LOGINS = {"cubic-dev-ai", "coderabbitai"}


def thread(*logins, resolved=False):
    nodes = [
        {
            "author": {
                "__typename": "Bot" if x in BOT_LOGINS else "User",
                "login": x,
            },
            "body": "b",
        }
        for x in logins
    ]
    return {
        "id": "T-" + "-".join(logins),
        "isResolved": resolved,
        "comments": {"totalCount": len(nodes), "nodes": nodes},
    }


def pr_with_threads(*threads, files=("docs/a.md",), checks="SUCCESS", more=False):
    pr = make_pr(list(files), checks=checks)
    pr["reviewThreads"] = {"pageInfo": {"hasNextPage": more}, "nodes": list(threads)}
    return pr


def test_bot_threads_on_green_checks_autofix(cfg):
    pr = pr_with_threads(thread("cubic-dev-ai"), thread("coderabbitai"))
    out = gate.score(pr, make_issue(), cfg)
    assert (out["decision"], out["fix"]) == ("autofix", "threads")
    assert "review: 2 unresolved thread(s)" in out["reasons"]


def test_resolved_threads_leave_owner_review(cfg):
    pr = pr_with_threads(thread("cubic-dev-ai", resolved=True))
    out = gate.score(pr, make_issue(), cfg)
    assert out["decision"] == "owner-review"
    assert "fix" not in out


def test_thread_the_owner_joined_waits_for_the_owner(cfg):
    pr = pr_with_threads(thread("cubic-dev-ai", OWNER))
    assert gate.score(pr, make_issue(), cfg)["decision"] == "owner-review"


def test_empty_thread_is_not_bot_only(cfg):
    empty = {"id": "T", "isResolved": False, "comments": {"totalCount": 0, "nodes": []}}
    pr = pr_with_threads(empty)
    assert gate.score(pr, make_issue(), cfg)["decision"] == "owner-review"


def test_empty_thread_beside_bot_threads_waits_for_the_owner(cfg):
    empty = {"id": "T", "isResolved": False, "comments": {"totalCount": 0, "nodes": []}}
    pr = pr_with_threads(thread("cubic-dev-ai"), empty)
    out = gate.score(pr, make_issue(), cfg)
    assert out["decision"] == "owner-review"
    assert "fix" not in out
    assert "review: 2 unresolved thread(s), owner involved" in out["reasons"]


@pytest.mark.parametrize("resolved", [False, True])
def test_human_in_any_thread_halts(cfg, resolved):
    pr = pr_with_threads(thread("cubic-dev-ai", "stranger", resolved=resolved))
    assert gate.score(pr, make_issue(), cfg)["decision"] == "halt"


@pytest.mark.parametrize(
    "files,decision",
    [
        ([".github/workflows/ci.yml"], "needs-human"),
        ([f"docs/f{i}.md" for i in range(13)], "split"),
    ],
)
def test_pillar_reds_win_over_threads(cfg, files, decision):
    pr = pr_with_threads(thread("cubic-dev-ai"), files=files)
    assert gate.score(pr, make_issue(), cfg)["decision"] == decision


@pytest.mark.parametrize(
    "checks,decision,fix",
    [("FAILURE", "autofix", "ci"), ("IN_PROGRESS", "wait", None)],
)
def test_ci_state_wins_over_threads(cfg, checks, decision, fix):
    pr = pr_with_threads(thread("cubic-dev-ai"))
    if checks == "IN_PROGRESS":
        pr["statusCheckRollup"] = [{"status": checks}]
    else:
        pr["statusCheckRollup"] = [{"conclusion": checks, "status": "COMPLETED"}]
    out = gate.score(pr, make_issue(), cfg)
    assert (out["decision"], out.get("fix")) == (decision, fix)


def test_user_named_like_a_bot_in_a_thread_halts(cfg):
    t = thread("cubic-dev-ai")
    t["comments"]["nodes"][0]["author"] = {
        "__typename": "User",
        "login": "cubic-dev-ai",
    }
    assert gate.score(pr_with_threads(t), make_issue(), cfg)["decision"] == "halt"


def test_more_thread_pages_halt(cfg):
    pr = pr_with_threads(thread("cubic-dev-ai"), more=True)
    assert gate.score(pr, make_issue(), cfg)["decision"] == "halt"


def test_unfetched_thread_replies_halt(cfg):
    t = thread("cubic-dev-ai")
    t["comments"]["totalCount"] = 51
    assert gate.score(pr_with_threads(t), make_issue(), cfg)["decision"] == "halt"


def test_pr_without_thread_data_scores_as_before(cfg):
    pr = make_pr(["docs/a.md", "packages/bot/src/x.test.ts"])
    assert gate.score(pr, make_issue(), cfg)["decision"] == "owner-review"


def test_unlisted_app_thread_waits_for_the_owner(cfg):
    t = thread("cubic-dev-ai")
    t["comments"]["nodes"][0]["author"] = {"__typename": "Bot", "login": "some-app"}
    assert (
        gate.score(pr_with_threads(t), make_issue(), cfg)["decision"] == "owner-review"
    )


def _bash(script, state):
    lib = REPO / "scripts" / "agent-tasks" / "agent-loop-lib.sh"
    return subprocess.run(
        ["bash", "-c", f'source "{lib}"; AGENT_STATE_DIR="{state}"; {script}'],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_fix_counter_seeds_from_legacy_then_increments(tmp_path):
    out = _bash(
        "AGENT_DRY_RUN=0; fix_tries o/r 5 1; fix_record o/r 5 2; fix_tries o/r 5 0; "
        "fix_record o/r 5 3; fix_tries o/r 5 0; fix_tries o/r 6 0",
        tmp_path,
    )
    assert out.split() == ["1", "2", "3", "0"]
    assert (tmp_path / "autofix" / "o_r-5").read_text().strip() == "3"


def test_fix_counter_dry_run_writes_nothing(tmp_path):
    out = _bash("AGENT_DRY_RUN=1; fix_record o/r 5 2; fix_tries o/r 5 0", tmp_path)
    assert "DRY-RUN" in out and out.split()[-1] == "0"
    assert not (tmp_path / "autofix").exists()


def test_notify_once_failed_send_leaves_no_marker(tmp_path):
    out = _bash(
        "AGENT_DRY_RUN=0; notify() { return 1; }; notify_once o/r 5 abc wait t b warn; "
        'ls "$AGENT_STATE_DIR/notified" 2>/dev/null | wc -l',
        tmp_path,
    )
    assert out.strip() == "0"


@pytest.mark.parametrize("key", ["fix-cap", "dirty-workdir", "no-scratch"])
def test_gate_autofix_alerts_fire_once_per_sha(tmp_path, key):
    # Runs the gate's own alert line: the label edit may fail and the workdir may stay
    # dirty, so the same alert must not repeat on every timer run.
    gate_sh = REPO / "scripts" / "agent-tasks" / "agent-pr-gate.sh"
    lines = [
        ln.strip()
        for ln in gate_sh.read_text().splitlines()
        if ln.strip().startswith("notify_once") and f" {key} " in ln
    ]
    assert len(lines) == 1, lines
    env = (
        'AGENT_DRY_RUN=0; notify() { echo "N $*"; }; REPO=o/r; N=5; '
        "WHAT='CI still red'; TRIES=3; WORKDIR=/w; DIRTY=x; "
    )
    run = f"SHA=abc; {lines[0]}; {lines[0]}; SHA=def; {lines[0]}"
    out = _bash(env + run, tmp_path)
    assert out.count("N --title") == 2
    assert sorted(p.name for p in (tmp_path / "notified").iterdir()) == [
        f"o_r-5-abc-{key}",
        f"o_r-5-def-{key}",
    ]


def test_gate_sends_no_undeduped_alerts():
    gate_sh = REPO / "scripts" / "agent-tasks" / "agent-pr-gate.sh"
    bare = [
        ln.strip()
        for ln in gate_sh.read_text().splitlines()
        if ln.strip().startswith("notify ")
    ]
    assert bare == []


def test_gate_merges_now_and_never_queues():
    # A queued --auto merge fires later without a new score: a human who joins after
    # the gate run would be merged over.
    gate_sh = REPO / "scripts" / "agent-tasks" / "agent-pr-gate.sh"
    merges = [
        ln.strip()
        for ln in gate_sh.read_text().splitlines()
        if ln.strip().startswith('if act "gh pr merge')
    ]
    assert len(merges) == 1, merges
    assert "--auto" not in merges[0]
    assert "--match-head-commit $SHA" in merges[0]


# --- scratch dir (commit messages, PR bodies, thread replies) -------------

LIB = REPO / "scripts" / "agent-tasks" / "agent-loop-lib.sh"
TASKS = REPO / "scripts" / "agent-tasks"


def _lib(script, *args):
    return subprocess.run(
        ["bash", "-c", f'source "{LIB}"; {script}', "_", *args],
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "scratch",
    [
        "",
        "/workspace/cojam",
        "/workspace/cojam/.git",
        "/tmp/agent-run.short",
        "/tmp/agent-run.Ab3dEf9h/../x",
        "/tmp/agent-run.Ab3dEf9h; rm -rf /",
        "/tmp/discord-scratch",
    ],
)
def test_claude_cmd_refuses_foreign_scratch_dir(scratch):
    res = _lib('claude_cmd LucasSantana-Dev/Lucky /w p fix/issue-7 "$1"', scratch)
    assert res.returncode == 1
    assert res.stdout == ""


def test_scratch_new_validates_the_remote_path():
    ok = _lib(f"AGENT_DRY_RUN=0; run_on_agent() {{ echo {SCRATCH}; }}; scratch_new")
    assert (ok.returncode, ok.stdout.strip()) == (0, SCRATCH)
    for remote in ("echo /workspace/cojam", "echo", "return 1"):
        bad = _lib(f"AGENT_DRY_RUN=0; run_on_agent() {{ {remote}; }}; scratch_new")
        assert bad.returncode == 1, remote
        assert bad.stdout == ""


def test_scratch_new_dry_run_touches_nothing():
    res = _lib(
        'AGENT_DRY_RUN=1; run_on_agent() { echo CALLED; }; d=$(scratch_new) && scratch_ok "$d" && echo ok'
    )
    assert res.stdout.strip() == "ok"


def test_scratch_rm_only_removes_scratch_paths():
    res = _lib(
        'AGENT_DRY_RUN=0; run_on_agent() { echo "RUN $1"; }; '
        'scratch_rm ""; scratch_rm /workspace/cojam; scratch_rm "/tmp/agent-run.Ab3dEf9h/..";'
        f" scratch_rm {SCRATCH}"
    )
    assert res.returncode == 0
    assert res.stdout.splitlines() == [f"RUN rm -rf -- {SCRATCH}"]


def test_workdir_clean_lists_offending_paths():
    status = "\\n".join(
        [
            "?? apps/web/lib/telemetry.pr-body.md",
            "?? telemetry.test.ts.commitmsg",
            "R  old.ts -> renamed.ts",
            "?? odd -> name.md",
            " M a.ts",
            " M b.ts",
            " M c.ts",
            " M d.ts",
            " M e.ts",
        ]
    )
    res = _lib(
        f"run_on_agent() {{ printf '{status}\\n'; }}; "
        'if out=$(workdir_clean /w); then echo clean; else echo "dirty: $out"; fi'
    )
    assert res.stdout.strip() == (
        "dirty: in the way: apps/web/lib/telemetry.pr-body.md,"
        " telemetry.test.ts.commitmsg, renamed.ts, odd -> name.md, a.ts and 4 more"
    )
    clean = _lib(
        'run_on_agent() { :; }; out=$(workdir_clean /w) && echo "clean [$out]"'
    )
    assert clean.stdout.strip() == "clean []"
    down = _lib(
        'run_on_agent() { return 255; }; out=$(workdir_clean /w) || echo "$out"'
    )
    assert down.stdout.strip() == "could not check: agent-box or git unreachable"


def _bash_allowed(cmd, cfg):
    import fnmatch

    rules = [r[5:-1] for r in cfg["claude_allowed_tools"] if r.startswith("Bash(")]
    return any(fnmatch.fnmatchcase(cmd, r) for r in rules)


def test_worker_prompt_writes_outside_the_repo(cfg):
    worker = (TASKS / "agent-worker.sh").read_text()
    assert ".git/agent-" not in worker
    assert "`git commit -F __SCRATCH__/commit-msg`" in worker
    assert "--body-file __SCRATCH__/pr-body.md`" in worker
    # The placeholder is filled before the prompt reaches claude_cmd.
    assert '"${PROMPT//__SCRATCH__/$SCRATCH}"' in worker
    for cmd in (
        f"git commit -F {SCRATCH}/commit-msg",
        f"gh pr create --repo o/r --base main --title t --body-file {SCRATCH}/pr-body.md",
    ):
        assert _bash_allowed(cmd, cfg), cmd


def test_gate_makes_scratch_before_spending_budget_or_attempts():
    text = (TASKS / "agent-pr-gate.sh").read_text()
    made = text.index("SCRATCH=$(scratch_new)")
    assert made < text.index("budget_take ||")
    assert made < text.index('fix_record "$REPO"')


def test_gate_autofix_writes_outside_the_repo():
    gate_path = TASKS / "agent-pr-gate.sh"
    gate_sh = gate_path.read_text()
    assert ".git/agent-" not in gate_sh
    assert "REPLIES_FILE" not in gate_sh
    assert 'REPLIES="$SCRATCH/thread-replies.json"' in gate_sh
    calls = [ln.strip() for ln in gate_sh.splitlines() if "CMD=$(claude_cmd" in ln]
    assert len(calls) == 1 and '"$SCRATCH")' in calls[0], calls
    extract = f'eval "$(sed -n "/^NEUTRAL=/p;/^git_rules()/,/^}}/p" "{gate_path}")"'
    out = subprocess.run(
        ["bash", "-c", f"{extract}; git_rules {SCRATCH}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert f"git commit -F {SCRATCH}/commit-msg" in out


@pytest.mark.parametrize("script", ["agent-worker.sh", "agent-pr-gate.sh"])
def test_scratch_dir_is_removed_on_exit_and_after_each_run(script):
    text = (TASKS / script).read_text()
    trap = "trap 'scratch_rm \"$SCRATCH\"' EXIT"
    assert text.count(trap) == 1
    # Plus an explicit removal after the claude run, outside the trap string.
    lines = [ln.strip() for ln in text.splitlines()]
    after_run = [i for i, ln in enumerate(lines) if ln == 'scratch_rm "$SCRATCH"']
    assert after_run, "no explicit scratch_rm after the claude run"
    last = after_run[-1]
    assert lines[last + 1] == 'SCRATCH=""'
    runs = [i for i, ln in enumerate(lines) if 'act "$CMD"' in ln]
    assert len(runs) == 1, runs
    assert runs[0] < last


def test_discord_scratch_dir_agrees_across_files():
    conf = REPO / "config" / "agent-box"
    path = "/tmp/discord-scratch"
    settings = json.loads((conf / "discord-channel-settings.json").read_text())
    assert settings["permissions"]["additionalDirectories"] == [path]
    sh = (conf / "discord-channel.sh").read_text()
    assert f"SCRATCH={path}\n" in sh
    assert 'mkdir -m 700 "$SCRATCH"' in sh
    assert "rm -rf $SCRATCH;" in sh  # after claude exits, inside the tmux command
    assert 'kill-session -t "$SESSION" 2>/dev/null; rm -rf "$SCRATCH"' in sh
    md = (conf / "discord-channel.md").read_text()
    assert f"commit -F {path}/commit-msg" in md
    assert f"--body-file {path}/pr-body.md" in md
    assert ".git/agent-" not in md


# --- merge-check and pr-automerge (ADR 0042) ------------------------------

TASKS = REPO / "scripts" / "agent-tasks"
AUTOMERGE = TASKS / "pr-automerge.sh"
HEAD = "a" * 40


def test_merge_check_passes_a_clean_owner_pr(cfg):
    assert gate.merge_check(make_pr(["packages/bot/src/x.ts"]), cfg, []) == []


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"isDraft": True}, "draft"),
        ({"isDraft": None}, "draft"),
        ({"state": "MERGED"}, "not open"),
        ({"isCrossRepository": True}, "fork"),
        ({"baseRefName": "release"}, "base is release, must be main"),
        ({"author": {"login": "someone"}}, "another human"),
        ({"comments": [{"author": {"login": "someone"}}]}, "another human"),
        ({"changedFiles": 101}, "truncated"),
        ({"files": []}, "missing"),
    ],
)
def test_merge_check_refuses(cfg, change, reason):
    pr = {**make_pr(["src/x.ts"]), **change}
    assert any(reason in r for r in gate.merge_check(pr, cfg, []))


@pytest.mark.parametrize(
    "key",
    [
        "state",
        "isDraft",
        "isCrossRepository",
        "baseRefName",
        "changedFiles",
        "reviewThreads",
    ],
)
def test_merge_check_fails_closed_on_missing_fields(cfg, key):
    pr = make_pr(["src/x.ts"])
    del pr[key]
    assert gate.merge_check(pr, cfg, [])


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/ci.yml",
        "compose/agent-box.yml",
        "config/agent-box/agent-gate.json",
        "scripts/agent-tasks/pr-automerge.sh",
        "packages/backend/src/auth/x.ts",
        ".env.production",
        "infra/main.tf",
        "scripts/deploy.sh",
        "CLAUDE.md",
        "Dockerfile.agent-box",
        "prisma/migrations/1/migration.sql",
        "package.json",
        "pnpm-lock.yaml",
        "server/go.mod",
        "server/go.sum",
    ],
)
def test_merge_check_refuses_sensitive_and_infra_paths(cfg, path):
    reasons = gate.merge_check(make_pr(["src/x.ts", path]), cfg, [])
    assert any("owner-review paths" in r for r in reasons)


def test_merge_check_needs_the_linked_issues(cfg):
    pr = make_pr(["src/x.ts"])
    assert gate.merge_check(pr, cfg, None) == ["linked issues not loaded"]
    foreign = make_issue()
    foreign["author"] = {"login": "someone"}
    assert any("another human" in r for r in gate.merge_check(pr, cfg, [foreign]))
    assert gate.merge_check(pr, cfg, [make_issue()]) == []


@pytest.mark.parametrize(
    "path,ok",
    [
        ("docs/a.md", True),
        ("tests/unit/test_x.py", True),
        ("config/caddy/Caddyfile", False),
        ("scripts/backup/run.sh", False),
        ("tailscale/acl.json", False),
        ("observability/prometheus.yml", False),
        (".sops.yaml", False),
        ("homelab_manager/cli.py", False),
    ],
)
def test_merge_check_homelab_blocks_host_infra(path, ok):
    c = gate.load_config(CONFIG)
    c = {**c, **c["repos"]["LucasSantana-Dev/homelab"]}
    pr = make_pr([path])
    pr["baseRefName"] = "release"
    assert (gate.merge_check(pr, c, []) == []) is ok


def test_merge_check_refuses_open_threads_even_from_bots(cfg):
    pr = pr_with_threads(thread("cubic-dev-ai"), files=("src/x.ts",))
    assert gate.merge_check(pr, cfg, []) == ["1 unresolved review thread(s)"]


def test_merge_check_refuses_unfetched_thread_pages(cfg):
    pr = pr_with_threads(files=("src/x.ts",), more=True)
    assert "review threads not fully loaded" in gate.merge_check(pr, cfg, [])


def test_merge_check_homelab_needs_release_base():
    c = gate.load_config(CONFIG)
    c = {**c, **c["repos"]["LucasSantana-Dev/homelab"]}
    pr = make_pr(["docs/a.md"])
    assert gate.merge_check(pr, c, []) == ["base is main, must be release"]
    pr["baseRefName"] = "release"
    assert gate.merge_check(pr, c, []) == []


def test_no_red_mode_merges_yellow_pillars(cfg):
    cfg["auto_merge"] = "no-red"
    pr = make_pr(["packages/bot/src/x.ts", "packages/bot/src/x.test.ts"])
    out = gate.score(pr, make_issue(), cfg)
    assert "yellow" in out["pillars"].values()
    assert out["decision"] == "auto-merge"


def test_no_red_mode_never_merges_red(cfg):
    cfg["auto_merge"] = "no-red"
    out = gate.score(make_pr(["packages/backend/src/auth/a.ts"]), make_issue(), cfg)
    assert out["decision"] != "auto-merge"


def test_green_mode_still_holds_yellow(cfg):
    cfg["auto_merge"] = True
    pr = make_pr(["packages/bot/src/x.ts", "packages/bot/src/x.test.ts"])
    assert gate.score(pr, make_issue(), cfg)["decision"] == "owner-review"


def test_auto_merge_waits_for_the_owner_when_merge_check_fails(cfg):
    cfg["auto_merge"] = "no-red"
    pr = make_pr(["packages/bot/src/x.ts", "packages/bot/src/x.test.ts"])
    pr["isDraft"] = True
    out = gate.score(pr, make_issue(), cfg)
    assert out["decision"] == "owner-review"
    assert "merge check: draft" in out["reasons"]


def test_cli_merge_check_needs_an_allowlisted_repo():
    assert _cli_raw("merge-check").returncode == 2
    assert _cli_raw("merge-check", "--repo", "someone/else").returncode == 2


def test_cli_merge_check_roundtrip():
    pr = make_pr(["docs/a.md"])
    pr["baseRefName"] = "release"
    out = _cli(
        "merge-check",
        "--repo",
        "LucasSantana-Dev/homelab",
        stdin=json.dumps({"pr": pr, "issues": []}),
    )
    assert json.loads(out.stdout) == {"ok": True, "reasons": []}


ISSUE_URL = "https://github.com/LucasSantana-Dev/Lucky/issues/1"


def _gh_pr(files=("src/x.ts",), queued=False, **extra):
    pr = make_pr(list(files))
    del pr["reviewThreads"]  # gh pr view has none; the wrapper adds them
    pr["headRefOid"] = HEAD
    pr["autoMergeRequest"] = {"mergeMethod": "SQUASH"} if queued else None
    pr["closingIssuesReferences"] = [{"number": 1, "url": ISSUE_URL}]
    pr.update(extra)
    return pr


def _fake_bin(tmp_path, threads=None, issue=None):
    """A bin dir with a fake gh that logs its args and serves pr-<n>.json files."""
    (tmp_path / "threads.json").write_text(
        json.dumps(threads or {"pageInfo": {"hasNextPage": False}, "nodes": []})
    )
    (tmp_path / "issue.json").write_text(json.dumps(issue or make_issue()))
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(
        "#!/bin/bash\n"
        f'echo "$*" >> "{tmp_path}/gh.log"\n'
        'case "$1 $2" in\n'
        f'  "pr view") cat "{tmp_path}/pr-$3.json" ;;\n'
        '  "api graphql")\n'
        '    if [[ "$*" == *mutation* ]]; then\n'
        '      for a in "$@"; do case "$a" in id=*) id=${a#id=} ;; body=*) body=${a#body=} ;; esac; done\n'
        '      kind=reply; [[ "$*" == *resolveReviewThread* ]] && kind=resolve\n'
        '      [[ "$kind" == reply ]] && rc=${GH_REPLY_RC:-0} || rc=${GH_RESOLVE_RC:-0}\n'
        f'      echo "$kind $id $body" >> "{tmp_path}/mutations.log"\n'
        '      if [[ "$kind" == resolve && "$rc" == 0 ]]; then\n'
        "        jq --arg id \"$id\" '(.nodes[] | select(.id == $id) | .isResolved) = true' "
        f'"{tmp_path}/threads.json" > "{tmp_path}/t.json"\n'
        f'        mv "{tmp_path}/t.json" "{tmp_path}/threads.json"\n'
        "      fi\n"
        '      exit "$rc"\n'
        "    fi\n"
        f'    cat "{tmp_path}/threads.json" ;;\n'
        f'  "issue view") [[ "$3" == "{ISSUE_URL}" ]] && cat "{tmp_path}/issue.json" ;;\n'
        f'  "pr list") cat "{tmp_path}/list.txt" ;;\n'
        '  "pr merge") exit "${GH_MERGE_RC:-0}" ;;\n'
        "  *) exit 9 ;;\n"
        "esac\n"
    )
    gh.chmod(0o755)
    for tool in ("jq", "python3", "git"):
        link = bindir / tool
        if not link.exists():
            link.symlink_to(shutil.which(tool))
    return bindir


def _automerge(
    tmp_path, *args, prs=None, threads=None, issue=None, env=None, script=None
):
    """Run pr-automerge with a fake gh. prs maps PR number to gh pr view JSON."""
    for n, pr in (prs or {}).items():
        (tmp_path / f"pr-{n}.json").write_text(json.dumps(pr))
    bindir = _fake_bin(tmp_path, threads, issue)
    full_env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "PR_AUTOMERGE_STATE": str(tmp_path / "state"),
        **(env or {}),
    }
    res = subprocess.run(
        ["/bin/bash", str(script or AUTOMERGE), *args],
        env=full_env,
        capture_output=True,
        text=True,
    )
    log = tmp_path / "gh.log"
    return res, (log.read_text() if log.exists() else "")


def _merge_calls(log):
    return [ln for ln in log.splitlines() if ln.startswith("pr merge")]


def test_automerge_queues_a_clean_pr_on_the_checked_head(tmp_path):
    res, log = _automerge(tmp_path, "LucasSantana-Dev/Lucky", "7", prs={7: _gh_pr()})
    assert res.returncode == 0, res.stdout + res.stderr
    assert _merge_calls(log) == [
        f"pr merge 7 -R LucasSantana-Dev/Lucky --squash --auto --match-head-commit {HEAD}"
    ]
    entry = tmp_path / "state" / "LucasSantana-Dev_Lucky-7"
    assert entry.read_text().strip() == HEAD


def test_automerge_does_not_queue_twice(tmp_path):
    pr = _gh_pr(queued=True)
    res, log = _automerge(tmp_path, "LucasSantana-Dev/Lucky", "7", prs={7: pr})
    assert res.returncode == 0, res.stdout + res.stderr
    assert _merge_calls(log) == []


def test_automerge_refuses_without_merging(tmp_path):
    pr = _gh_pr(files=("src/x.ts", ".github/workflows/ci.yml"))
    res, log = _automerge(tmp_path, "LucasSantana-Dev/Lucky", "7", prs={7: pr})
    assert res.returncode == 1
    assert "refused: owner-review paths" in res.stdout
    assert _merge_calls(log) == []
    assert not (tmp_path / "state").exists()


def test_automerge_turns_off_a_queued_merge_that_fails(tmp_path):
    pr = _gh_pr(queued=True, comments=[{"author": {"login": "someone"}}])
    res, log = _automerge(tmp_path, "LucasSantana-Dev/Lucky", "7", prs={7: pr})
    assert res.returncode == 1
    assert _merge_calls(log) == ["pr merge 7 -R LucasSantana-Dev/Lucky --disable-auto"]


def test_automerge_refuses_bot_threads(tmp_path):
    threads = {"pageInfo": {"hasNextPage": False}, "nodes": [thread("cubic-dev-ai")]}
    res, log = _automerge(
        tmp_path, "LucasSantana-Dev/Lucky", "7", prs={7: _gh_pr()}, threads=threads
    )
    assert res.returncode == 1
    assert _merge_calls(log) == []


@pytest.mark.parametrize(
    "args",
    [
        ("someone/else", "7"),
        ("LucasSantana-Dev/Lucky", "7; rm -rf /"),
        ("LucasSantana-Dev/Lucky", "--admin"),
        ("LucasSantana-Dev/Lucky",),
        ("--sweep", "x"),
    ],
)
def test_automerge_bad_arguments_never_merge(tmp_path, args):
    res, log = _automerge(tmp_path, *args, prs={7: _gh_pr()})
    assert res.returncode != 0
    assert _merge_calls(log) == []


def test_automerge_sweep(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    for n in (1, 2, 3, 4):
        (state / f"LucasSantana-Dev_Lucky-{n}").write_text(HEAD)
    (state / "junk name").write_text("")
    prs = {
        1: _gh_pr(queued=True),  # still fine: kept
        2: _gh_pr(queued=True, files=("src/x.ts", "compose/x.yml")),  # turned off
        3: _gh_pr(queued=True, state="MERGED"),  # done: forgotten
        4: _gh_pr(queued=False),  # turned off by someone: forgotten
    }
    res, log = _automerge(tmp_path, "--sweep", prs=prs)
    assert res.returncode == 3
    assert _merge_calls(log) == ["pr merge 2 -R LucasSantana-Dev/Lucky --disable-auto"]
    assert sorted(p.name for p in state.iterdir()) == [
        "LucasSantana-Dev_Lucky-1",
        "junk name",
    ]


def test_automerge_merge_calls_are_only_queue_or_disable():
    calls = [
        ln.strip()
        for ln in AUTOMERGE.read_text().splitlines()
        if "gh pr merge" in ln and not ln.lstrip().startswith("#")
    ]
    assert len(calls) == 2, calls
    assert all("--admin" not in c for c in calls)
    assert any('--squash --auto --match-head-commit "$sha"' in c for c in calls)
    assert any("--disable-auto" in c for c in calls)


def test_automerge_ships_root_owned_in_the_image():
    df = (REPO / "Dockerfile.agent-box").read_text()
    for src, dst in [
        ("scripts/agent-tasks/pr-automerge.sh", "/opt/agent-config/pr-automerge.sh"),
        ("scripts/agent-tasks/agent_gate.py", "/opt/agent-config/agent_gate.py"),
        ("config/agent-box/agent-gate.json", "/opt/agent-config/agent-gate.json"),
    ]:
        assert f"COPY {src} {dst}" in df
    assert "ln -s /opt/agent-config/pr-automerge.sh /usr/local/bin/pr-automerge" in df


def test_model_still_cannot_run_gh_pr_merge(cfg):
    conf = REPO / "config" / "agent-box"
    discord = json.loads((conf / "discord-channel-settings.json").read_text())
    user = json.loads((conf / "settings.json").read_text())
    assert "Bash(gh pr merge*)" in discord["permissions"]["deny"]
    assert "Bash(gh * pr merge*)" in discord["permissions"]["deny"]
    assert "Bash(gh pr merge*)" in user["permissions"]["deny"]
    assert "Bash(gh pr merge*)" in cfg["claude_disallowed_tools"]
    rules = (conf / "discord-channel.md").read_text()
    assert "pr-automerge <owner/repo> <pr-number>" in rules


def test_gate_sweeps_queued_merges():
    gate_sh = (TASKS / "agent-pr-gate.sh").read_text()
    assert "pr-automerge --sweep" in gate_sh
    view = next(ln for ln in gate_sh.splitlines() if "gh pr view $2" in ln)
    for f in ("state", "isDraft", "isCrossRepository", "baseRefName", "changedFiles"):
        assert f in view


def test_automerge_refuses_a_pr_closing_a_foreign_issue(tmp_path):
    res, log = _automerge(
        tmp_path,
        "LucasSantana-Dev/Lucky",
        "7",
        prs={7: _gh_pr()},
        issue=make_issue(author="someone"),
    )
    assert res.returncode == 1
    assert "another human" in res.stdout
    assert _merge_calls(log) == []


def test_automerge_refuses_when_a_linked_issue_cannot_load(tmp_path):
    pr = _gh_pr(closingIssuesReferences=[{"number": 9, "url": None}])
    res, log = _automerge(tmp_path, "LucasSantana-Dev/Lucky", "7", prs={7: pr})
    assert res.returncode == 1
    assert "could not load" in res.stdout
    assert _merge_calls(log) == []


def test_automerge_keeps_tracking_when_disable_fails(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "LucasSantana-Dev_Lucky-2").write_text(HEAD)
    pr = _gh_pr(queued=True, files=("src/x.ts", "compose/x.yml"))
    res, log = _automerge(tmp_path, "--sweep", prs={2: pr}, env={"GH_MERGE_RC": "1"})
    assert res.returncode == 3
    assert "STILL QUEUED" in res.stdout
    assert (state / "LucasSantana-Dev_Lucky-2").exists()


def test_image_copy_ignores_the_callers_environment(tmp_path):
    """Installed under /opt/agent-config, the wrapper pins its config, registry and PATH."""
    opt = (tmp_path / "opt").resolve()
    opt.mkdir()
    bindir = _fake_bin(tmp_path)
    locked_state = tmp_path / "locked-state"
    src = AUTOMERGE.read_text()
    src = src.replace("/opt/agent-config", str(opt))
    src = src.replace(
        "PATH=/usr/local/bin:/usr/bin:/bin", f"PATH={bindir}:/usr/bin:/bin"
    )
    src = src.replace("/home/agent/.local/state/pr-automerge", str(locked_state))
    (opt / "pr-automerge.sh").write_text(src)
    shutil.copy(SCRIPT, opt / "agent_gate.py")
    shutil.copy(CONFIG, opt / "agent-gate.json")
    loose = json.loads(CONFIG.read_text())
    for key in ("high_impact_paths", "sensitive_paths", "repo_merge_block_paths"):
        loose[key] = []
    (tmp_path / "loose.json").write_text(json.dumps(loose))
    env = {
        "AGENT_GATE_CONFIG": str(tmp_path / "loose.json"),
        "PR_AUTOMERGE_STATE": str(tmp_path / "hidden"),
        "PATH": "/nonexistent",
    }
    bad = _gh_pr(files=("src/x.ts", ".github/workflows/ci.yml"))
    res, log = _automerge(
        tmp_path,
        "LucasSantana-Dev/Lucky",
        "7",
        prs={7: bad},
        env=env,
        script=opt / "pr-automerge.sh",
    )
    assert res.returncode == 1, res.stdout + res.stderr
    assert "owner-review paths" in res.stdout
    assert _merge_calls(log) == []
    res, log = _automerge(
        tmp_path,
        "LucasSantana-Dev/Lucky",
        "8",
        prs={8: _gh_pr()},
        env=env,
        script=opt / "pr-automerge.sh",
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert (locked_state / "LucasSantana-Dev_Lucky-8").exists()
    assert not (tmp_path / "hidden").exists()


# --- automerge-push-guard (hook) ------------------------------------------

PUSH_GUARD = REPO / "config" / "agent-box" / "automerge-push-guard.sh"


def _push_guard(tmp_path, command, listed="", merge_rc="0", list_ok=True):
    repo = tmp_path / "Lucky"
    if not repo.exists():
        subprocess.run(["git", "init", "-q", "-b", "fix/x", str(repo)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "remote",
                "add",
                "origin",
                "https://github.com/LucasSantana-Dev/Lucky.git",
            ],
            check=True,
        )
    bindir = _fake_bin(tmp_path)
    (tmp_path / "list.txt").write_text(listed)
    if not list_ok:
        (tmp_path / "list.txt").unlink()
    payload = {"tool_input": {"command": command.format(repo=repo)}, "cwd": "/"}
    res = subprocess.run(
        ["bash", str(PUSH_GUARD)],
        input=json.dumps(payload),
        env={
            **os.environ,
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "GH_MERGE_RC": merge_rc,
        },
        capture_output=True,
        text=True,
    )
    log = tmp_path / "gh.log"
    return res, (log.read_text() if log.exists() else "")


def test_push_guard_ignores_other_commands(tmp_path):
    res, log = _push_guard(tmp_path, "git -C {repo} status")
    assert res.returncode == 0
    assert log == ""


@pytest.mark.parametrize(
    "command",
    [
        "git -C {repo} push origin fix/x",
        "git -C {repo} push -u origin fix/x",
        "git -C {repo} push origin HEAD",
        "git -C {repo} push",
        "git -C {repo} add -A && git -C {repo} push origin fix/x 2>&1",
    ],
)
def test_push_guard_turns_off_a_queued_merge_before_the_push(tmp_path, command):
    res, log = _push_guard(tmp_path, command, listed="12\n")
    assert res.returncode == 0, res.stderr
    assert "pr list -R LucasSantana-Dev/Lucky --head fix/x --state open" in log
    assert "pr merge 12 -R LucasSantana-Dev/Lucky --disable-auto" in log
    assert "run pr-automerge LucasSantana-Dev/Lucky 12" in res.stderr


def test_push_guard_lets_a_push_without_queued_merge_through(tmp_path):
    res, log = _push_guard(tmp_path, "git -C {repo} push origin fix/x")
    assert res.returncode == 0
    assert "pr merge" not in log


@pytest.mark.parametrize(
    "kwargs", [{"list_ok": False}, {"listed": "12\n", "merge_rc": "1"}]
)
def test_push_guard_blocks_when_it_cannot_turn_auto_merge_off(tmp_path, kwargs):
    res, _ = _push_guard(tmp_path, "git -C {repo} push origin fix/x", **kwargs)
    assert res.returncode == 2
    assert "BLOCK" in res.stderr


def test_push_guard_is_installed_and_registered():
    df = (REPO / "Dockerfile.agent-box").read_text()
    entry = (REPO / "config" / "agent-box" / "entrypoint.sh").read_text()
    settings = json.loads((REPO / "config" / "agent-box" / "settings.json").read_text())
    assert (
        "COPY config/agent-box/automerge-push-guard.sh "
        "/opt/agent-config/hooks/automerge-push-guard.sh" in df
    )
    assert "automerge-push-guard; do" in entry
    commands = [
        h["command"]
        for m in settings["hooks"]["PreToolUse"]
        if m["matcher"] == "Bash"
        for h in m["hooks"]
        if h["type"] == "command"
    ]
    assert "/home/agent/.claude/hooks/automerge-push-guard.sh" in commands


# --- pr-automerge thread replies (ADR 0042, amendment) --------------------

REVIEWED = "b" * 40  # the commit the bot reviewed; HEAD is a later push


def review_thread(tid, *logins, commit=REVIEWED, resolved=False):
    t = thread(*logins, resolved=resolved)
    t["id"] = tid
    for c in t["comments"]["nodes"]:
        c["originalCommit"] = {"oid": commit}
    return t


def pr_for_replies(*threads, commits=(REVIEWED, HEAD), more=False):
    pr = pr_with_threads(*threads, files=("src/x.ts",), more=more)
    pr["headRefOid"] = HEAD
    pr["commits"] = [{"oid": c, "authors": [{"login": OWNER}]} for c in commits]
    return pr


def _plan(pr, cfg, replies, issues=()):
    return gate.thread_replies(pr, cfg, list(issues), replies)


def test_thread_replies_resolve_a_fixed_bot_thread(cfg):
    pr = pr_for_replies(review_thread("T1", "cubic-dev-ai"))
    replies = [{"id": "T1", "fixed": True, "reply": "Fixed in the last commit."}]
    assert _plan(pr, cfg, replies) == (
        [],
        [{"id": "T1", "reply": "Fixed in the last commit.", "resolve": True}],
        {},
    )


def test_thread_replies_leave_a_dismissed_claim_open(cfg):
    pr = pr_for_replies(review_thread("T1", "coderabbitai"))
    replies = [{"id": "T1", "fixed": False, "reply": "The value is never null here."}]
    _, actions, _ = _plan(pr, cfg, replies)
    assert actions == [
        {"id": "T1", "reply": "The value is never null here.", "resolve": False}
    ]


@pytest.mark.parametrize(
    "commits",
    [
        (REVIEWED,),  # nothing pushed after the review
        ("c" * 40, HEAD),  # reviewed commit not in the PR (unknown)
        (REVIEWED, HEAD, "d" * 40),  # list does not end at the head
        (),
    ],
)
def test_thread_replies_skip_a_fix_that_is_not_pushed(cfg, commits):
    pr = pr_for_replies(review_thread("T1", "cubic-dev-ai"), commits=commits)
    if commits == (REVIEWED,):
        pr["headRefOid"] = REVIEWED
    replies = [{"id": "T1", "fixed": True, "reply": "Fixed."}]
    reasons, actions, skipped = _plan(pr, cfg, replies)
    assert (reasons, actions) == ([], [])
    assert "push first" in skipped["T1"]


def test_thread_replies_fail_closed_on_missing_oids(cfg):
    pr = pr_for_replies(review_thread("T1", "cubic-dev-ai", commit=None))
    pr["headRefOid"] = None
    pr["commits"] = [{"authors": [{"login": OWNER}]}, {"authors": [{"login": OWNER}]}]
    _, actions, skipped = _plan(pr, cfg, [{"id": "T1", "fixed": True, "reply": "x"}])
    assert actions == [] and "push first" in skipped["T1"]


def test_thread_replies_need_a_push_after_the_last_bot_comment(cfg):
    t = review_thread("T1", "cubic-dev-ai", "cubic-dev-ai")
    t["comments"]["nodes"][1]["originalCommit"] = {"oid": HEAD}  # re-review on HEAD
    pr = pr_for_replies(t)
    _, actions, skipped = _plan(pr, cfg, [{"id": "T1", "fixed": True, "reply": "x"}])
    assert actions == [] and "push first" in skipped["T1"]


def test_thread_replies_never_touch_owner_or_app_threads(cfg):
    pr = pr_for_replies(
        review_thread("T1", "cubic-dev-ai", OWNER),  # the owner joined
        review_thread("T2", "cubic-dev-ai"),
    )
    # An App outside the bot list: not human, but not the session's to answer.
    pr["reviewThreads"]["nodes"][1]["comments"]["nodes"][0]["author"] = {
        "__typename": "Bot",
        "login": "some-app",
    }
    replies = [
        {"id": "T1", "fixed": True, "reply": "x"},
        {"id": "T2", "fixed": True, "reply": "x"},
    ]
    _, actions, skipped = _plan(pr, cfg, replies)
    assert actions == []
    assert set(skipped) == {"T1", "T2"}
    assert all("bot-only" in why for why in skipped.values())


def test_thread_replies_refuse_a_human_thread_outright(cfg):
    pr = pr_for_replies(
        review_thread("T1", "cubic-dev-ai"), review_thread("T2", "someone")
    )
    reasons, actions, _ = _plan(pr, cfg, [{"id": "T1", "fixed": True, "reply": "x"}])
    assert actions == []
    assert any("another human" in r for r in reasons)


@pytest.mark.parametrize(
    "entry,key,why",
    [
        ({"id": "T9", "fixed": True, "reply": "x"}, "T9", "not an open thread"),
        ({"id": "T1", "fixed": True, "reply": "  "}, "T1", "empty reply"),
        ({"id": "T1", "fixed": True}, "T1", "empty reply"),
        ({"id": "T1;x", "reply": "x"}, "#0", "no valid thread id"),
        ({"id": 5, "reply": "x"}, "#0", "no valid thread id"),
        ("T1", "#0", "no valid thread id"),
    ],
)
def test_thread_replies_skip_bad_entries(cfg, entry, key, why):
    pr = pr_for_replies(review_thread("T1", "cubic-dev-ai"))
    _, actions, skipped = _plan(pr, cfg, [entry])
    assert actions == []
    assert why in skipped[key]


def test_thread_replies_skip_resolved_and_doubled_threads(cfg):
    pr = pr_for_replies(
        review_thread("T1", "cubic-dev-ai", resolved=True),
        review_thread("T2", "cubic-dev-ai"),
    )
    replies = [
        {"id": "T1", "fixed": True, "reply": "x"},
        {"id": "T2", "fixed": True, "reply": "first"},
        {"id": "T2", "fixed": False, "reply": "second"},
    ]
    _, actions, skipped = _plan(pr, cfg, replies)
    assert actions == []
    assert skipped == {"T1": "not an open thread of this PR", "T2": "named twice"}


@pytest.mark.parametrize(
    "reply",
    [
        "@claude fix the rest",
        "Fixed. cc @coderabbitai",
        "/review",
        "Fixed.\n  /ask why",
    ],
)
def test_thread_replies_skip_mentions_and_slash_commands(cfg, reply):
    pr = pr_for_replies(review_thread("T1", "cubic-dev-ai"))
    _, actions, skipped = _plan(pr, cfg, [{"id": "T1", "fixed": True, "reply": reply}])
    assert actions == [] and "mentions" in skipped["T1"]


def test_thread_replies_allow_plain_text_with_slashes(cfg):
    pr = pr_for_replies(review_thread("T1", "cubic-dev-ai"))
    reply = "Fixed in src/a.ts and the and/or check, see x @ line 3."
    _, actions, _ = _plan(pr, cfg, [{"id": "T1", "fixed": True, "reply": reply}])
    assert actions[0]["resolve"] is True


def test_thread_replies_resolve_only_on_a_real_true(cfg):
    pr = pr_for_replies(review_thread("T1", "cubic-dev-ai"))
    _, actions, _ = _plan(pr, cfg, [{"id": "T1", "fixed": "true", "reply": "x"}])
    assert actions == [{"id": "T1", "reply": "x", "resolve": False}]


def test_thread_replies_owner_reply_hands_the_thread_to_the_owner(cfg):
    """After a dismissed claim the thread holds the owner's reply: never answered again."""
    pr = pr_for_replies(review_thread("T1", "cubic-dev-ai", OWNER))
    _, actions, skipped = _plan(pr, cfg, [{"id": "T1", "fixed": True, "reply": "x"}])
    assert actions == [] and "bot-only" in skipped["T1"]


def test_thread_replies_cap_text_and_drop_dashes(cfg):
    pr = pr_for_replies(review_thread("T1", "cubic-dev-ai"))
    reply = "Fixed — the guard runs first–always. " + "y" * 3000
    _, actions, _ = _plan(pr, cfg, [{"id": "T1", "fixed": True, "reply": reply}])
    out = actions[0]["reply"]
    assert out.startswith("Fixed, the guard runs first, always. ")
    assert "—" not in out and "–" not in out
    assert len(out) <= 2000


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"state": "MERGED"}, "not open"),
        ({"isCrossRepository": True}, "fork"),
        ({"author": {"login": "someone"}}, "another human"),
    ],
)
def test_thread_replies_refuse_unsafe_prs(cfg, change, reason):
    pr = {**pr_for_replies(review_thread("T1", "cubic-dev-ai")), **change}
    reasons, actions, _ = _plan(pr, cfg, [{"id": "T1", "fixed": True, "reply": "x"}])
    assert actions == [] and any(reason in r for r in reasons)


def test_thread_replies_fail_closed(cfg):
    pr = pr_for_replies(review_thread("T1", "cubic-dev-ai"), more=True)
    ok = [{"id": "T1", "fixed": True, "reply": "x"}]
    assert "review threads not fully loaded" in _plan(pr, cfg, ok)[0]
    pr = pr_for_replies(review_thread("T1", "cubic-dev-ai"))
    assert _plan(pr, cfg, {"T1": "x"})[0] == ["replies file is not a JSON array"]
    assert gate.thread_replies(pr, cfg, None, ok)[0] == ["linked issues not loaded"]
    foreign = make_issue(author="someone")
    assert any("another human" in r for r in _plan(pr, cfg, ok, issues=[foreign])[0])


def test_open_threads_lists_ids_and_marks_bot_only(cfg):
    pr = pr_for_replies(
        review_thread("T1", "cubic-dev-ai"),
        review_thread("T2", "cubic-dev-ai", OWNER),
        review_thread("T3", "coderabbitai", resolved=True),
    )
    out = gate.list_open_threads(pr, cfg)
    assert [(t["id"], t["bot_only"]) for t in out] == [("T1", True), ("T2", False)]
    assert out[0]["comments"] == [{"author": "cubic-dev-ai", "body": "b"}]


def test_cli_thread_commands_need_an_allowlisted_repo():
    for cmd in ("open-threads", "thread-replies"):
        assert _cli_raw(cmd).returncode == 2
        assert _cli_raw(cmd, "--repo", "someone/else").returncode == 2


def _replies_file(tmp_path, replies):
    f = tmp_path / "replies.json"
    f.write_text(replies if isinstance(replies, str) else json.dumps(replies))
    return str(f)


def _threads_conn(*threads):
    return {"pageInfo": {"hasNextPage": False}, "nodes": list(threads)}


def _pushed_pr(**extra):
    commits = [{"oid": c, "authors": [{"login": OWNER}]} for c in (REVIEWED, HEAD)]
    return _gh_pr(commits=commits, **extra)


def _mutations(tmp_path):
    log = tmp_path / "mutations.log"
    return log.read_text().splitlines() if log.exists() else []


def _answer(tmp_path, replies, threads, env=None):
    return _automerge(
        tmp_path,
        "LucasSantana-Dev/Lucky",
        "7",
        "--replies",
        _replies_file(tmp_path, replies),
        prs={7: _pushed_pr()},
        threads=threads,
        env=env,
    )


def test_automerge_replies_resolve_then_queue(tmp_path):
    threads = _threads_conn(
        review_thread("T1", "cubic-dev-ai"), review_thread("T2", "coderabbitai")
    )
    replies = [
        {"id": "T1", "fixed": True, "reply": "Fixed, guard added."},
        {"id": "T2", "fixed": True, "reply": "Fixed too."},
    ]
    res, log = _answer(tmp_path, replies, threads)
    assert res.returncode == 0, res.stdout + res.stderr
    assert _mutations(tmp_path) == [
        "reply T1 Fixed, guard added.",
        "resolve T1 ",
        "reply T2 Fixed too.",
        "resolve T2 ",
    ]
    assert len(_merge_calls(log)) == 1
    assert "--squash --auto --match-head-commit" in _merge_calls(log)[0]


def test_automerge_dismissed_claim_stays_open_and_blocks_the_merge(tmp_path):
    threads = _threads_conn(review_thread("T1", "cubic-dev-ai"))
    replies = [{"id": "T1", "fixed": False, "reply": "Not reachable: x is checked."}]
    res, log = _answer(tmp_path, replies, threads)
    assert res.returncode == 1
    assert _mutations(tmp_path) == ["reply T1 Not reachable: x is checked."]
    assert "left open for the owner" in res.stdout
    assert "1 unresolved review thread(s)" in res.stdout
    assert _merge_calls(log) == []


def test_automerge_replies_never_post_on_a_pr_with_a_human_thread(tmp_path):
    threads = _threads_conn(
        review_thread("T1", "cubic-dev-ai"), review_thread("T2", "someone")
    )
    res, log = _answer(tmp_path, [{"id": "T1", "fixed": True, "reply": "x"}], threads)
    assert res.returncode == 1
    assert "replies refused: another human" in res.stdout
    assert _mutations(tmp_path) == []
    assert _merge_calls(log) == []


def test_automerge_does_not_resolve_when_the_reply_fails(tmp_path):
    threads = _threads_conn(review_thread("T1", "cubic-dev-ai"))
    res, log = _answer(
        tmp_path,
        [{"id": "T1", "fixed": True, "reply": "x"}],
        threads,
        env={"GH_REPLY_RC": "1"},
    )
    assert res.returncode == 1
    assert _mutations(tmp_path) == ["reply T1 x"]
    assert "failed, left open" in res.stdout
    assert "0 of 1 replies posted" in res.stdout
    assert _merge_calls(log) == []


def test_automerge_reports_a_failed_resolve(tmp_path):
    threads = _threads_conn(review_thread("T1", "cubic-dev-ai"))
    res, log = _answer(
        tmp_path,
        [{"id": "T1", "fixed": True, "reply": "x"}],
        threads,
        env={"GH_RESOLVE_RC": "1"},
    )
    assert res.returncode == 1
    assert "could not resolve it" in res.stdout
    assert "1 of 1 replies posted" in res.stdout
    assert _merge_calls(log) == []


@pytest.mark.parametrize("content", ["not json", "[1] [2]", "x" * 70000, None])
def test_automerge_bad_replies_file_posts_nothing(tmp_path, content):
    path = (
        str(tmp_path / "missing.json")
        if content is None
        else _replies_file(tmp_path, content)
    )
    res, log = _automerge(
        tmp_path,
        "LucasSantana-Dev/Lucky",
        "7",
        "--replies",
        path,
        prs={7: _pushed_pr()},
        threads=_threads_conn(review_thread("T1", "cubic-dev-ai")),
    )
    assert res.returncode == 1
    assert _mutations(tmp_path) == []
    assert _merge_calls(log) == []


def test_automerge_lists_open_threads(tmp_path):
    threads = _threads_conn(
        review_thread("T1", "cubic-dev-ai"),
        review_thread("T2", "coderabbitai", resolved=True),
    )
    res, log = _automerge(
        tmp_path,
        "LucasSantana-Dev/Lucky",
        "7",
        "--threads",
        prs={7: _pushed_pr()},
        threads=threads,
    )
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert [(t["id"], t["bot_only"]) for t in out] == [("T1", True)]
    assert _mutations(tmp_path) == [] and _merge_calls(log) == []


@pytest.mark.parametrize(
    "args",
    [
        ("LucasSantana-Dev/Lucky", "7", "--replies"),
        ("LucasSantana-Dev/Lucky", "7", "--threads", "x"),
        ("LucasSantana-Dev/Lucky", "7", "--admin", "x"),
        ("--sweep", "--replies", "x"),
    ],
)
def test_automerge_bad_thread_arguments_do_nothing(tmp_path, args):
    res, log = _automerge(tmp_path, *args, prs={7: _pushed_pr()})
    assert res.returncode != 0
    assert _mutations(tmp_path) == [] and _merge_calls(log) == []


def test_automerge_only_mutations_are_reply_and_resolve():
    src = AUTOMERGE.read_text()
    mutations = [ln for ln in src.splitlines() if "mutation(" in ln]
    assert [m.split("=", 1)[0] for m in mutations] == [
        "REPLY_MUTATION",
        "RESOLVE_MUTATION",
    ]
    api_calls = [
        ln.strip()
        for ln in src.splitlines()
        if "gh api" in ln and not ln.lstrip().startswith("#")
    ]
    assert len(api_calls) == 3, api_calls
    assert all("gh api graphql" in c for c in api_calls)


def test_discord_session_answers_threads_through_pr_automerge():
    conf = REPO / "config" / "agent-box"
    discord = json.loads((conf / "discord-channel-settings.json").read_text())
    assert "Bash(gh api*)" in discord["permissions"]["deny"]
    assert "Bash(gh * api*)" in discord["permissions"]["deny"]
    rules = (conf / "discord-channel.md").read_text()
    assert "pr-automerge <owner/repo> <pr-number> --threads" in rules
    assert "--replies /tmp/discord-scratch/thread-replies.json" in rules
