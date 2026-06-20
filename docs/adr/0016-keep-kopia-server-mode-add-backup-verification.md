# ADR-0016: Keep kopia server-mode; add backup verification (don't migrate the tool)

- **Status:** Accepted
- **Date:** 2026-05-29

## Context

kopia (offsite encrypted backups → Backblaze B2, server mode in a container) had
a multi-month silent outage: an invalid CLI flag crash-looped the container 4861×
and nothing alerted. Two fixes already shipped: PR #164 (remove the flag) and
PR #165 (Prometheus alerts for kopia container down / crash-loop).

That raised a deeper question (`/research-and-decide`): is **kopia server-mode**
the right backup approach, or should we migrate to **kopia CLI + systemd-timer**
or **restic**? And — separately — how do we ensure backups are actually
*succeeding and restorable*, not just that the process is up?

## Decision

**Two decisions:**

1. **Keep kopia server-mode. Do NOT migrate the tool or invocation mode.**
2. **Add backup *verification*, effort-ranked**, because "container up" ≠
   "backups valid".

A critic review flipped an initial lean toward CLI-timer migration. Rationale:
the incident was a **config-flag bug (now fixed) + an alerting gap (now closed)**,
not an inherent server-mode flaw. There is **no demonstrated server-mode-specific
friction** beyond this one bug — no pull signal for a migration. CLI+systemd-timer
would only trade the (now-alerted) crash-loop vector for *no automatic retry*
semantics; restic costs a full re-backup (different repo format) for no documented
benefit. kopia server is just another long-lived daemon in the stack; once
observability covers it (#165 + freshness below), it needs no special treatment.

**Verification roadmap (priority order):**
1. **Enable B2 Object Lock (30-day immutability)** on the kopia bucket — highest
   ROI, ~$0; guards against ransomware / credential-leak deletion. *Operator
   action (B2 console).*
2. **Snapshot-freshness alert** — distinct from #165's container-health alerts:
   catches "container up but no snapshot created in 24–48h". kopia 0.21.x exposes
   no stable Prometheus snapshot metric (feature PRs unmerged), so: cron
   `kopia snapshot list --json` → write a node-exporter **textfile** metric
   (last-snapshot unix ts) → Prometheus alert on `time() - metric > 48h`.
3. **`kopia snapshot verify --verify-files-percent=1` daily** — cheap
   bit-rot/corruption sampling (~$1/TB/mo egress). After #2 is stable.

## Alternatives considered

- **kopia CLI + systemd-timer** — rejected: no pull signal; trades crash-loop
  (now alerted) for no-retry; loses nothing we use but gains nothing material.
  Zero-migration, so cheap to revisit if server-mode friction appears.
- **restic + timer** — rejected: full re-backup (different repo format), manual B2
  lifecycle + forget/prune, same observability gap; switching off a now-working
  tool on the basis of a config bug is unjustified.
- **borgbackup / autorestic** — rejected: Borg 2.x B2 support immature (2026);
  autorestic is multi-backend orchestration overhead a single host doesn't need.
- **Monthly automated restore test** — deferred: enterprise-grade ceremony a solo
  operator won't sustain; Object Lock + freshness + integrity sampling cover the
  realistic failure modes. Revisit if >1TB critical data or a restore incident.

## Consequences

- No migration risk/effort; kopia server-mode stays, now fixed + alerted.
- After the roadmap: silent-failure (freshness), deletion (Object Lock), and
  bit-rot (verify) gaps all closed at low effort.
- Object Lock blocks deleting snapshots within the retention window — intentional
  (ransomware defense); document so an urgent space-reclaim isn't a surprise.
- The Prometheus/Alertmanager stack is itself a SPOF for alerting — accepted for a
  solo homelab (Grafana is checked manually); not production-grade paging.

## Revisit when

- **Tool/mode:** ≥2 distinct kopia *daemon* crashes (not config bugs) in a month,
  a memory leak / CPU spin, kopia project abandonment, or a breaking B2 change →
  reconsider CLI-timer (zero-migration) or restic.
- **Restore testing:** a restore reveals a gap, critical data exceeds ~1TB, or a
  second host / failover need appears → add the monthly restore test.
- **Freshness alert:** if it never fires in 3 months, re-tune or retire.

## Update (2026-06-20) — offsite same-disk gap addressed (#266)

The "offsite → Backblaze B2" target named in this ADR's Context was the *intended*
design but was **deferred and never wired**, so in practice the repo was
**same-disk-only**, leaving host-disk-failure uncovered. Rather than keep waiting on
the B2 tier, an **rsync mirror of the encrypted repo to a second host/disk** now ships:
`scripts/maintenance/kopia-offsite-sync.sh` + `kopia-offsite-sync.timer` (daily),
target set via `KOPIA_OFFSITE_TARGET` in `.env` (operator picks a host/disk).
Recovery depends on `KOPIA_REPO_PASSWORD`, now kept off-host in SOPS (#272). The
B2/S3 tier (`KOPIA_S3_*`) remains deferred as a future second offsite layer. See
docs/backup.md §Offsite Disaster Recovery.
