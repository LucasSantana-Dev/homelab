# ADR-0017: Portainer keeps read-write docker.sock (accepted risk; socket-proxy is theater here)

- **Status:** Accepted
- **Date:** 2026-05-29

## Context

A security audit flagged that **Portainer** mounts `/var/run/docker.sock`
**read-write** (`compose/core.yml`), while every other socket consumer in the
stack (homepage, what's-up-docker, agent-box, cadvisor) mounts it `:ro`. The
audit suggested changing Portainer to `:ro`.

That suggestion is **mechanically wrong**: Portainer is a Docker *management* UI
— it creates/starts/stops/removes containers and deploys stacks. A read-only
socket strips the write API and reduces Portainer to a viewer that can't manage
anything. So `:ro` is not a valid option for this container.

The real fork was: **keep read-write** vs **docker-socket-proxy**
(tecnativa/docker-socket-proxy — a filtering proxy exposing only a subset of the
Docker API).

## Decision

**Keep Portainer's docker.sock read-write. Do not add a socket-proxy.**

Threat model for this host: single-host, **Tailscale-only** (no public ingress;
ports loopback/`${BIND_IP}`-bound), **solo trusted operator**, Portainer gated
behind Tailscale + its own auth.

A socket-proxy is **security theater** in this model:
- The proxy itself still needs rw socket access — it moves the trust boundary,
  doesn't remove it.
- The attacks that matter (a Portainer RCE, or operator-credential theft over
  Tailscale) are **not** prevented by the proxy — an attacker who reaches
  Portainer can still spawn a privileged container = host root. In a
  single-operator homelab, "limit which Docker API calls a compromised Portainer
  can make" is academic when any container-spawn is game-over.
- It adds a container to patch/monitor + trial-and-error to find the API
  endpoints Portainer needs — maintenance cost for ~zero net risk reduction here.

## Alternatives considered

- **`:ro`** — rejected: breaks Portainer's core function.
- **docker-socket-proxy** — rejected for THIS threat model (theater + maintenance
  cost); would be correct if the access model changed (see revisit).
- **Decommission Portainer** — out of scope; the operator uses UI-driven
  management. Becomes relevant only under a declarative-only (git-push) posture.

## Consequences

- Portainer remains fully functional.
- Documented accepted risk: a Portainer compromise ≈ host root, mitigated only by
  the Tailscale + auth perimeter and single-operator assumption.
- An inline comment on the `compose/core.yml` Portainer socket mount points here,
  so future audits reconcile via the comment instead of re-flagging.

## Revisit when (→ implement socket-proxy, or decommission)

- Portainer becomes multi-user / shared-team access.
- Portainer (or any container UI) is exposed beyond Tailscale / public ingress.
- A Portainer or container-breakout CVE lands with no immediate patch (temporary
  containment).
- Shift to declarative-only deploys (Terraform / git-push) → socket access goes
  away entirely; decommission Portainer instead.
