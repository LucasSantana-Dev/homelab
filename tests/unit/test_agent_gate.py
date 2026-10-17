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
SCRATCH = "/tmp/agent-run.Ab3dEf9h"


@pytest.fixture
def cfg():
    # Pin Phase 1 so scoring tests do not follow the live auto_merge flag.
    c = gate.load_config(CONFIG)
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
        " telemetry.test.ts.commitmsg, renamed.ts, a.ts, b.ts and 3 more"
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
    assert len(after_run) == 1, after_run
    assert lines[after_run[0] + 1] == 'SCRATCH=""'


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
