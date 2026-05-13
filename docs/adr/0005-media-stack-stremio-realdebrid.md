# ADR 0005: Media stack — keep Stremio + RealDebrid, defer *arr migration

- **Status:** Proposed (conditional) — promotes to Accepted once all pre-conditions are complete (deadline 2026-05-27)
- **Date:** 2026-05-13
- **Deciders:** Lucas (solo operator)
- **Supersedes:** —
- **Superseded by:** —
- **Related:** [`.claude/plans/homepage-customization-2026-05-13.md`](../../.claude/plans/homepage-customization-2026-05-13.md), [`.claude/plans/dashboard-gap-analysis.md`](../../.claude/plans/dashboard-gap-analysis.md)

---

## Context

The Reddit r/selfhosted dashboard inspirations that motivated the Homepage redesign featured ~12 *arr / Plex services (Sonarr, Radarr, Prowlarr, Seerr, Tautulli, qBittorrent, sabnzbd, Watcharr, Wizarr, Bazarr, Plex, Immich). Before designing dashboard sections around the current stack, we needed to settle a longer-running question: **is Stremio still the right primary media surface, or should we migrate to a Plex/Jellyfin + *arr stack?**

The decision is forcing because:

- Phase 2 of the Homepage redesign will commit dashboard sections, widget API keys, and CSS layout to a particular topology.
- Disk pressure is real: **163 GB free / 468 GB total** on the host. A media library would eat most of that within a year.
- RealDebrid introduced filename-based filtering in May 2026 that removes ~50% of historically-available links[^3] — flagged in community sources as a possible end-of-era for the Stremio+RD model.
- We've never explicitly written down *why* we run Stremio, so the choice keeps getting re-litigated by every "should we add Plex?" thought.

## Decision

**Keep Stremio Server + RealDebrid as the primary media stack. Reject *arr migration for the next ~6 months. Reject Plex permanently in favor of Jellyfin should we ever migrate.**

This decision is **binding only after** the pre-conditions in the next section are satisfied. Without them, the decision is reactive and unaccountable per the Phase 2 critic verdict.

### Pre-conditions (must complete within 2 weeks of this ADR; tracked as separate tasks)

1. **Verify exit path:** spend ~2 hours testing AllDebrid as a drop-in for RealDebrid inside Stremio + Torrentio / MediaFusion. Document the swap procedure. If incompatible, this ADR loses one of its core assumptions and must be re-opened.
2. **Wire monitoring:**
   - Gatus health check for the Stremio Server HTTP endpoint (already running, just needs a check).
   - Cron job that probes 5–10 popular-title searches against the active Stremio addon weekly; alert via Discord if >1 fails.
   - Disk usage alert at 70% and 85% (currently 60% — gives weeks of warning, not days).
3. **Pre-stage a fallback addon:** configure MediaFusion (or Comet) alongside Torrentio inside Stremio. Don't wait for Torrentio to fail to discover the fallback procedure.
4. **Schedule the Restic backups** (backlog B1, already deferred too long). Without scheduled backups, the disk-pressure analysis underlying this ADR can't be trusted.

If any pre-condition fails to complete in 2 weeks, this ADR auto-degrades to "Proposed" and Phase 4 of the Homepage plan is blocked.

## Alternatives considered

### A. Plex + *arr stack — **rejected**

- Plex Pass: USD 6.99/mo or USD 249.99 lifetime (April 2025 hike from USD 119.99; +108% one-time)[^1].
- Remote streaming now gated behind separate Remote Watch Pass (USD 1.99–2.99/mo)[^1].
- All feature-parity wins (4K HW transcode, HDR, family management) are now matched by Jellyfin for $0[^2].
- Conclusion: Plex's only remaining moat is family-share UX polish, which doesn't justify the lifetime premium for solo + occasional family.

### B. Jellyfin + *arr stack — **rejected for now, viable in 6+ months**

The genuinely competitive alternative. Reasons it loses today:

- **Disk:** 163 GB free vs. 360–600 GB/yr expected library growth. Requires a 2 TB external HDD purchase (~USD 70–80) just to be feasible.
- **Setup cost:** ~16 hours of focused work (Jellyfin install, Sonarr/Radarr/Prowlarr/Seerr/Bazarr config, TRaSH-Guides custom formats, Recyclarr automation, indexer pool curation including FlareSolverr for Cloudflare-blocked sites).
- **Ongoing tuning:** weekly indexer pool maintenance, VIP rotation, quality-profile adjustment.
- **Risk posture:** for a Brazilian residential ISP, public-tracker traffic is more legible to DPI than HTTPS debrid. (The critic correctly noted this risk is tertiary, not primary — but it's still net-positive on Stremio's side.)

Becomes the winner if: family-share grows beyond "occasional," RealDebrid degrades materially, or we acquire a 2 TB+ disk for unrelated reasons.

### C. Stremio + self-hosted addon (Knightcrawler / MediaFusion / Comet) — **partially adopted**

We will run **MediaFusion or Comet alongside Torrentio** as a fallback (see pre-condition #3). Not a replacement — an insurance policy against Torrentio's ~5–10% annual downtime.

### D. Hybrid (Stremio for discovery, Jellyfin for playback) — **rejected**

Combines the disk cost of Jellyfin with the brittleness of Stremio. Adds operational complexity without resolving either failure mode. The critic's analysis confirmed this is incoherent.

### E. Stay on Stremio + RealDebrid — **accepted (with reservations)**

- Cost: ~EUR 50/yr (RD subscription) + ~zero infrastructure.
- Footprint: 36.5 MiB RAM, 0.06% CPU, 0 GB disk growth.
- Exit cost: low if AllDebrid drop-in works (pre-condition #1 verifies this).
- Risks: addon brittleness, RealDebrid policy creep, no family-scale headroom — all bounded and monitorable per pre-conditions.

## Consequences

### Positive

- Zero net new infrastructure debt this quarter; Homepage Phase 2 can proceed without redesigning sections around a media library that doesn't exist yet.
- 163 → 0 GB disk runway is preserved for the things actually growing (Nextcloud, Forgejo, agent-logs, langfuse).
- ~16 hours of *arr stack setup time stays available for higher-value work (audit-deep remediation tasks #8–#14).
- Family-share remains adequate for current usage patterns (1 primary + occasional secondary viewer).

### Negative

- Continued exposure to Torrentio outages (~5–10% annual downtime). Mitigated by the MediaFusion/Comet fallback (pre-condition #3) and by accepting that family-share is "best-effort," not SLA-bound.
- Continued exposure to RealDebrid policy changes. We're betting the May 2026 filter changes are not the start of a terminal slide; if they are, the 6-month revisit catches it.
- Single-debrid dependency. Pre-condition #1 verifies a drop-in exit, but we have not actually exercised it.
- We're choosing simplicity-now over building muscle on the *arr stack. If we ever migrate, setup cost is paid in full at that future point, not amortized.

### Neutral

- Dashboard layout (Homepage Phase 2) will omit the entire *arr / Plex / qBittorrent section. This shrinks visual density vs. the inspiration screenshots but matches our actual surface area.
- Family-share UX stays Stremio-class (functional, not polished). Acceptable for now.

## Revisit triggers — operationalized

Replaces the original vague "revisit in 6 months" language. Any one of the following triggers a formal re-open of this ADR:

| # | Trigger | Measurement | Threshold |
|---|---------|-------------|-----------|
| T1 | Torrentio (or active primary addon) uptime drops | Gatus uptime tracking, monthly | <95% in any calendar month |
| T2 | RealDebrid stream-search failure rate | Weekly cron that probes 10 popular titles | >2 failures (>20%) in any week, persisting 2 consecutive weeks |
| T3 | Disk pressure on host | Existing Prometheus node-exporter | Free space <60 GB (current is 163 GB) |
| T4 | RealDebrid policy change | Manual scan of r/RealDebrid, RD status page | Any announcement adding *new* content classes to the filter beyond the May 2026 baseline |
| T5 | Family-share usage grows | Track simultaneous-stream events (Gatus / Stremio Server logs) | >3 simultaneous streams observed in any month, OR >1 viewer becomes daily |
| T6 | An external 2 TB+ disk arrives on the host | physical | Disk mounted, formatted, ≥1 TB free for media |
| T7 | Scheduled checkpoint | Calendar reminder | 2026-11-13 (6 months from this ADR), regardless of T1–T6 state |

The earlier checkpoint at 2026-07-13 (per critic's recommendation) is a softer review: just answer "are we on track for any of T1–T5?" If yes, escalate.

## Implementation tasks (pilot scope from Phase 3)

- [ ] Test AllDebrid + Torrentio compatibility; document swap procedure (pre-condition #1)
- [ ] Add Gatus health check for Stremio Server endpoint (pre-condition #2)
- [ ] Cron `lucky-external-apis.sh`-style script for RealDebrid title probe; Discord alert via `notify.sh` (pre-condition #2)
- [ ] Disk-usage alerts in Prometheus / Alertmanager at 70% and 85% (pre-condition #2)
- [ ] Configure MediaFusion or Comet in Stremio alongside Torrentio (pre-condition #3)
- [ ] Schedule Restic backups (B1 from May 3 backlog) (pre-condition #4)
- [ ] Calendar reminder for 2026-07-13 (soft check) + 2026-11-13 (hard revisit)

Each is small enough for a stand-alone PR. All seven combined are <1 working day.

## Notes

This ADR closes a question that had been re-litigated without a written answer for ~6 months. The Phase 2 critic verdict (`/research-and-decide` workflow, 2026-05-13) is recorded by reference: the decision is accepted *with* the amendments the critic surfaced, not without them.

[^1]: Plex Pass 2025–26 pricing changes: https://bytesized-hosting.com/guides/plex-2025-slash-2026-changes-what-seedbox-users-need-to-know/ and https://support.plex.tv/articles/201751006-plex-pass-feature-overview/
[^2]: Jellyfin feature parity with Plex (family sharing): https://www.xda-developers.com/jellyfin-comes-very-close-to-plex-in-family-friendly-features/ and https://www.homedock.cloud/blog/self-hosting/plex-vs-jellyfin-2026/
[^3]: RealDebrid May 2026 filtering / enforcement update: https://store.elfhosted.com/blog/2026/05/12/real-debrid-filtering-may-2026/ and https://troypoint.com/new-report-details-rise-and-fall-of-real-debrid-may-2026-update/
