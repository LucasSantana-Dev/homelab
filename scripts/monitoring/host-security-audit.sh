#!/bin/bash
# host-security-audit.sh
# Weekly defensive audit of this host: Lynis (hardening) and Trivy (HIGH and
# CRITICAL CVEs in the images of running containers). Results go to the
# node-exporter textfile collector, reports to REPORT_DIR. It changes no host
# setting and no existing container, but it is not read-only: it may `docker
# pull` an image that is not yet local (an IMAGES override can name one), and
# it creates/reuses a `trivy-cache` Docker volume to cache Trivy's CVE
# database across runs.
#
# Trivy never gets the Docker socket (a `:ro` mount would still grant full
# daemon control). This script, already root, exports each image with
# `docker save` into a private temp dir and Trivy reads the tar with --input.
#
# Metrics exported:
#   host_security_audit_last_run_timestamp_seconds  epoch of this run
#   host_lynis_ok                                   1 if lynis ran and wrote a report
#   host_lynis_hardening_index                      lynis hardening index (0-100)
#   host_lynis_warnings                             lynis warning count
#   host_image_scan_ok{image}                       1 if trivy scanned the image
#   host_image_vulnerabilities{image,severity}      HIGH/CRITICAL CVE count
#
# Any failure to list images or to publish the metric file exits non-zero, so
# systemd records the run as failed and the staleness alert fires.
#
# IMAGES="img1 img2" overrides the running-container list (used to prove the
# scan with a known-vulnerable image).

set -uo pipefail

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
REPORT_DIR="${REPORT_DIR:-/var/log/homelab/security}"
SCAN_TMP="${SCAN_TMP:-/var/tmp}"
TRIVY_IMAGE="${TRIVY_IMAGE:-aquasec/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969}"
METRIC_FILE="${TEXTFILE_DIR}/host-security-audit.prom"

die() { echo "host-security-audit: $*" >&2; exit 1; }

mkdir -p "$TEXTFILE_DIR" "$REPORT_DIR" || die "cannot create $TEXTFILE_DIR or $REPORT_DIR"
TEMP_FILE="$(mktemp "${TEXTFILE_DIR}/.host-security-audit.XXXXXX")" || die "mktemp failed in $TEXTFILE_DIR"
WORK="$(mktemp -d "${SCAN_TMP}/host-audit.XXXXXX")" || die "mktemp failed in $SCAN_TMP"
chmod 700 "$WORK"
trap 'rm -rf "$TEMP_FILE" "$WORK"' EXIT
out() { printf '%s\n' "$*" >> "$TEMP_FILE" || die "write to $TEMP_FILE failed"; }

# ---- Lynis --------------------------------------------------------------
lynis_ok=0 hardening=0 warnings=0
lynis_dat="$REPORT_DIR/lynis-report.dat"
if command -v lynis >/dev/null 2>&1 &&
  lynis audit system --quick --no-colors --cronjob \
    --report-file "$lynis_dat" --log-file "$REPORT_DIR/lynis.log" >/dev/null 2>&1 &&
  [ -s "$lynis_dat" ]; then
  lynis_ok=1
  hardening=$(sed -n 's/^hardening_index=//p' "$lynis_dat" | tail -1)
  warnings=$(grep -c '^warning\[\]=' "$lynis_dat" || true)
fi

out "# HELP host_lynis_ok Lynis audit ran and wrote a report"
out "# TYPE host_lynis_ok gauge"
out "host_lynis_ok $lynis_ok"
out "# HELP host_lynis_hardening_index Lynis hardening index (0-100)"
out "# TYPE host_lynis_hardening_index gauge"
out "host_lynis_hardening_index ${hardening:-0}"
out "# HELP host_lynis_warnings Lynis warning count"
out "# TYPE host_lynis_warnings gauge"
out "host_lynis_warnings ${warnings:-0}"

# ---- Trivy --------------------------------------------------------------
# IMAGE_PAIRS holds one "id|label" per line: the immutable image ID to scan
# and save (never changes underneath us), and a human repo:tag for the
# metric's `image` label. `docker ps --format '{{.Image}}'` reports the
# mutable tag a container was started with; if that tag gets retagged or
# re-pulled between enumeration and `docker save`, the scan would silently
# cover a different image than the one actually running. Resolving each
# running container's bound image ID with `docker inspect` closes that race.
if [ -z "${IMAGES:-}" ]; then
  container_ids=$(docker ps -q) || die "docker ps failed; no image was scanned"
  IMAGE_PAIRS=""
  for cid in $container_ids; do
    pair=$(docker inspect --format '{{.Image}}|{{.Config.Image}}' "$cid" 2>/dev/null) || die "docker inspect failed for container $cid; no image was scanned"
    IMAGE_PAIRS="${IMAGE_PAIRS}${pair}"$'\n'
  done
  IMAGE_PAIRS=$(sort -u <<< "$IMAGE_PAIRS")
else
  # An IMAGES override names images directly (not necessarily running), so
  # the id and the label are the same pullable reference.
  IMAGE_PAIRS=""
  for name in $IMAGES; do
    IMAGE_PAIRS="${IMAGE_PAIRS}${name}|${name}"$'\n'
  done
fi

out "# HELP host_image_scan_ok Trivy scanned the image"
out "# TYPE host_image_scan_ok gauge"
out "# HELP host_image_vulnerabilities HIGH/CRITICAL CVEs in an image in use"
out "# TYPE host_image_vulnerabilities gauge"
summary="$REPORT_DIR/trivy-summary.txt"
errors="$REPORT_DIR/trivy-errors.log"
: > "$summary" || die "cannot write $summary"
: > "$errors" || die "cannot write $errors"

scan() {
  local tar="$WORK/image.tar"
  # IMAGES overrides may name images that are not local yet.
  docker image inspect "$1" >/dev/null 2>&1 || docker pull -q "$1" >/dev/null 2>>"$errors" || return 1
  docker save -o "$tar" "$1" 2>>"$errors" || { rm -f "$tar"; return 1; }
  docker run --rm --network bridge \
    -v "$tar:/scan/image.tar:ro" \
    -v trivy-cache:/root/.cache/ \
    "$TRIVY_IMAGE" image --quiet --scanners vuln --severity HIGH,CRITICAL \
    --format json --input /scan/image.tar 2>>"$errors"
  local rc=$?
  rm -f "$tar"
  return $rc
}

for pair in $IMAGE_PAIRS; do
  id="${pair%%|*}"
  img="${pair#*|}"
  [ -n "$img" ] || img="$id"
  label=${img//\"/}
  # One retry: the first scan of a run can fail while the CVE database downloads.
  if { json=$(scan "$id") || json=$(scan "$id"); } &&
    counts=$(printf '%s' "$json" | python3 -c '
import json, sys
d = json.load(sys.stdin)
c = {"HIGH": 0, "CRITICAL": 0}
for r in d.get("Results") or []:
    for v in r.get("Vulnerabilities") or []:
        if v.get("Severity") in c:
            c[v["Severity"]] += 1
print(c["HIGH"], c["CRITICAL"])'); then
    read -r high crit <<< "$counts"
    out "host_image_scan_ok{image=\"$label\"} 1"
    out "host_image_vulnerabilities{image=\"$label\",severity=\"HIGH\"} $high"
    out "host_image_vulnerabilities{image=\"$label\",severity=\"CRITICAL\"} $crit"
    printf '%s CRITICAL=%s HIGH=%s\n' "$img" "$crit" "$high" >> "$summary" || die "write to $summary failed"
  else
    out "host_image_scan_ok{image=\"$label\"} 0"
    printf '%s SCAN FAILED\n' "$img" >> "$summary" || die "write to $summary failed"
  fi
done

out "# HELP host_security_audit_last_run_timestamp_seconds Epoch of the last audit run"
out "# TYPE host_security_audit_last_run_timestamp_seconds gauge"
out "host_security_audit_last_run_timestamp_seconds $(date +%s)"

chmod 644 "$TEMP_FILE" || die "chmod failed"
mv "$TEMP_FILE" "$METRIC_FILE" || die "could not publish $METRIC_FILE"
echo "lynis_ok=$lynis_ok hardening=${hardening:-0} warnings=${warnings:-0} images=$(wc -l < "$summary")"
