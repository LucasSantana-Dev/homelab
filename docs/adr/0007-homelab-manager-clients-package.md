# ADR 0007 — `homelab_manager.clients` package: one owner per external dependency

- **Status:** Accepted
- **Date:** 2026-05-14
- **Deciders:** Lucas Santana
- **Supersedes:** —
- **Related:** audit-deep H6+M1 (hardening of `services/status.py:get_service_logs`), audit-deep v2 M4 (`core/config.py` coverage)

> ADR numbering note: this file is `0007-` because `0006-wol-via-shell-endpoint-not-gui-container.md` exists. The R1 meta-plan referenced "ADR 0008" — corrected here. R2/R3 will be 0008/0009.

## Context

The `homelab_manager` Python package grew organically. Two patterns showed up
in multiple services with subtle behavioural drift:

1. **Docker SDK client construction.** `services/status.py` called
   `docker.from_env()` and let the exception propagate; `services/health.py`
   wrapped it in try/except and stored `None` on failure. Tests mocked at two
   different paths.
2. **`docker compose` subprocess invocations.** `services/status.py:get_service_logs`
   (after audit-deep H6+M1) had a registry-allowlist check + line clamping +
   stderr-scrubbing. `services/updates.py` had 6 nearly-identical subprocess
   call sites with **none** of that hardening — error handlers echoed
   `{e.stderr}` directly, a latent M1 violation.

The drift was not strictly a bug, but every audit-deep round had to re-check
each call site individually, and any future hardening (e.g. a timeout, a new
denylist) would need to be applied in N places without a single owner.

## Decision

Introduce `homelab_manager.clients` as the package's "infrastructure layer":

- `clients/docker_client.py` — `DockerClientFactory` (lazy singleton) + module-
  level `get_docker_client()` accessor. Returns `Optional[DockerClient]` —
  `None` on daemon failure, mirroring the safer of the two pre-R1 patterns.
- `clients/compose_cli.py` — `ComposeCLI.run([...])` for arbitrary
  `docker compose <args>` invocations, plus `ComposeCLI.logs(service, lines)`
  that bakes in the audit-deep H6 registry allowlist + M1 stderr scrub +
  `clamp_lines()` helper.
- `core/errors.py` — `scrub_subprocess_error(exc, *, context)` shared helper
  so every error path produces a safe-to-echo string instead of raw stderr.

`services/status.py.get_service_logs` collapses to a 1-line wrapper over
`ComposeCLI.logs()`. `services/updates.py`'s 6 subprocess sites become 6
`self._compose.run([...])` calls and all 4 error handlers use
`scrub_subprocess_error()`.

Tests mock at the canonical seam
(`homelab_manager.clients.docker_client.docker`) and reset the factory
singleton per-test via an `autouse` fixture.

## Alternatives considered

**A. Leave each service as-is, just copy the H6+M1 hardening into `updates.py`.**
   Cheapest. Rejected because the next audit round would need to re-verify each
   site again, and the drift gradient only grows over time.

**B. Use a thin facade (a single `HomelabClients` class with both
   docker + compose methods).**
   One-class API is conceptually neat but fights testability: mocking the
   facade requires mocking both methods even when a test only cares about one.
   Two narrow classes win on test surface area.

**C. Move to the upstream Docker SDK's compose integration**
   (`docker.compose.…`). Rejected: it's experimental and would tie us to a
   library version constraint the deployment pipeline doesn't currently
   enforce. The subprocess approach is the actual deployment contract.

## Consequences

### Positive

- **Single mock seam per resource.** Test files patch
  `homelab_manager.clients.docker_client.docker` and reset the factory; no
  more per-service mock-path archaeology.
- **Latent M1 violation closed.** `updates.py` no longer leaks subprocess
  stderr (`{e.stderr}` → `scrub_subprocess_error(exc, context=...)`).
- **Coverage gains.** Overall package coverage 81% → 86%; `core/config.py`
  62% → 100% (closes audit-deep v2 M4 / task #22); new modules each at 100%.
- **Future hardening is one-file.** Adding a timeout, a denylist, or a metrics
  hook to `docker compose` invocations only touches `compose_cli.py`.
- **R2 consumes this directly.** `scripts/maintenance/` becomes thin wrappers
  over the new clients, removing a class of `sys.path.insert` + duplicate-logic
  smells.

### Negative

- **Behaviour change in `services/status.py.__init__`.** Pre-R1, a Docker
  daemon failure raised at construction; now `self.docker_client` is `None`.
  Downstream methods are already guarded by try/except → outcome is the same
  ("unknown" status), but a caller that relied on the constructor raising
  would now see a successful object that silently fails later. No such
  caller exists in the current codebase (verified via grep); if one appears,
  add an `is_available()` check explicitly.
- **One extra import per service.** Trivial; offset by net LOC reduction
  (~30 lines deleted across `status.py` + `updates.py`).
- **Singleton state to manage in tests.** Mitigated by an `autouse` fixture
  in each affected test file that calls `DockerClientFactory._instance = None`
  before and after each test.

### Neutral

- **No public API change.** Every `Manager` class keeps its method names and
  signatures. External callers (CLI, scripts/maintenance, tests) are
  unaffected by the internal restructure.

## Revisit when

- A second host joins the homelab (multi-host orchestration) → consider
  moving to the SDK's full async API rather than subprocess.
- The Docker SDK gets a stable, non-experimental compose integration that
  obviates the subprocess path.
- `clients/` grows beyond 3 modules (e.g. someone adds a `git_cli.py`) →
  re-evaluate whether infra-layer code should split further.

## Validation evidence

- Suite: 233 → 284 passed (+51); 7 skipped (unchanged).
- Coverage: 81% → 86% overall; key modules:
  - `core/config.py` 62% → 100%
  - `clients/docker_client.py` 100% (new)
  - `clients/compose_cli.py` 100% (new)
  - `core/errors.py` 100% (new)
  - `services/status.py` 98% (unchanged)
  - `services/updates.py` 97% → 94% (new error branches, ≥90% gate met)
- Security contracts preserved: 11/11 tests in `TestGetServiceLogs` pass
  unchanged against the wrapper implementation (audit-deep H6+M1).
- Grep gates passed:
  - `grep -rE "subprocess\.run\(" homelab_manager/services/` → 0
  - `grep -rE "docker\.from_env\(" homelab_manager/services/` → 0
