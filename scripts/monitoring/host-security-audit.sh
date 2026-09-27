#!/bin/bash
# host-security-audit.sh
# Weekly defensive audit of this host: Lynis (hardening) and Trivy (HIGH and
# CRITICAL CVEs in the images of running containers). Results go to the
# node-exporter textfile collector, reports to REPORT_DIR. Read-only: it never
# changes the host or a container.
#
# Metrics exported:
#   host_security_audit_last_run_timestamp_seconds  epoch of this run
#   host_lynis_ok                                   1 if lynis ran and wrote a report
#   host_lynis_hardening_index                      lynis hardening index (0-100)
#   host_lynis_warnings                             lynis warning count
#   host_image_scan_ok{image}                       1 if trivy scanned the image
#   host_image_vulnerabilities{image,severity}      HIGH/CRITICAL CVE count
#
# IMAGES="img1 img2" overrides the running-container list (used to prove the
# scan with a known-vulnerable image).

set -uo pipefail

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
REPORT_DIR="${REPORT_DIR:-/var/log/homelab/security}"
TRIVY_IMAGE="${TRIVY_IMAGE:-aquasec/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969}"
METRIC_FILE="${TEXTFILE_DIR}/host-security-audit.prom"
TEMP_FILE="$(mktemp "${TEXTFILE_DIR}/.host-security-audit.XXXXXX")"
trap 'rm -f "$TEMP_FILE"' EXIT

mkdir -p "$REPORT_DIR"
out() { printf '%s\n' "$*" >> "$TEMP_FILE"; }

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
if [ -z "${IMAGES:-}" ]; then
  IMAGES=$(docker ps --format '{{.Image}}' | sort -u)
fi

out "# HELP host_image_scan_ok Trivy scanned the image"
out "# TYPE host_image_scan_ok gauge"
out "# HELP host_image_vulnerabilities HIGH/CRITICAL CVEs in an image in use"
out "# TYPE host_image_vulnerabilities gauge"
summary="$REPORT_DIR/trivy-summary.txt"
: > "$summary"
scan() {
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock:ro \
    -v trivy-cache:/root/.cache/ \
    "$TRIVY_IMAGE" image --quiet --scanners vuln --severity HIGH,CRITICAL \
    --format json "$1" 2>>"$REPORT_DIR/trivy-errors.log"
}
: > "$REPORT_DIR/trivy-errors.log"
for img in $IMAGES; do
  label=${img//\"/}
  # One retry: the first scan of a run can fail while the CVE database downloads.
  if { json=$(scan "$img") || json=$(scan "$img"); } &&
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
    printf '%s CRITICAL=%s HIGH=%s\n' "$img" "$crit" "$high" >> "$summary"
  else
    out "host_image_scan_ok{image=\"$label\"} 0"
    printf '%s SCAN FAILED\n' "$img" >> "$summary"
  fi
done

out "# HELP host_security_audit_last_run_timestamp_seconds Epoch of the last audit run"
out "# TYPE host_security_audit_last_run_timestamp_seconds gauge"
out "host_security_audit_last_run_timestamp_seconds $(date +%s)"

chmod 644 "$TEMP_FILE"
mv "$TEMP_FILE" "$METRIC_FILE"
trap - EXIT
echo "lynis_ok=$lynis_ok hardening=${hardening:-0} warnings=${warnings:-0} images=$(wc -l < "$summary")"
