# ADR-0015: The hotfix lane is reserved for active incidents, not long-standing broken features

- **Status:** Accepted
- **Date:** 2026-05-29

## Context

The `kopia` offsite-backup container was found crash-looping (4861 restarts,
exit 1) on an invalid CLI flag (`--without-password=false`). The fix is one line.
The question was the **ship path**: `hotfix` (commit to `main`, tag, deploy now,
bypassing the `release` branch) vs the normal `PR → release → /release-cut →
deploy` flow.

The instinct was to hotfix because "backups are down" reads as severe. A
`/research-and-decide` critique flipped that:

- kopia had **4861 restarts spanning its entire deployed life** — it has *never*
  worked. Offsite backups have been down for months, undetected (no alerting).
- "Down for months, never once worked" makes the urgency framing **false**: the
  marginal cost of waiting one normal release cycle is ~0 against months of
  silent failure.
- kopia is **isolated** — nothing `depends_on` it, it blocks no other service's
  startup (verified). So it is a P2 broken-feature, not a P0 incident.
- Bypassing `release` creates DAG debt (release is ahead of main; a hotfix on
  main risks unintended cherry-picks and a messy reconcile).

## Decision

Ship the kopia fix via the **normal `PR → release` flow** (Option B), not a
hotfix.

Generalising the rule: **the hotfix lane (bypassing `release`) is reserved for
*active* incidents** — data loss happening now, the server unable to boot/serve,
or a security exposure under active exploitation. A feature that has been broken
for a long time without active harm does **not** qualify, however important the
feature is (backups included). "Important" ≠ "urgent"; only *active harm* + *time-
sensitivity* justify bypassing the release branch.

## Alternatives considered

- **A. hotfix** — rejected: no active harm; bypass creates DAG debt; mints a tag
  immediately after v2.5.1 for no time-saving benefit.
- **C. fold-into-next-cut** — effectively the same as B here (nothing else pending
  on `release`); B with an explicit deploy is cleaner.

## Consequences

- kopia stays broken until the next `/release-cut` + deploy. Acceptable: it has
  been broken for months; the marginal delay is negligible.
- The release DAG stays clean; the fix reaches prod via the canonical path.
- A reusable severity gate now exists for future "should I hotfix this?" calls.

## Revisit when

- An incident shows **active** data loss/corruption, server-down, or live security
  exposure — then the hotfix lane is the correct, intended tool.
- Separately (out of scope here, flagged by the critique): backups failed
  **silently for months**. The real latent risk is the **absence of alerting on
  backup health**, not the flag. Worth its own decision (kopia server-mode +
  alerting vs alternatives).
