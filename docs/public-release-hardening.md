# Public Release Hardening Guide

This runbook prepares the repository for public visibility while keeping production credentials private.

## Goals

- Keep only public-safe configuration and docs in git.
- Rotate all sensitive credentials before publication.
- Rewrite git history to remove historical sensitive artifacts.
- Enforce continuous secret and identity hygiene in pre-commit and CI.

## 1) Pre-Release Safety Checkpoint

Run:

```bash
./scripts/security/pre-release-checkpoint.sh
```

This creates:

- Backup branch and tag at current `HEAD`
- Mirror clone backup under `backups/public-release/<timestamp>/`
- Credential rotation inventory generated from `.env.example`

## 2) Credential Rotation (Required)

Rotate and validate cutover for:

- Cloudflare API and tunnel tokens
- Discord webhooks (`ALERTMANAGER_DISCORD_WEBHOOK`, `WATCHDOG_DISCORD_WEBHOOK`, `WUD_DISCORD_WEBHOOK_URL`, `UPDATE_DISCORD_WEBHOOK_URL`)
- Sentry auth token
- GitHub and Docker Hub tokens
- Tinyauth secret + GitHub OAuth client credentials
- Any additional API keys used by custom services

Only after validation, revoke old credentials.

## 3) Sanitize Working Tree

Before opening the repository:

```bash
./scripts/security/secret-gate.sh
./scripts/security/public-safety-gate.sh
```

## 4) Rewrite Git History

Prerequisites:

- Clean working tree
- `git-filter-repo` installed
- Safety checkpoint created

Run:

```bash
./scripts/security/rewrite-history.sh
```

Push when validated:

```bash
./scripts/security/rewrite-history.sh --push --remote origin
```

After force-push, collaborators must re-clone.

## 5) Ongoing Policy

- Secrets live only in local ignored files (`.env`, local secret files, decrypted secret outputs).
- Public docs/config examples must stay pseudonymized.
- CI and pre-commit gates are mandatory for all pull requests.
