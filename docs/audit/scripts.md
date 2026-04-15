# Scripts Audit

## Count by dir
31  scripts/maintenance/
11  scripts/migration/
6  scripts/security/
5  scripts/deployment/
4  scripts/bootstrap/
1  scripts/monitoring/
1  scripts/lib/
0  scripts/systemd/
0  scripts/logs/
0  scripts/hacs/

## Scripts missing 'set -euo pipefail'
scripts/maintenance/import-wave-g-images.sh
scripts/maintenance/reconcile-automation.sh
scripts/maintenance/homelab-watchdog.sh
scripts/maintenance/update-containers.sh
scripts/maintenance/cleanup-project.sh
scripts/maintenance/burnin-status.sh
scripts/monitoring/status-services.sh
scripts/migration/wave-a-status.sh
scripts/security/validate-env.sh
scripts/deployment/startup-services.sh
scripts/deployment/shutdown-services.sh
scripts/bootstrap/create-observability-secrets.sh

## Shellcheck — top issues
     15  warning
     11  note

## Shellcheck — worst-offender files
      6 scripts/maintenance/update-containers.sh
      5 scripts/security/security-scan.sh
      4 scripts/maintenance/automated-backup.sh
      2 scripts/migration/encrypt-k8s-secret.sh
      2 scripts/maintenance/workflow-ref-guard.sh
      2 scripts/maintenance/cleanup-project.sh
      1 scripts/maintenance/update-containers-cron.sh
      1 scripts/maintenance/stabilize-host-prep.sh
      1 scripts/maintenance/recover-lucky-db.sh
      1 scripts/maintenance/pr-health-watchdog.sh
      1 scripts/maintenance/main-ci-watchdog.sh

## Suspicious credential patterns (redacted)
scripts/maintenance/recover-lucky-db.sh:9:DB_PASSWORD=***REDACTED***
scripts/maintenance/update-containers.sh:18:FORGE_MCP_BASIC_AUTH_PASSWORD=***REDACTED***
scripts/maintenance/update-containers.sh:19:FORGE_MCP_ADMIN_PASSWORD=***REDACTED***
scripts/maintenance/update-containers.sh:32:        FORGE_MCP_BASIC_AUTH_PASSWORD=***REDACTED***
scripts/maintenance/update-containers.sh:35:        FORGE_MCP_ADMIN_PASSWORD=***REDACTED***
scripts/maintenance/update-containers.sh:47:    FORGE_MCP_BASIC_AUTH_PASSWORD=***REDACTED***
scripts/maintenance/update-containers.sh:51:    FORGE_MCP_ADMIN_PASSWORD=***REDACTED***
scripts/maintenance/authentik-register-apps.sh:104:            -e AK_GRAFANA_CLIENT_SECRET=***REDACTED***
scripts/maintenance/authentik-register-apps.sh:106:            -e AK_PORTAINER_CLIENT_SECRET=***REDACTED***
scripts/maintenance/authentik-register-apps.sh:793:AUTHENTIK_GRAFANA_CLIENT_SECRET=***REDACTED***
scripts/maintenance/authentik-register-apps.sh:795:AUTHENTIK_PORTAINER_CLIENT_SECRET=***REDACTED***
scripts/maintenance/post-t24-terraform-apply.sh:58:gate_token=***REDACTED***
scripts/maintenance/post-t24-terraform-apply.sh:91:CLOUDFLARE_API_TOKEN=***REDACTED***
scripts/maintenance/post-t24-terraform-apply.sh:115:  CLOUDFLARE_API_TOKEN=***REDACTED***
scripts/maintenance/post-t24-terraform-apply.sh:148:  CLOUDFLARE_API_TOKEN=***REDACTED***
scripts/maintenance/post-t24-terraform-apply.sh:155:  CLOUDFLARE_API_TOKEN=***REDACTED***
scripts/security/pre-release-checkpoint.sh:39:  grep -E 'TOKEN=***REDACTED***
scripts/bootstrap/create-nextcloud-secrets.sh:13:  --from-literal=***REDACTED***
scripts/bootstrap/create-nextcloud-secrets.sh:14:  --from-literal=***REDACTED***
scripts/bootstrap/create-authentik-secrets.sh:19:  --from-literal=***REDACTED***
