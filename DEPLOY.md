# CryptoAID Trade AI — Deployment Guide

## 1. Static PWA Deployment (Hostinger Document Root)

The public PWA is accessible at:
[https://trade.cryptoaid.support](https://trade.cryptoaid.support)

### Document Root
```
/home/u173050672/domains/cryptoaid.support/public_html/trade
```

### Static Files Deployed
- `index.html` (Complete 13-page cockpit UI)
- `static/manifest.json` (PWA application manifest)
- `static/sw.js` (Offline Service Worker)
- `static/css/app.css` (Glassmorphism design system)
- `static/js/app.js` (Single-Page Application client controller)

Local synchronization directory in master repo:
`c:\81PLUS_GLOBAL_MASTER\cryptoaid.support\public_html\trade`

---

## 2. Server Runtime Deployment (VPS / Dedicated Instance / Docker)

### Option A: Docker Compose (Recommended)

1. Clone repository:
   ```bash
   git clone https://github.com/destinorandagio/cryptoaid-trade-ai.git
   cd cryptoaid-trade-ai
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env to add TELEGRAM_BOT_TOKEN and TRADING_WALLET_ADDRESS
   ```

3. Build and launch container:
   ```bash
   docker compose up -d --build
   ```

4. View logs:
   ```bash
   docker compose logs -f
   ```

---

### Option B: Systemd Daemon on Linux VPS

1. Create service file `/etc/systemd/system/trade-ai.service`:
   ```ini
   [Unit]
   Description=CryptoAID Trade AI Master Daemon
   After=network.target

   [Service]
   Type=simple
   User=tradeai
   WorkingDirectory=/opt/cryptoaid-trade-ai
   ExecStart=/opt/cryptoaid-trade-ai/.venv/bin/python scripts/run_trade_ai.py
   Restart=always
   RestartSec=5
   EnvironmentFile=/opt/cryptoaid-trade-ai/.env

   [Install]
   WantedBy=multi-user.target
   ```

2. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable trade-ai
   sudo systemctl start trade-ai
   ```

3. Run Watchdog monitor in parallel (via crontab or secondary service):
   ```bash
   */5 * * * * cd /opt/cryptoaid-trade-ai && /opt/cryptoaid-trade-ai/.venv/bin/python scripts/run_watchdog.py >> /var/log/trade_watchdog.log 2>&1
   ```
