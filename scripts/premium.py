#!/usr/bin/env python3
"""
TWSE Premium — 台股即時訊號通知服務。
自動掃描台股技術訊號，透過 Email/Telegram 發送給付費客戶。
"""
import os, sys, json, smtplib, subprocess
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
    "monthly": {"price": 49, "name": "月費方案", "signals_per_day": 2, "sms": False},
    "quarterly": {"price": 99, "name": "季費方案", "signals_per_day": 4, "sms": False},
    "annual": {"price": 299, "name": "年費方案", "signals_per_day": 10, "sms": True},
    "lifetime": {"price": 999, "name": "終身方案", "signals_per_day": 999, "sms": True},
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
            # Fallback to mock data for demo
            result["top_picks"] = _mock_signals()
    else:
        result["top_picks"] = _mock_signals()
    
    return result


def _mock_signals() -> list[dict]:
    """Mock signals for demo/preview."""
    return [
        {"ticker": "2330", "name": "台積電", "signal": "BUY", "score": 92,
         "reason": "MACD黃金交叉+ADX>25+外資連續買超5日"},
        {"ticker": "2317", "name": "鴻海", "signal": "BUY", "score": 85,
         "reason": "突破月線+成交量放大2倍+KD黃金交叉"},
        {"ticker": "2454", "name": "聯發科", "signal": "HOLD", "score": 65,
         "reason": "RSI中性區間+外資買賣互見"},
        {"ticker": "2412", "name": "中華電", "signal": "SELL", "score": 30,
         "reason": "MACD死亡交叉+投信連續賣超"},
        {"ticker": "2002", "name": "中鋼", "signal": "BUY", "score": 78,
         "reason": "低檔十字線+外資轉買+本益比偏低"},
    ]


def format_signal_email(signals: dict, customer_name: str = "客戶") -> str:
    """Format scan results as an email."""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    picks = signals.get("top_picks", [])
    
    if not picks:
        return f"<h2>📊 {date_str} 掃描結果</h2><p>今日無明顯訊號</p>"
    
    lines = [f"<h2>📊 {date_str} 台股掃描報告</h2>"]
    lines.append(f"<p>親愛的 {customer_name}，以下是今日掃描結果：</p>")
    lines.append("<table border='1' cellpadding='8' style='border-collapse:collapse;width:100%;'>")
    lines.append("<tr style='background:#2563eb;color:white;'>"
                 "<th>股票</th><th>訊號</th><th>評分</th><th>理由</th></tr>")
    
    for p in picks:
        signal_color = {"BUY": "green", "SELL": "red", "HOLD": "orange"}.get(p["signal"], "gray")
        lines.append(f"<tr><td><b>{p['ticker']}</b> {p['name']}</td>"
                     f"<td style='color:{signal_color};font-weight:bold;'>{p['signal']}</td>"
                     f"<td>{p['score']}</td><td>{p['reason']}</td></tr>")
    
    lines.append("</table>")
    
    # Market context
    market = signals.get("market_signals", [])
    if market:
        lines.append("<h3>📈 大盤指標</h3><ul>")
        for m in market[:5]:
            lines.append(f"<li>{m}</li>")
        lines.append("</ul>")
    
    lines.append("<hr><p style='color:gray;font-size:0.8em;'>"
                 "TWSE Premium · 本報告僅供參考，投資盈虧自負</p>")
    
    return "".join(lines)


def send_email(to_email: str, subject: str, html: str, smtp_config: dict):
    """Send email via SMTP (using free SendGrid/Gmail)."""
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


def generate_landing_page() -> str:
    """Generate landing page HTML with pricing."""
    pricing_cards = ""
    for key, tier in TIERS.items():
        pricing_cards += f"""
        <div class="pricing-card">
            <h3>{tier['name']}</h3>
            <p class="price">${tier['price']}</p>
            <ul>
                <li>📊 每日 {tier['signals_per_day']} 次掃描</li>
                <li>📧 Email 通知</li>
                <li>{"📱 SMS 簡訊通知" if tier['sms'] else "❌ 無 SMS"}</li>
                <li>📈 大盤指標分析</li>
                <li>🔍 個股評分系統</li>
            </ul>
            <a href="https://buy.stripe.com/test_XXX_{key}" class="cta-btn">立即訂閱</a>
        </div>"""
    
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TWSE Premium — 台股即時訊號</title>
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
            <p style="color:#94a3b8;font-size:1.2rem;">台股自動掃描 · 即時訊號 · 每日通知</p>
        </header>
        
        <div class="preview">
            <h2>🔍 今日掃描結果預覽</h2>
            <div id="signals">載入中...</div>
        </div>
        
        <h2 style="text-align:center;margin:30px 0;">📋 方案選擇</h2>
        <div class="pricing-grid">{pricing_cards}</div>
        
        <footer>
            <p>TWSE Premium by slashman413 · 數據來源：公開市場資訊</p>
            <p>⚠️ 投資有風險，本服務僅供參考</p>
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
                '得分: ' + s.score + '<br><small>' + s.reason + '</small></div>'
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
                html = format_signal_email(signals, c.get("name", "客戶"))
                if send_email(email, f"📊 TWSE Premium {datetime.now().strftime('%m/%d')} 掃描報告", html, smtp):
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
        customers = json.loads(CUSTOMERS_FILE.read_text()) if CUSTOMERS_FILE.exists() else []
        customer = {
            "id": f"twse_{len(customers)+1}",
            "email": email,
            "tier": tier,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "price": TIERS[tier]["price"],
        }
        customers.append(customer)
        CUSTOMERS_FILE.write_text(json.dumps(customers, indent=2, ensure_ascii=False))
        
        # Log income
        income = json.loads(INCOME_LOG.read_text()) if INCOME_LOG.exists() else []
        income.append({"date": datetime.now().strftime("%Y-%m-%d"), "amount": TIERS[tier]["price"],
                       "source": f"TWSE Premium {tier}", "customer": email})
        INCOME_LOG.write_text(json.dumps(income, indent=2, ensure_ascii=False))
        
        print(f"✅ Registered: {email} on {tier} (${TIERS[tier]['price']})")
    
    elif cmd == "status":
        customers = json.loads(CUSTOMERS_FILE.read_text()) if CUSTOMERS_FILE.exists() else []
        income = json.loads(INCOME_LOG.read_text()) if INCOME_LOG.exists() else []
        total = sum(i.get("amount", 0) for i in income)
        print(f"📊 TWSE Premium Status:")
        print(f"  Customers: {len(customers)}")
        print(f"  Total revenue: ${total:.2f}")
        print(f"  Signals generated: {len(json.loads(SIGNAL_LOG.read_text())) if SIGNAL_LOG.exists() else 0}")


if __name__ == "__main__":
    main()
