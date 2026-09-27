#!/bin/bash
# compose-services-exporter.sh
# Exports, per default-profile compose service, whether it has a running
# container. Services under `profiles:` (deliberately stopped, ADR 0040) are
# not in `docker compose config --services` and are not expected.
#
# Why: on 2026-09-20 eight services lost their containers (failed start at
# boot, then docker-prune removed them). Nothing alerted for 7 days, because a
# container that does not exist exposes no metric and no health check.
#
# Metrics exported:
#   homelab_compose_service_running{service}             1 running, 0 not
#   homelab_compose_services_not_running                  count of the zeros
#   homelab_compose_exporter_last_run_timestamp_seconds   meta-healthcheck
#   homelab_compose_exporter_ok                           1 if compose answered

set -uo pipefail

REPO_DIR="${REPO_DIR:-/home/luk-server/homelab}"
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
METRIC_FILE="${TEXTFILE_DIR}/homelab-compose-services.prom"

die() { echo "compose-services-exporter: $*" >&2; exit 1; }
mkdir -p "$TEXTFILE_DIR" || die "cannot create $TEXTFILE_DIR"
TEMP_FILE="$(mktemp "${TEXTFILE_DIR}/.homelab-compose-services.XXXXXX")" || die "mktemp failed"
trap 'rm -f "$TEMP_FILE"' EXIT

cd "$REPO_DIR" || die "cannot cd to $REPO_DIR"
ok=1
expected=$(docker compose config --services 2>/dev/null) || ok=0
[ -n "$expected" ] || ok=0

# `docker compose ps --status running --format '{{.Service}}'` also lists
# one-off `docker compose run` containers under their target service's name,
# so a leftover one-off run can mask a service that has no real, long-lived
# container running. Resolve each running container's own labels instead and
# skip the ones tagged com.docker.compose.oneoff=True.
running=""
if [ "$ok" = 1 ]; then
  running_names=$(docker compose ps --status running --format '{{.Name}}' 2>/dev/null) || ok=0
  if [ "$ok" = 1 ]; then
    for cname in $running_names; do
      info=$(docker inspect --format \
        '{{ index .Config.Labels "com.docker.compose.oneoff" }}|{{ index .Config.Labels "com.docker.compose.service" }}' \
        "$cname" 2>/dev/null) || continue
      [ "${info%%|*}" = "True" ] && continue
      running="${running}${info#*|}"$'\n'
    done
  fi
fi

{
  echo "# HELP homelab_compose_service_running 1 if the default-profile service has a running container"
  echo "# TYPE homelab_compose_service_running gauge"
  missing=0
  if [ "$ok" = 1 ]; then
    for svc in $expected; do
      if grep -qxF -- "$svc" <<< "$running"; then
        echo "homelab_compose_service_running{service=\"$svc\"} 1"
      else
        echo "homelab_compose_service_running{service=\"$svc\"} 0"
        missing=$((missing + 1))
      fi
    done
  fi
  echo "# HELP homelab_compose_services_not_running Default-profile services without a running container"
  echo "# TYPE homelab_compose_services_not_running gauge"
  echo "homelab_compose_services_not_running $missing"
  echo "# HELP homelab_compose_exporter_ok 1 if docker compose answered"
  echo "# TYPE homelab_compose_exporter_ok gauge"
  echo "homelab_compose_exporter_ok $ok"
  echo "# HELP homelab_compose_exporter_last_run_timestamp_seconds Unix time of the last run"
  echo "# TYPE homelab_compose_exporter_last_run_timestamp_seconds gauge"
  echo "homelab_compose_exporter_last_run_timestamp_seconds $(date +%s)"
} > "$TEMP_FILE"

chmod 644 "$TEMP_FILE" || die "chmod failed"
mv "$TEMP_FILE" "$METRIC_FILE" || die "could not publish $METRIC_FILE"
trap - EXIT
echo "ok=$ok not_running=$missing"
[ "$ok" = 1 ] || exit 1
