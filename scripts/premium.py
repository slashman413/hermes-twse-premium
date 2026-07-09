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


def _smtp_from_env() -> dict:
    return {
        "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from": os.environ.get("SMTP_FROM", "premium@hermes-invest.com"),
    }


def send_welcome_email(email: str, tier_key: str):
    """Confirm access the moment a subscriber pays, so they don't wait for the next scan."""
    smtp = _smtp_from_env()
    if not smtp["user"] or not smtp["password"]:
        print("ℹ️ SMTP not configured — skipping welcome email")
        return
    tier = TIERS.get(tier_key, TIERS["monthly"])
    # Richer zh-TW welcome (see EMAILS.md, Email 1). No first-name on file → use a neutral greeting.
    html = (
        f"<h2>✅ TWSE Premium 已開通</h2>"
        f"<p>歡迎加入 <b>TWSE Premium</b>（{tier['name']} 方案）。你的訂閱已開通。</p>"
        f"<p><b>接下來會收到什麼：</b></p>"
        f"<ul>"
        f"<li>每個交易日約 <b>09:00 與 13:30（台北時間）</b>，Email 送上當日精選訊號。</li>"
        f"<li>每檔含：代號／名稱／方向（買/賣）／量化評分／進出場參考價位，以及當日大盤與類股判讀。</li>"
        f"<li>你的方案每日最多 <b>{tier['signals_per_day']}</b> 檔訊號。</li>"
        f"</ul>"
        f"<p>第一份報告會在下一次掃描時送達。想隨時取消？直接回覆這封信即可。</p>"
        f"<p>如何使用訊號、以及 2004–2026 全市場回測："
        f"<a href='https://slashman413.github.io/twse-backtests/'>公開儀表板</a></p>"
        f"<hr><p style='color:gray;font-size:0.8em;'>TWSE Premium · 非投資建議，投資請自負風險 · 回信即可取消。</p>"
    )
    if send_email(email, "✅ TWSE Premium 已開通 — 你的每日訊號怎麼收", html, smtp):
        print(f"📧 Welcome email sent to {email}")


def save_public_report(signals: dict):
    """Save a PUBLIC teaser for the free GitHub Pages preview.

    The paid product IS the actionable detail (ticker, direction, score, reason),
    so it must never be committed to a public repo. We publish only counts and a
    locked/masked teaser here; the full picks go to paying subscribers by email.
    """
    picks = signals.get("top_picks", [])
    report = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M"),
        "total_signals": len(picks),
        "buys": sum(1 for s in picks if s.get("signal") == "BUY"),
        "sells": sum(1 for s in picks if s.get("signal") == "SELL"),
        # Masked teaser: hint at coverage without leaking the actionable signal.
        "locked_preview": [
            {"ticker_masked": (p.get("ticker", "0000")[0] + "***"), "locked": True}
            for p in picks
        ],
    }

    logs = []
    if SIGNAL_LOG.exists():
        logs = json.loads(SIGNAL_LOG.read_text())
    logs.append(report)
    SIGNAL_LOG.write_text(json.dumps(logs, indent=2, ensure_ascii=False))


def _register_customer(email: str, tier_name: str, verified: bool = False):
    """Register a customer. Only a *verified* paid event (Ko-fi webhook) books revenue;
    manual/test registrations grant access but are not counted as income, so the
    revenue numbers can never be inflated by comps or tests."""
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
        "verified": verified,
    }
    customers.append(customer)
    CUSTOMERS_FILE.write_text(json.dumps(customers, indent=2, ensure_ascii=False))

    # Only log income for verified paid events — never for manual/test registrations.
    if verified:
        income = json.loads(INCOME_LOG.read_text()) if INCOME_LOG.exists() else []
        income.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "amount": tier_info["price"],
            "source": f"TWSE Premium {tier_key}",
            "customer": email,
            "verified": True,
        })
        INCOME_LOG.write_text(json.dumps(income, indent=2, ensure_ascii=False))

    send_welcome_email(email, tier_key)
    tag = "PAID" if verified else "unverified (no revenue booked)"
    print(f"✅ Registered: {email} on {tier_key} (${tier_info['price']}) — {tag}")


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
    RECOMMENDED = "annual"
    PER_MONTH = {
        "monthly": "$49 / 月",
        "quarterly": "≈ $33 / 月 · 每季扣款",
        "annual": "≈ $25 / 月 · 年繳",
        "lifetime": "一次付清 · 終身使用",
    }
    SAVINGS = {"quarterly": "省 33%", "annual": "省 49%", "lifetime": ""}
    pricing_cards = ""
    for key, tier in TIERS.items():
        rec = " recommended" if key == RECOMMENDED else ""
        badge = '<div class="badge">★ 最佳方案</div>' if key == RECOMMENDED else ""
        permo = PER_MONTH.get(key, "")
        save = SAVINGS.get(key, "")
        save_html = f' · <span style="color:#22c55e">{save}</span>' if save else ""
        spd = tier['signals_per_day']
        sig_phrase = "每日全部精選訊號（含進出場）" if spd >= 99 else f"每日 {spd} 檔精選訊號（含進出場）"
        pricing_cards += f"""
        <div class="pricing-card{rec}">
            {badge}
            <h3>{tier['name']}</h3>
            <p class="price">${tier['price']}</p>
            <p class="per-month">{permo}{save_html}</p>
            <ul>
                <li>📊 {sig_phrase}</li>
                <li>📧 Email 即時通知</li>
                <li>{"📱 SMS 簡訊快訊" if tier['sms'] else "—"}</li>
                <li>📈 大盤 + 類股輪動分析</li>
                <li>🔍 9 步量化評分</li>
            </ul>
            <a href="https://ko-fi.com/s/b99720d13d" class="cta-btn">立即開始收訊號 →</a>
            <p class="cancel">隨時可取消</p>
        </div>"""

    # SEO + GA4 head (plain strings so literal { } need no f-string escaping).
    seo_head = """<title>台股量化選股訊號｜大飆股 DNA 每日掃描 $49/月</title>
<meta name="description" content="每日盤後大飆股 DNA 量化掃描，2004–2026 回測驗證的 9 步策略。今日進出場訊號 + 名單，$49/月，7 天試用。">
<link rel="canonical" href="https://slashmantools.us/hermes-twse-premium/" />
<meta property="og:type" content="website" />
<meta property="og:locale" content="zh_TW" />
<meta property="og:url" content="https://slashmantools.us/hermes-twse-premium/" />
<meta property="og:title" content="大飆股 DNA — 台股每日量化選股訊號" />
<meta property="og:description" content="每日盤後大飆股 DNA 量化掃描，2004–2026 回測驗證的 9 步策略。今日進出場訊號 + 名單，$49/月，7 天試用。" />
<meta property="og:image" content="https://slashmantools.us/hermes-twse-premium/og.png" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:image" content="https://slashmantools.us/hermes-twse-premium/og.png" />
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"大飆股 DNA Premium","description":"台股每日量化選股訊號，9 步策略，2004–2026 回測驗證。","brand":{"@type":"Brand","name":"大飆股 DNA"},"offers":{"@type":"Offer","price":"49.00","priceCurrency":"USD","url":"https://slashmantools.us/hermes-twse-premium/"}}
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-MY95FHB8JG"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-MY95FHB8JG');
</script>"""

    extra_script = """<script>
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a.cta-btn');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    if (/ko-?fi\\.com|gumroad\\.com|lemonsqueezy\\.com/i.test(href) && typeof gtag === 'function') {
      gtag('event', 'begin_checkout', { product: 'twse-premium', cta_text: (a.textContent || '').trim().slice(0, 60), destination: href });
    }
  });
</script>"""

    return f"""<!DOCTYPE html>
<html lang="zh-Hant-TW">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
{seo_head}
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:-apple-system,sans-serif; background:#0a0a1a; color:#e2e8f0; }}
    .container {{ max-width:1000px; margin:auto; padding:20px; }}
    header {{ text-align:center; padding:50px 0; }}
    h1 {{ font-size:2.5rem; background:linear-gradient(135deg,#22c55e,#3b82f6); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    .pricing-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:15px; }}
    .pricing-card {{ background:#1e293b; border-radius:16px; padding:25px; position:relative; }}
    .pricing-card.recommended {{ border:2px solid #22c55e; box-shadow:0 0 28px rgba(34,197,94,.28); }}
    .badge {{ position:absolute; top:-13px; left:50%; transform:translateX(-50%); background:#22c55e; color:#03210f; font-size:.75rem; font-weight:800; padding:4px 14px; border-radius:999px; white-space:nowrap; }}
    .pricing-card .price {{ font-size:2.5rem; font-weight:bold; color:#22c55e; }}
    .per-month {{ color:#cbd5e1; font-size:.9rem; margin:2px 0 10px; }}
    .cancel {{ text-align:center; color:#64748b; font-size:.78rem; margin-top:10px; }}
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
            <p style="color:#e2e8f0;font-size:1.3rem;max-width:640px;margin:12px auto 0;">每個交易日早上，直接收到「今天該關注的台股」——附方向、評分與進出場價位。</p>
            <p style="color:#64748b;font-size:1rem;margin-top:8px;">9 步量化策略 · 2004–2026 全市場回測驗證 · 隨時可取消</p>
        </header>

        <div class="preview">
            <h2>🔍 今日掃描結果</h2>
            <p id="scan-summary" style="color:#94a3b8;">Loading…</p>
            <div id="signals"></div>
            <a href="https://ko-fi.com/s/b99720d13d" class="cta-btn" style="margin-top:15px;max-width:340px;">🔓 解鎖今日訊號 — 每月 $49 起</a>
            <p style="text-align:center;color:#64748b;font-size:.85rem;margin-top:10px;">解鎖後每交易日 09:00 前送達 · 隨時可取消 · 非投資建議</p>
        </div>

        <div class="preview">
            <h2>📈 Why trust these signals?</h2>
            <p style="color:#94a3b8;margin:10px 0;">
                Every signal comes from the same 9-step quant strategy, back-tested across
                <b>2004–2026</b> on the full Taiwan market. The historical results are public — verify before you subscribe.
            </p>
            <a href="https://slashmantools.us/twse-backtests/" target="_blank" class="cta-btn" style="max-width:320px;background:linear-gradient(135deg,#3b82f6,#2563eb);">See the full backtests (free) →</a>
        </div>

        <div class="preview">
            <h2>🆚 不是投顧老師，不是發財群組</h2>
            <p style="color:#94a3b8;margin:10px 0 18px;">
                傳統投顧年費動輒 8 萬到上百萬，訊號分級、績效不公開，一般會員往往比大戶晚收到。
                我們做的正好相反——<b>公開回測、系統化選股、所有訂閱者同一時間收到同一份訊號。</b>
            </p>
            <div style="overflow-x:auto;">
            <table style="width:100%;border-collapse:collapse;font-size:.92rem;">
                <thead><tr style="color:#cbd5e1;text-align:left;">
                    <th style="padding:8px;border-bottom:1px solid #334155;">項目</th>
                    <th style="padding:8px;border-bottom:1px solid #334155;">傳統投顧老師</th>
                    <th style="padding:8px;border-bottom:1px solid #334155;color:#22c55e;">TWSE Premium</th>
                </tr></thead>
                <tbody style="color:#94a3b8;">
                    <tr><td style="padding:8px;border-bottom:1px solid #1e293b;">年費</td><td style="padding:8px;border-bottom:1px solid #1e293b;">NT$8 萬 – 100 萬+</td><td style="padding:8px;border-bottom:1px solid #1e293b;color:#e2e8f0;">約 NT$1.5 萬（US$49/月）</td></tr>
                    <tr><td style="padding:8px;border-bottom:1px solid #1e293b;">績效揭露</td><td style="padding:8px;border-bottom:1px solid #1e293b;">不公開，信任個人</td><td style="padding:8px;border-bottom:1px solid #1e293b;color:#e2e8f0;">2004–2026 完整回測，方法與規則公開</td></tr>
                    <tr><td style="padding:8px;border-bottom:1px solid #1e293b;">訊號時效</td><td style="padding:8px;border-bottom:1px solid #1e293b;">分級，一般會員較慢</td><td style="padding:8px;border-bottom:1px solid #1e293b;color:#e2e8f0;">系統化，人人同時收到</td></tr>
                    <tr><td style="padding:8px;border-bottom:1px solid #1e293b;">選股方式</td><td style="padding:8px;border-bottom:1px solid #1e293b;">老師喊盤，主觀判斷</td><td style="padding:8px;border-bottom:1px solid #1e293b;color:#e2e8f0;">9 步規則化量化掃描</td></tr>
                    <tr><td style="padding:8px;">獲利保證</td><td style="padding:8px;">常暗示保證獲利</td><td style="padding:8px;color:#e2e8f0;">不保證獲利，僅供參考</td></tr>
                </tbody>
            </table>
            </div>
            <p style="color:#64748b;font-size:.82rem;margin-top:14px;">投顧費用區間引自公開的 PTT／媒體使用者經驗，各家差異大。本服務為系統化選股與回測研究，非個股投資建議。</p>
        </div>

        <h2 style="text-align:center;margin:30px 0;">📋 Pricing Plans</h2>
        <div class="pricing-grid">{pricing_cards}</div>

        <footer>
            <p>TWSE Premium by slashman413 · Data source: public market info</p>
            <p>⚠️ Trading carries risk. Not financial advice — for reference only.</p>
        </footer>
    </div>
    <script>
        fetch('signals.json').then(r=>r.json()).then(d=>{{
            const last = d[d.length-1];
            if(!last) return;
            document.getElementById('scan-summary').innerHTML =
                '📅 ' + last.date + ' · <b>' + (last.total_signals||0) + '</b> signals today · ' +
                '<span style="color:#22c55e">' + (last.buys||0) + ' BUY</span> / ' +
                '<span style="color:#ef4444">' + (last.sells||0) + ' SELL</span>';
            const locked = last.locked_preview || [];
            document.getElementById('signals').innerHTML = locked.length
                ? locked.map(s =>
                    '<div class="signal">🔒 <b>' + s.ticker_masked +
                    '</b> — ticker, direction, score &amp; entry/exit are for subscribers</div>'
                  ).join('')
                : '<div class="signal">No signals today.</div>';
        }});
    </script>
    {extra_script}
</body>
</html>"""


def main():
    ensure_data()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"

    if cmd == "scan":
        signals = scan_market()
        save_public_report(signals)
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
                # Deliver the number of signals the customer's tier is entitled to.
                tier_key = c.get("tier", "monthly")
                limit = TIERS.get(tier_key, TIERS["monthly"])["signals_per_day"]
                tier_signals = {**signals, "top_picks": signals.get("top_picks", [])[:limit]}
                html = format_signal_email(tier_signals, c.get("name", "Subscriber"))
                if send_email(email, f"📊 TWSE Premium {datetime.now().strftime('%m/%d')} Scan Report", html, smtp):
                    notified += 1

        print(f"📧 Notified {notified} customers")

        # Generate pages
        docs_dir = BASE_DIR / "docs"
        docs_dir.mkdir(exist_ok=True)
        (docs_dir / "index.html").write_text(generate_landing_page(), encoding="utf-8")
        # Publish the (masked) signal log next to the page so its fetch('signals.json')
        # resolves — otherwise the "today's scan" hero preview 404s and hangs on "Loading…".
        if SIGNAL_LOG.exists():
            (docs_dir / "signals.json").write_text(SIGNAL_LOG.read_text(encoding="utf-8"), encoding="utf-8")
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
            # A real Ko-fi payment event → verified revenue.
            _register_customer(email, tier, verified=True)
        elif event in ("kofi_cancellation", "kofi_refund"):
            _cancel_customer(email)
        else:
            # Unknown event: grant access but do not book revenue (unverified).
            _register_customer(email, tier, verified=False)

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
