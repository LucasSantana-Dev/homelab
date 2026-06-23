#!/usr/bin/env bash
# hermes-wud-classify.sh — classify a WUD container update via claude --print.
# Called by the agent-box HTTP server on POST /wud-classify.
#
# Input:  JSON on stdin (WUD container update payload from n8n)
# Output: JSON on stdout — {"safe_to_schedule": bool, "urgency": "low|medium|high", "reason": "string"}
set -euo pipefail

INPUT=$(cat)

NAME=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
c = d.get('container', d)
print(c.get('name', d.get('name', 'unknown')))
" 2>/dev/null || echo "unknown")

OLD_TAG=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
c = d.get('container', d)
uk = c.get('updateKind', {})
print(uk.get('localValue', c.get('image', {}).get('tag', {}).get('value', '?')))
" 2>/dev/null || echo "?")

NEW_TAG=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
c = d.get('container', d)
uk = c.get('updateKind', {})
# WUD's http-trigger payload is flat: new version is in result.tag.
# Keep updateKind.remoteValue as a fallback for the legacy/Discord shape.
print(uk.get('remoteValue') or d.get('result', {}).get('tag') or c.get('result', {}).get('tag') or '?')
" 2>/dev/null || echo "?")

PROMPT="You are a homelab ops assistant. A container image update is available.

Container: $NAME
Update: $OLD_TAG → $NEW_TAG

Classify this update. Reply with ONLY valid JSON, no prose before or after:
{\"safe_to_schedule\":true,\"urgency\":\"low\",\"reason\":\"one sentence\"}

urgency rules:
- low: patch/digest-only/build metadata change
- medium: minor version bump with new features
- high: security fix, CVE patch, or major version bump

safe_to_schedule: false only when urgency=high AND container is critical infrastructure
(database, proxy, auth, caddy, mariadb, redis, prometheus)"

RESULT=$(claude --print "$PROMPT" 2>/dev/null | python3 -c "
import sys, json, re
text = sys.stdin.read()
m = re.search(r'\{[^{}]+\}', text, re.DOTALL)
if m:
    try:
        d = json.loads(m.group())
        if all(k in d for k in ('safe_to_schedule', 'urgency', 'reason')):
            print(json.dumps(d))
            sys.exit(0)
    except Exception:
        pass
print(json.dumps({'safe_to_schedule': True, 'urgency': 'low', 'reason': 'classification parse error'}))
" 2>/dev/null) || RESULT='{"safe_to_schedule":true,"urgency":"low","reason":"classification unavailable"}'

printf '%s\n' "$RESULT"
