# ADR-0021: Skill Header Constraint Enforcement — Ritual-First, Escalate to Examples

**Status:** Accepted
**Date:** 2026-06-18

## Context

The `grill-with-options` skill requires `AskUserQuestion` headers ≤12 characters (UI chip constraint). Over two eval iterations, the model violated this rule once per iteration:

- Iteration 1: `Orchestration` (13 chars)
- Iteration 2: `Observability` (13 chars)

Pattern: the model self-reports the violation after generating the header — proving it retrieves the constraint at evaluation time, not at generation time. Root cause is **write-time deprioritization**, not ignorance. The model prefers domain-accurate words; the constraint check happens post-hoc.

Two fix strategies evaluated:

| Strategy | Approach |
|----------|----------|
| B-only | Add pre-write count ritual + one counter-example (Observability → Monitoring) |
| F (combined) | B-only + move constraint first + 4+ counter-examples + second example shape |

Decision-critic (Opus, artifact-only) returned NEEDS_REVISION: both options add comprehension-time text to an execution-time problem. Recommended testing B-only first — lowest-cost gate before committing to F.

## Decision

Apply **B-only first**. The pre-write ritual ("Before finalizing any header, count its characters") inverts the generation order: check before commit, not after. If B-only achieves ≥90% compliance in the next eval, adopt it. If it fails, escalate to F and plan a fallback (hardcoded approved-header set or constrained synonym list).

The critic's key objection — "ritual language is comprehension-time, not generation-time" — is correct but untested. The only way to resolve it is empirically. B-only is the minimal test.

## Alternatives Considered

- **Option A (more counter-examples only):** Rejected. Model already saw Orchestration as a counter-example and still chose Observability. Single-example generalization doesn't hold across deployment domain words.
- **Option F (combined fix):** Deferred pending B-only result. If B fails, F becomes the default with a hardcode fallback.
- **Hardcode headers (pre-approved list):** Not yet attempted. Reserve as final fallback if B and F both fail.
- **No change:** Rejected. The violation is consistent across evals; it will persist.

## Consequences

**Positive:**
- Minimal edit — one ritual phrase + one counter-example.
- Preserves SKILL.md readability (doesn't inflate instruction length).
- Creates clear escalation path: B → F → hardcode.

**Negative:**
- May not work. The ritual is a comprehension cue; deprioritization at generation time may override it.
- Requires another eval iteration to confirm.

**Neutral:**
- The deployment eval is the uniquely hard scenario. Architecture and feature evals pass 100% without this fix.

## Revisit When

- B-only eval-deployment passes → adopt and close.
- B-only fails → escalate to F immediately; add hardcode fallback plan.
- A third domain word beyond Orchestration/Observability appears → the set of violators is larger than assumed; may require hardcoded list earlier.
