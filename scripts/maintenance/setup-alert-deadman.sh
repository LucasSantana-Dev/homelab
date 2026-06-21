#!/bin/bash
# Idempotently (re)create the alerting-pipeline dead-man-switch (ADR-0026):
#   - a healthchecks.io check "alert-pipeline-deadman" (5m period, 2m grace)
#   - a verified email channel (the project owner) assigned to it
#   - the Alertmanager → healthchecks ping-URL file
# Run on the host after a healthchecks rebuild. Alertmanager config (the Watchdog
# route + deadmanswitch receiver) lives in config/alertmanager/alertmanager.yml.
set -euo pipefail

PING_FILE=/home/luk-server/homelab/config/alertmanager/deadman_ping_url

code="$(docker exec healthchecks python manage.py shell -c '
import json
from datetime import timedelta
from hc.api.models import Check, Channel
from hc.accounts.models import Project
p = Project.objects.first(); owner = p.owner.email
chk, _ = Check.objects.get_or_create(name="alert-pipeline-deadman", project=p,
    defaults={"timeout": timedelta(minutes=5), "grace": timedelta(minutes=2)})
chk.timeout = timedelta(minutes=5); chk.grace = timedelta(minutes=2); chk.save()
ch = Channel.objects.filter(project=p, kind="email").first()
if not ch:
    ch = Channel(project=p, kind="email"); ch.value = json.dumps({"value": owner, "up": True, "down": True}); ch.save()
ch.email_verified = True; ch.save()              # owner controls this address
chk.channel_set.add(ch)
print(str(chk.code))
' 2>/dev/null | grep -E '^[0-9a-f-]{36}$' | head -1)"

if [[ -z "${code}" ]]; then echo "ERROR: failed to create/find the deadman check"; exit 1; fi
echo "deadman check code: ${code}"
echo "http://healthchecks:8000/ping/${code}" | sudo tee "${PING_FILE}" >/dev/null
echo "wrote ${PING_FILE}"
echo "Reload Alertmanager to pick up the ping file: docker kill -s HUP alertmanager"
