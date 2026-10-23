"""WUD classify endpoint for agent-box (port 8080), run as agent with python3 -I.

n8n calls POST /wud-classify with the WUD payload; hermes returns classification JSON.
Callers must send the shared secret in the X-Classify-Token header. The entrypoint
pipes that secret (WUD_CLASSIFY_TOKEN from the agent-box sops file) on stdin, so it
is never in a file or in this process's environment. Without it the server exits.
"""

import hmac
import http.server
import json
import subprocess
import sys

# The copy baked into the image, not the one in /workspace/homelab: that checkout
# is the agent gate's workdir and can sit on a PR branch, so its script is
# whatever the PR under autofix says. A change to the script ships with the image.
CLASSIFY_CMD = [
    "bash",
    "-c",
    "source /etc/profile.d/agent-env.sh 2>/dev/null; "
    "exec bash /opt/agent-config/hermes-wud-classify.sh",
]
FALLBACK = json.dumps(
    {"safe_to_schedule": True, "urgency": "low", "reason": "hermes unavailable"}
).encode()
MAX_BODY = 64 * 1024  # WUD payloads are ~1-2KB; cap to avoid resource exhaustion (#310)
MIN_TOKEN_LEN = 32


def read_token(stream):
    """First line of stream as bytes, or None when it is shorter than MIN_TOKEN_LEN."""
    token = stream.readline().strip().encode()
    return token if len(token) >= MIN_TOKEN_LEN else None


class Handler(http.server.BaseHTTPRequestHandler):
    token = b""

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
        given = self.headers.get("X-Classify-Token", "").encode()
        if not self.token or not hmac.compare_digest(given, self.token):
            self.send_response(401)
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


def main():
    token = read_token(sys.stdin)
    if token is None:
        sys.exit(
            "[agent-box] no WUD_CLASSIFY_TOKEN on stdin; not starting /wud-classify"
        )
    Handler.token = token
    # n8n reaches this over the Docker network; 8080 is not published on the host.
    http.server.HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()  # nosec B104


if __name__ == "__main__":
    main()
