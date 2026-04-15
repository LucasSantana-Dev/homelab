---
status: proposed
created: 2026-04-15
owner: lucassantana
pr:
tags: security,audit-p0
---

# script-secret-hygiene

## Goal
Remove plaintext DB and MCP passwords from scripts/maintenance/recover-lucky-db.sh and update-containers.sh. Rotate leaked values.

## Context
Audit flagged DB_PASSWORD, FORGE_MCP_BASIC_AUTH_PASSWORD, FORGE_MCP_ADMIN_PASSWORD embedded inline.

## Approach
1. Rotate each credential in source systems.
2. Move to .env (already gitignored); source it in each script.
3. Scrub git history if commits exposed them (defer; depends on leak scope).
