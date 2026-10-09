"""WUD classify endpoint for agent-box (port 8080), run as agent with python3 -I.

n8n calls POST /wud-classify with the WUD payload; hermes returns classification JSON.
"""

import http.server
import json
import subprocess

CLASSIFY_CMD = [
    "bash",
    "-c",
    "source /etc/profile.d/agent-env.sh 2>/dev/null; "
    "exec bash /workspace/homelab/scripts/agent-tasks/hermes-wud-classify.sh",
]
FALLBACK = json.dumps(
    {"safe_to_schedule": True, "urgency": "low", "reason": "hermes unavailable"}
).encode()
MAX_BODY = 64 * 1024  # WUD payloads are ~1-2KB; cap to avoid resource exhaustion (#310)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        ok = self.path == "/healthz"
        self.send_response(200 if ok else 404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        if ok:
            self.wfile.write(b"ok")

    def do_POST(self):
        if self.path != "/wud-classify":
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = -1
        if length < 0 or length > MAX_BODY:
            self.send_response(413)
            self.end_headers()
            return
        body = self.rfile.read(length)
        try:
            r = subprocess.run(
                CLASSIFY_CMD, input=body, capture_output=True, timeout=120
            )
            out = (
                r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else FALLBACK
            )
        except Exception:
            out = FALLBACK
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)


# n8n reaches this over the Docker network; 8080 is not published on the host.
http.server.HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()  # nosec B104
