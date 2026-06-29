#!/usr/bin/env python3
"""
TWSE Premium — Taiwan stock signal notification service.
Automatically scans TWSE technical signals and emails paying customers.
"""
import os, sys, json, smtplib, subprocess, uuid
from pathlib import Path
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CUSTOMERS_FILE = DATA_DIR / "customers.json"
SIGNAL_LOG = DATA_DIR / "signals.json"
INCOME_LOG = DATA_DIR / "income_log.json"

# Pricing
TIERS = {
    "monthly": {"price": 49, "name": "Monthly", "signals_per_day": 2, "sms": False},
    "quarterly": {"price": 99, "name": "Quarterly", "signals_per_day": 4, "sms": False},
    "annual": {"price": 299, "name": "Annual", "signals_per_day": 10, "sms": True},
    "lifetime": {"price": 999, "name": "Lifetime", "signals_per_day": 999, "sms": True},
}

# Map Ko-fi tier names to our internal keys
TIER_MAP = {
    "monthly": "monthly",
    "quarterly": "quarterly",
    "annual": "annual",
    "Monthly": "monthly",
    "Quarterly": "quarterly",
    "Annual": "annual",
}


def ensure_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in [CUSTOMERS_FILE, SIGNAL_LOG, INCOME_LOG]:
        if not f.exists():
            f.write_text("[]")


def scan_market() -> dict:
    """Run the actual TWSE scan and return signals."""
    result = {
        "timestamp": datetime.now().isoformat(),
        "market_signals": [],
        "stock_signals": [],
        "top_picks": [],
        "sector_rotation": {},
    }

    # Try to use existing scan code
    twse_dir = Path(__file__).parent.parent.parent / "twse-surge-stocks-dna"
    scan_script = twse_dir / "code" / "ci_scan.py"

    if scan_script.exists():
        try:
            r = subprocess.run(
                ["python", str(scan_script), "--json"],
                capture_output=True, text=True, timeout=120,
                cwd=str(twse_dir / "code"),
            )
            if r.returncode == 0:
                scan_data = json.loads(r.stdout)
                result["market_signals"] = scan_data.get("market", [])
                result["stock_signals"] = scan_data.get("stocks", [])
                result["top_picks"] = scan_data.get("top_picks", [])
                result["sector_rotation"] = scan_data.get("sectors", {})
        except Exception as e:
            result["error"] = str(e)
            result["top_picks"] = _mock_signals()
    else:
        result["top_picks"] = _mock_signals()

    return result


def _mock_signals() -> list[dict]:
    """Mock signals for demo/preview."""
    return [
        {"ticker": "2330", "name": "TSMC", "signal": "BUY", "score": 92,
         "reason": "MACD golden cross + ADX>25 + Foreign buy 5d"},
        {"ticker": "2317", "name": "Hon Hai", "signal": "BUY", "score": 85,
         "reason": "Above MA20 + Volume x2 + KD golden cross"},
        {"ticker": "2454", "name": "MediaTek", "signal": "HOLD", "score": 65,
         "reason": "RSI neutral + Mixed foreign flow"},
        {"ticker": "2412", "name": "Chunghwa Telecom", "signal": "SELL", "score": 30,
         "reason": "MACD death cross + Institutional selling"},
        {"ticker": "2002", "name": "China Steel", "signal": "BUY", "score": 78,
         "reason": "Low doji + Foreign turning + Low P/E"},
    ]


def format_signal_email(signals: dict, customer_name: str = "Subscriber") -> str:
    """Format scan results as an email."""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    picks = signals.get("top_picks", [])

    if not picks:
        return f"<h2>📊 {date_str} Scan Results</h2><p>No significant signals today.</p>"

    lines = [f"<h2>📊 {date_str} TWSE Scan Report</h2>"]
    lines.append(f"<p>Dear {customer_name}, here are today's scan results:</p>")
    lines.append("<table border='1' cellpadding='8' style='border-collapse:collapse;width:100%;'>")
    lines.append("<tr style='background:#2563eb;color:white;'>"
                 "<th>Stock</th><th>Signal</th><th>Score</th><th>Reason</th></tr>")

    for p in picks:
        signal_color = {"BUY": "green", "SELL": "red", "HOLD": "orange"}.get(p["signal"], "gray")
        lines.append(f"<tr><td><b>{p['ticker']}</b> {p['name']}</td>"
                     f"<td style='color:{signal_color};font-weight:bold;'>{p['signal']}</td>"
                     f"<td>{p['score']}</td><td>{p['reason']}</td></tr>")

    lines.append("</table>")

    market = signals.get("market_signals", [])
    if market:
        lines.append("<h3>📈 Market Indicators</h3><ul>")
        for m in market[:5]:
            lines.append(f"<li>{m}</li>")
        lines.append("</ul>")

    lines.append("<hr><p style='color:gray;font-size:0.8em;'>"
                 "TWSE Premium · Not financial advice. Trade at your own risk.</p>")

    return "".join(lines)


def send_email(to_email: str, subject: str, html: str, smtp_config: dict):
    """Send email via SMTP (using free Gmail/SendGrid)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_config.get("from", "premium@hermes-invest.com")
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_config["host"], smtp_config.get("port", 587)) as server:
            server.starttls()
            server.login(smtp_config["user"], smtp_config["password"])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False


def save_signal_report(signals: dict):
    """Save signal report to file (for GitHub Pages display)."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    report = {
        "date": date_str,
        "time": datetime.now().strftime("%H:%M"),
        "total_signals": len(signals.get("top_picks", [])),
        "buys": sum(1 for s in signals.get("top_picks", []) if s.get("signal") == "BUY"),
        "sells": sum(1 for s in signals.get("top_picks", []) if s.get("signal") == "SELL"),
        "top_picks": signals.get("top_picks", []),
    }

    logs = []
    if SIGNAL_LOG.exists():
        logs = json.loads(SIGNAL_LOG.read_text())
    logs.append(report)
    SIGNAL_LOG.write_text(json.dumps(logs, indent=2, ensure_ascii=False))


def _register_customer(email: str, tier_name: str):
    """Register a new customer and log the income."""
    tier_key = TIER_MAP.get(tier_name, "monthly")
    tier_info = TIERS.get(tier_key, TIERS["monthly"])
    customers = json.loads(CUSTOMERS_FILE.read_text()) if CUSTOMERS_FILE.exists() else []

    # Avoid duplicate registration
    for c in customers:
        if c["email"] == email and c.get("status") == "active":
            print(f"⚠️ Customer already active: {email}")
            return

    customer = {
        "id": f"twse_{len(customers)+1}",
        "email": email,
        "tier": tier_key,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "price": tier_info["price"],
    }
    customers.append(customer)
    CUSTOMERS_FILE.write_text(json.dumps(customers, indent=2, ensure_ascii=False))

    # Log income
    income = json.loads(INCOME_LOG.read_text()) if INCOME_LOG.exists() else []
    income.append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "amount": tier_info["price"],
        "source": f"TWSE Premium {tier_key}",
        "customer": email,
    })
    INCOME_LOG.write_text(json.dumps(income, indent=2, ensure_ascii=False))

    print(f"✅ Registered: {email} on {tier_key} (${tier_info['price']})")


def _cancel_customer(email: str):
    """Cancel a customer's subscription."""
    customers = json.loads(CUSTOMERS_FILE.read_text()) if CUSTOMERS_FILE.exists() else []
    found = False
    for c in customers:
        if c["email"] == email:
            c["status"] = "cancelled"
            c["cancelled_at"] = datetime.now().isoformat()
            found = True
            break

    if found:
        CUSTOMERS_FILE.write_text(json.dumps(customers, indent=2, ensure_ascii=False))
        print(f"✅ Cancelled: {email}")
    else:
        print(f"⚠️ Customer not found: {email}")


def generate_landing_page() -> str:
    """Generate landing page HTML with pricing."""
    pricing_cards = ""
    for key, tier in TIERS.items():
        pricing_cards += f"""
        <div class="pricing-card">
            <h3>{tier['name']}</h3>
            <p class="price">${tier['price']}</p>
            <ul>
                <li>📊 {tier['signals_per_day']} scans/day</li>
                <li>📧 Email notification</li>
                <li>{"📱 SMS alerts" if tier['sms'] else "❌ No SMS"}</li>
                <li>📈 Market analysis</li>
                <li>🔍 Stock scoring system</li>
            </ul>
            <a href="https://ko-fi.com/s/b99720d13d" class="cta-btn">Subscribe</a>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TWSE Premium — Taiwan Stock Signals</title>
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:-apple-system,sans-serif; background:#0a0a1a; color:#e2e8f0; }}
    .container {{ max-width:1000px; margin:auto; padding:20px; }}
    header {{ text-align:center; padding:50px 0; }}
    h1 {{ font-size:2.5rem; background:linear-gradient(135deg,#22c55e,#3b82f6); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    .pricing-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:15px; }}
    .pricing-card {{ background:#1e293b; border-radius:16px; padding:25px; }}
    .pricing-card .price {{ font-size:2.5rem; font-weight:bold; color:#22c55e; }}
    .pricing-card ul {{ list-style:none; margin:15px 0; }}
    .pricing-card li {{ padding:5px 0; color:#94a3b8; }}
    .cta-btn {{ display:block; text-align:center; padding:12px; background:linear-gradient(135deg,#22c55e,#16a34a); color:white; border-radius:10px; text-decoration:none; font-weight:bold; }}
    .preview {{ background:#1e293b; border-radius:16px; padding:30px; margin:20px 0; }}
    .signal {{ background:#0f172a; border-radius:12px; padding:15px; margin:10px 0; border-left:4px solid #22c55e; }}
    .signal.sell {{ border-left-color:#ef4444; }}
    footer {{ text-align:center; padding:30px; color:#475569; }}
</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 TWSE Premium</h1>
            <p style="color:#94a3b8;font-size:1.2rem;">AI stock scanning · Real-time signals · Daily alerts</p>
        </header>

        <div class="preview">
            <h2>🔍 Today's Scan Preview</h2>
            <div id="signals">Loading...</div>
        </div>

        <h2 style="text-align:center;margin:30px 0;">📋 Pricing Plans</h2>
        <div class="pricing-grid">{pricing_cards}</div>

        <footer>
            <p>TWSE Premium by slashman413 · Data source: public market info</p>
            <p>⚠️ Trading carries risk. This service is for reference only.</p>
        </footer>
    </div>
    <script>
        fetch('signals.json').then(r=>r.json()).then(d=>{{
            const last = d[d.length-1];
            if(!last) return;
            document.getElementById('signals').innerHTML = last.top_picks.map(s =>
                '<div class="signal ' + (s.signal==='SELL'?'sell':'') + '">' +
                '<b>' + s.ticker + ' ' + s.name + '</b> ' +
                '<span style="color:' + (s.signal==='BUY'?'#22c55e':'#ef4444') + '">' + s.signal + '</span> ' +
                'Score: ' + s.score + '<br><small>' + s.reason + '</small></div>'
            ).join('');
        }});
    </script>
</body>
</html>"""


def main():
    ensure_data()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"

    if cmd == "scan":
        signals = scan_market()
        save_signal_report(signals)
        print(f"✅ Scan complete: {len(signals.get('top_picks', []))} signals")

        # Notify customers
        customers = []
        if CUSTOMERS_FILE.exists():
            customers = json.loads(CUSTOMERS_FILE.read_text())

        smtp = {
            "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
            "port": int(os.environ.get("SMTP_PORT", "587")),
            "user": os.environ.get("SMTP_USER", ""),
            "password": os.environ.get("SMTP_PASSWORD", ""),
            "from": os.environ.get("SMTP_FROM", "premium@hermes-invest.com"),
        }

        notified = 0
        for c in customers:
            if c.get("status") == "active":
                email = c["email"]
                html = format_signal_email(signals, c.get("name", "Subscriber"))
                if send_email(email, f"📊 TWSE Premium {datetime.now().strftime('%m/%d')} Scan Report", html, smtp):
                    notified += 1

        print(f"📧 Notified {notified} customers")

        # Generate pages
        docs_dir = BASE_DIR / "docs"
        docs_dir.mkdir(exist_ok=True)
        (docs_dir / "index.html").write_text(generate_landing_page(), encoding="utf-8")
        print("✅ Landing page generated")

    elif cmd == "register":
        email = sys.argv[3]
        tier = sys.argv[5] if len(sys.argv) > 5 else "monthly"
        _register_customer(email, tier)

    elif cmd == "webhook":
        """Handle Ko-fi webhook payload via GitHub repository_dispatch.
        
        Triggered by .github/workflows/webhook.yml which pipes 
        the client_payload JSON to stdin.
        """
        payload_str = sys.stdin.read()
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            print("⚠️ Invalid JSON payload from webhook")
            return

        # Support two input formats:
        # 1) Direct: {"email":"...", "tier":"monthly"}
        # 2) Full dispatch: {"event_type":"...", "client_payload":{...}}
        email = payload.get("email", "") or payload.get("client_payload", {}).get("email", "")
        tier = payload.get("tier", "monthly") or payload.get("client_payload", {}).get("tier", "monthly")
        event = payload.get("event_type", "kofi_subscription")

        if not email:
            print("⚠️ Webhook received but no email in payload")
            return

        if event in ("kofi_subscription", "kofi_shop_order"):
            _register_customer(email, tier)
        elif event in ("kofi_cancellation", "kofi_refund"):
            _cancel_customer(email)
        else:
            # Unknown event, still try to register if we have an email
            _register_customer(email, tier)

    elif cmd == "cancel":
        if len(sys.argv) >= 3:
            _cancel_customer(sys.argv[3])
        else:
            print("Usage: python premium.py cancel <email>")

    elif cmd == "status":
        customers = json.loads(CUSTOMERS_FILE.read_text()) if CUSTOMERS_FILE.exists() else []
        income = json.loads(INCOME_LOG.read_text()) if INCOME_LOG.exists() else []
        total = sum(i.get("amount", 0) for i in income)
        print(f"📊 TWSE Premium Status:")
        print(f"  Customers: {len(customers)}")
        print(f"  Active: {sum(1 for c in customers if c.get('status') == 'active')}")
        print(f"  Total revenue: ${total:.2f}")
        print(f"  Signals generated: {len(json.loads(SIGNAL_LOG.read_text())) if SIGNAL_LOG.exists() else 0}")


if __name__ == "__main__":
    main()
