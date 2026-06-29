# TWSE Premium — Automated Customer Flow

## How it works (zero manual work)

When a customer subscribes on Ko-fi:

```
Ko-fi Webhook → GitHub API → Auto-register → Daily emails
     ↑              ↑              ↑              ↑
  Customer        Webhook       premium.py     scan.yml
  pays $49       bridge        adds to        sends signal
                 forwards      customers.     email to
                               json           customer
```

## Setup options

### Option A: Webhook Bridge (fully automated) ⭐ Recommended

1. Deploy `scripts/webhook_bridge.py` on Render (free):
   - Go to https://render.com → New Web Service
   - Connect your GitHub, select this repo
   - Start command: `python scripts/webhook_bridge.py`
   - Add env var: `GITHUB_TOKEN` = your GitHub PAT (repo scope)

2. Get your Render URL: `https://your-app.onrender.com`

3. In Ko-fi: Settings → Webhooks → Add:
   ```
   Webhook URL: https://your-app.onrender.com/webhook
   Method: POST
   ```

4. Done! New subscribers auto-register.

### Option B: Manual Register (from GitHub UI)

When you get a Ko-fi notification email:

1. Go to: https://github.com/slashman413/hermes-twse-premium/actions/workflows/register.yml
2. Click "Run workflow"
3. Enter the customer's email and tier
4. Click "Run" — done!

### Option C: Cancel subscriber

```
gh workflow run register.yml --repo slashman413/hermes-twse-premium \
  --field email=customer@email.com --field tier=monthly
```

Then edit `data/customers.json` → set `"status": "cancelled"`.

## What happens after registration

- **Daily scans**: Automatically run at 09:00 and 13:30 Taipei time (weekdays)
- **Email delivery**: Scan results sent to all active customers
- **Landing page**: Auto-updates with latest signals
- **Income tracking**: Logged to income_log.json

## Pricing tiers

| Tier | Price | Scans/day | SMS |
|------|-------|-----------|-----|
| Monthly | $49 | 2 | No |
| Quarterly | $99 | 4 | No |
| Annual | $299 | 10 | Yes |
