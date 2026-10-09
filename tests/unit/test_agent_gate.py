"""Tests for scripts/agent-tasks/agent_gate.py: the 4-pillar merge gate
(size, impact, value, security) and the issue picker for the agent loop."""

import importlib.util
import json
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


@pytest.fixture
def cfg():
    return gate.load_config(CONFIG)


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
        "files": [{"path": p} for p in files],
        "additions": lines,
        "deletions": 0,
        "closingIssuesReferences": [{"number": n} for n in closes],
        "statusCheckRollup": [{"conclusion": checks, "status": "COMPLETED"}],
        "comments": [{"author": {"login": c}} for c in comments],
        "reviews": [{"author": {"login": r}} for r in reviews],
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
    assert out == {"issue": None, "skipped": {"7": "agent PR already open"}}


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
    assert out["decision"] == "owner-review"


def test_cli_get_merges_repo_overrides():
    assert (
        _cli(
            "get", "--repo", "LucasSantana-Dev/homelab", "--key", "base"
        ).stdout.strip()
        == "release"
    )
    assert _cli("get", "--key", "auto_merge").stdout.strip() == "false"


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


def test_select_counts_agent_branch_without_closing_ref(cfg):
    out = gate.select([make_issue(number=9)], [{"headRefName": "agent/issue-9"}], cfg)
    assert out["skipped"] == {"9": "agent PR already open"}


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
            f'source "{lib}"; claude_cmd LucasSantana-Dev/Lucky /w "fix it; rm -rf /" agent/issue-7',
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


@pytest.mark.parametrize(
    "branch", ["", "main", "release", "agent/x:main", "agent/+x", "agent/x y"]
)
def test_claude_cmd_refuses_non_agent_branch(branch):
    lib = REPO / "scripts" / "agent-tasks" / "agent-loop-lib.sh"
    res = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{lib}"; claude_cmd LucasSantana-Dev/Lucky /w p "$1"',
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
