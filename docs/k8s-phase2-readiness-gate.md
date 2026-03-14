# Phase-2 Readiness Gate (Stateful Workloads)

Advance to phase 2 only if all checks pass:

1. Migration wave services stable for at least 14 days.
2. Backup + restore drill validated for `filebrowser` PVC.
3. Terraform plans are drift-free in consecutive runs.
4. K3s node remains within resource budget under normal load.
5. Rollback drills complete in maintenance window without data loss.
6. Compose update/watchdog automation remains healthy and unchanged.
