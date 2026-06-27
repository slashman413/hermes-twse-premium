# TWSE Premium — SMTP 設定指南

## 選項 1：Gmail（最簡單，推薦）

1. 開啟 Gmail 兩步驟驗證
2. 到 https://myaccount.google.com/apppasswords 產生 App Password
3. 填入 GitHub Secrets：

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=你的gmail@gmail.com
SMTP_PASSWORD=你的App Password（16碼）
SMTP_FROM=你的gmail@gmail.com
```

4. 到 GitHub repo Settings → Secrets and variables → Actions
5. 新增以上 5 個 secrets

## 選項 2：SendGrid（免費 100封/天）

1. 到 https://sendgrid.com 註冊免費帳號
2. 建立 API Key
3. 填入 GitHub Secrets：

```
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=你的SendGrid API Key
SMTP_FROM=premium@你的域名.com
```

## 選項 3：Mailgun（免費 100封/天）

1. 到 https://www.mailgun.com 註冊
2. 設定寄件域名
3. 取得 SMTP 憑證

---

## 設定後測試

設定完 secrets 後，手動觸發 workflow：

```bash
gh workflow run scan.yml --repo slashman413/hermes-twse-premium
```

或從 GitHub UI 點 "Run workflow"。

首次執行會：
1. 掃描台股技術訊號
2. 產生預覽頁面（GitHub Pages）
3. 嘗試發送 Email 給客戶

---

## GitHub Secrets 設定位置

1. 打開 https://github.com/slashman413/hermes-twse-premium/settings/secrets/actions
2. 點 "New repository secret"
3. 新增以下 secrets：

| Secret | 值 |
|--------|-----|
| SMTP_HOST | smtp.gmail.com |
| SMTP_PORT | 587 |
| SMTP_USER | 你的email |
| SMTP_PASSWORD | 你的密碼 |
| SMTP_FROM | 你的email |
