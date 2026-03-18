# k3s Restart Baseline

This note defines the restart-count baseline after Waves A-H migration so
operators do not treat historical node lifecycle restarts as active incidents.

## Snapshot Baseline

Use:

```bash
KUBECONFIG=~/.kube/config kubectl get pods -A --no-headers | awk '{print $1, $2, $5}' | sort
```

Observed historical examples:

- `apps/homepage`: restart count 7
- `apps/uptime-kuma`: restart count 7
- `apps/pihole`: restart count 8
- `observability/grafana`: restart count 11
- `kube-system/coredns`: restart count 10

## Classification Rule

Treat as informational (not incident) when all are true:

1. pod is `Running` and ready (`1/1` or expected ready count)
2. `kubectl describe pod` shows `Last State: Terminated`, `Reason: Unknown`,
   `Exit Code: 255` from prior node lifecycle
3. restart count is stable across checks

Treat as actionable incident when any are true:

- restart count increases between consecutive checks
- readiness/liveness probe failures continue
- pod enters CrashLoopBackOff, Error, or Pending unexpectedly

## 24-Hour Recheck

Run twice and compare deltas:

```bash
KUBECONFIG=~/.kube/config kubectl get pods -A --no-headers | awk '{print $1, $2, $5}' | sort
```

If counts are unchanged and pods stay healthy, no remediation is required.
