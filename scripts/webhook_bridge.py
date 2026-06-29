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
        print("[IN] Webhook received: %s..." % body[:300])

        # Ko-fi sends data as form-urlencoded: data={JSON}
        payload_raw = body
        content_type = self.headers.get("Content-Type", "")

        if "x-www-form-urlencoded" in content_type:
            # Parse form data: data={"type":"Subscription","email":"..."}
            import urllib.parse
            form = urllib.parse.parse_qs(body)
            payload_raw = form.get("data", [body])[0]

        try:
            data = json.loads(payload_raw)
        except json.JSONDecodeError:
            print("[ERR] Invalid JSON: %s" % payload_raw[:200])
            self.send_error(400, "Invalid JSON")
            return

        # Extract fields from Ko-fi payload
        email = data.get("email", "") or ""
        tier = data.get("tier_name", "") or data.get("tier", "") or "monthly"
        event_type_raw = data.get("type", "") or ""
        is_sub_payment = data.get("is_subscription_payment", False)
        is_first = data.get("is_first_subscription_payment", False)

        print("[INFO] Event: %s | Email: %s | Tier: %s" % (event_type_raw, email, tier))

        if email:
            if "cancel" in event_type_raw.lower() or "refund" in event_type_raw.lower():
                forward_to_github("kofi_cancellation", email, tier)
            elif event_type_raw in ("Subscription", "Shop Order") and (is_first or is_sub_payment):
                forward_to_github("kofi_subscription", email, tier)
            else:
                print("[WARN] Unknown event type: %s" % event_type_raw)
        else:
            print("[WARN] No email in payload: %s" % payload_raw[:300])

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
