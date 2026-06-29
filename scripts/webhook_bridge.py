#!/usr/bin/env python3
"""
TWSE Premium - Ko-fi Webhook Bridge

A minimal HTTP server that receives Ko-fi webhooks and forwards them
to GitHub's repository_dispatch API, triggering auto-registration.

HOW TO DEPLOY:
  Option A: Render (free) - https://render.com
    1. Push this file to a GitHub repo
    2. Create new Web Service -> Select repo
    3. Start command: python webhook_bridge.py
    4. Set env var: GITHUB_TOKEN=<your GitHub PAT>
    5. Set Ko-fi webhook URL to https://your-app.onrender.com/webhook

  Option B: Run locally with a tunnel
    python webhook_bridge.py --public-url https://your-tunnel.ngrok.io

  Option C: Manual trigger (no server needed)
    Go to GitHub -> Actions -> "Register Customer" -> Run workflow
"""

import os, json, http.server, urllib.request, urllib.error

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = "slashman413/hermes-twse-premium"

TIER_MAP = {
    "monthly": "monthly", "Monthly": "monthly",
    "quarterly": "quarterly", "Quarterly": "quarterly",
    "annual": "annual", "Annual": "annual",
}


def forward_to_github(event_type, email, tier="monthly"):
    """Send a repository_dispatch event to GitHub."""
    url = "https://api.github.com/repos/%s/dispatches" % REPO
    payload = json.dumps({
        "event_type": event_type,
        "client_payload": {
            "email": email,
            "tier": TIER_MAP.get(tier, "monthly"),
        }
    }).encode()

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", "Bearer %s" % GITHUB_TOKEN)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "twse-webhook-bridge")

    try:
        urllib.request.urlopen(req)
        print("[OK] Forwarded to GitHub: %s (%s)" % (event_type, email))
        return True
    except urllib.error.HTTPError as e:
        print("[ERR] GitHub API error: %d %s" % (e.code, e.read().decode()))
        return False


class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        print("[IN] Webhook received: %s..." % body[:200])

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        # Extract email from various Ko-fi payload formats
        email = data.get("email", "") or data.get("buyer_email", "") or ""
        tier = data.get("tier_name", "") or data.get("tier", "") or data.get("membership_tier", "") or "monthly"
        event = data.get("type", "") or data.get("event_type", "") or "kofi_subscription"

        if email:
            event_type = "kofi_cancellation" if ("cancel" in event.lower() or "refund" in event.lower()) else "kofi_subscription"
            forward_to_github(event_type, email, tier)
        else:
            print("[WARN] No email in payload: %s" % body[:300])

        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        html = """
        <html><body style="font-family:sans-serif;background:#0a0a1a;color:#e2e8f0;padding:40px;text-align:center;">
        <h1>TWSE Premium Webhook Bridge</h1>
        <p>Ko-fi webhook receiver is running.</p>
        <p>Set your Ko-fi webhook to POST to this URL + /webhook</p>
        </body></html>
        """
        self.wfile.write(html.encode())

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))


if __name__ == "__main__":
    import sys
    port = int(os.environ.get("PORT", 8080))

    if "--public-url" in sys.argv:
        idx = sys.argv.index("--public-url")
        public_url = sys.argv[idx + 1]
        print("[SETUP] Public URL: %s/webhook" % public_url)
        print("[SETUP] Set this as your Ko-fi webhook URL")

    print("[START] TWSE Webhook Bridge on port %d..." % port)
    if not GITHUB_TOKEN:
        print("[WARN] GITHUB_TOKEN not set! Auto-registration disabled.")
        print("[WARN] Set env var GITHUB_TOKEN to enable GitHub forwarding.")

    server = http.server.HTTPServer(("0.0.0.0", port), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down...")
