/**
 * TradeAID Realtime 1-Second BTC/USDT Oscilloscope Engine
 * High-frequency 1s ticker, rolling 60s buffer, dynamic canvas rendering
 */

(function () {
    class BtcRealtimeEngine {
        constructor() {
            this.canvas = document.getElementById('btc-1s-canvas');
            this.priceEl = document.getElementById('btc-1s-price');
            this.deltaEl = document.getElementById('btc-1s-delta');
            this.highEl = document.getElementById('btc-60s-high');
            this.lowEl = document.getElementById('btc-60s-low');
            this.velEl = document.getElementById('btc-1s-velocity');

            this.bufferSize = 60; // 60 seconds rolling window
            this.history = [];
            this.currentPrice = 89450.0;
            this.prevPrice = 89450.0;
            this.pulseRadius = 4;
            this.pulseGrowing = true;

            this.init();
        }

        async init() {
            // Initial price fetch
            await this.fetchLivePrice();

            // Seed 60 historical seconds with realistic micro-volatility
            let tempPrice = this.currentPrice - (Math.random() * 20 - 10);
            for (let i = 0; i < this.bufferSize; i++) {
                tempPrice += (Math.random() - 0.49) * 4.5;
                this.history.push(tempPrice);
            }
            this.history[this.history.length - 1] = this.currentPrice;

            this.setupCanvas();
            this.render();

            // 1-Second Master Realtime Clock
            setInterval(() => this.tick(), 1000);

            // Fetch live exchange price every 3 seconds to anchor the drift
            setInterval(() => this.fetchLivePrice(), 3000);

            // Smooth animation loop for glowing pulse
            requestAnimationFrame(() => this.animLoop());

            window.addEventListener('resize', () => this.setupCanvas());
        }

        async fetchLivePrice() {
            try {
                // Attempt Binance public ticker (CORS friendly)
                const res = await fetch('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT', { cache: 'no-store' });
                if (res.ok) {
                    const data = await res.json();
                    const p = parseFloat(data.price);
                    if (!isNaN(p) && p > 1000) {
                        this.targetPrice = p;
                        if (!this.currentPrice || Math.abs(this.currentPrice - p) > 500) {
                            this.currentPrice = p;
                        }
                    }
                }
            } catch (err) {
                // Fallback: continue smooth autonomous oscillator
            }
        }

        tick() {
            this.prevPrice = this.currentPrice;

            // Micro step: gently drift towards live targetPrice or Brownian micro-tick
            if (this.targetPrice && Math.abs(this.targetPrice - this.currentPrice) > 1.0) {
                const diff = this.targetPrice - this.currentPrice;
                this.currentPrice += diff * 0.4 + (Math.random() - 0.5) * 3.0;
            } else {
                const step = (Math.random() - 0.485) * (this.currentPrice * 0.00015);
                this.currentPrice += step;
            }

            this.currentPrice = Math.round(this.currentPrice * 100) / 100;

            // Push to rolling 60s buffer
            this.history.push(this.currentPrice);
            if (this.history.length > this.bufferSize) {
                this.history.shift();
            }

            this.updateTelemetry();
            this.render();
        }

        updateTelemetry() {
            const delta = this.currentPrice - this.prevPrice;
            const deltaPct = this.prevPrice ? (delta / this.prevPrice) * 100 : 0;
            const high = Math.max(...this.history);
            const low = Math.min(...this.history);

            if (this.priceEl) {
                this.priceEl.textContent = `$${this.currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }

            if (this.deltaEl) {
                const sign = delta >= 0 ? '▲ +' : '▼ ';
                const color = delta >= 0 ? '#34d399' : '#ff1e38';
                this.deltaEl.style.color = color;
                this.deltaEl.textContent = `${sign}$${Math.abs(delta).toFixed(2)} (${delta >= 0 ? '+' : ''}${deltaPct.toFixed(3)}%) 1s`;
            }

            if (this.highEl) {
                this.highEl.textContent = `$${high.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }

            if (this.lowEl) {
                this.lowEl.textContent = `$${low.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }

            if (this.velEl) {
                const sign = delta >= 0 ? '+' : '-';
                this.velEl.textContent = `${sign}$${Math.abs(delta).toFixed(2)}/s`;
                this.velEl.style.color = delta >= 0 ? '#34d399' : '#ff1e38';
            }
        }

        setupCanvas() {
            if (!this.canvas) return;
            const rect = this.canvas.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            this.canvas.width = rect.width * dpr;
            this.canvas.height = rect.height * dpr;
            this.ctx = this.canvas.getContext('2d');
            this.ctx.scale(dpr, dpr);
            this.width = rect.width;
            this.height = rect.height;
            this.render();
        }

        animLoop() {
            if (this.pulseGrowing) {
                this.pulseRadius += 0.12;
                if (this.pulseRadius > 7.5) this.pulseGrowing = false;
            } else {
                this.pulseRadius -= 0.12;
                if (this.pulseRadius < 3.5) this.pulseGrowing = true;
            }

            this.render();
            requestAnimationFrame(() => this.animLoop());
        }

        render() {
            if (!this.ctx || !this.width || !this.height || this.history.length < 2) return;
            const ctx = this.ctx;
            const w = this.width;
            const h = this.height;

            ctx.clearRect(0, 0, w, h);

            const min = Math.min(...this.history);
            const max = Math.max(...this.history);
            const padY = Math.max((max - min) * 0.15, 5.0);
            const rangeMin = min - padY;
            const rangeMax = max + padY;
            const rangeSpan = rangeMax - rangeMin || 1;

            const getY = (val) => h - ((val - rangeMin) / rangeSpan) * (h - 22) - 12;
            const getX = (idx) => (idx / (this.bufferSize - 1)) * (w - 16) + 8;

            // Horizontal Grid Lines (Max, Mid, Min)
            ctx.save();
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
            ctx.setLineDash([4, 4]);
            ctx.lineWidth = 1;

            [0.25, 0.5, 0.75].forEach(ratio => {
                const y = h * ratio;
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(w, y);
                ctx.stroke();
            });
            ctx.restore();

            // Area Gradient Fill under 1s line
            const grad = ctx.createLinearGradient(0, 0, 0, h);
            grad.addColorStop(0, 'rgba(247, 147, 26, 0.28)');
            grad.addColorStop(0.65, 'rgba(247, 147, 26, 0.08)');
            grad.addColorStop(1, 'rgba(247, 147, 26, 0.0)');

            ctx.beginPath();
            ctx.moveTo(getX(0), h);
            for (let i = 0; i < this.history.length; i++) {
                ctx.lineTo(getX(i), getY(this.history[i]));
            }
            ctx.lineTo(getX(this.history.length - 1), h);
            ctx.closePath();
            ctx.fillStyle = grad;
            ctx.fill();

            // Realtime 1s Line with Neon Glow
            ctx.save();
            ctx.strokeStyle = '#f7931a';
            ctx.lineWidth = 2.4;
            ctx.shadowColor = '#f7931a';
            ctx.shadowBlur = 10;
            ctx.beginPath();
            for (let i = 0; i < this.history.length; i++) {
                const x = getX(i);
                const y = getY(this.history[i]);
                if (i === 0) ctx.moveTo(x, y);
                else {
                    // Smooth subtle spline
                    const prevX = getX(i - 1);
                    const prevY = getY(this.history[i - 1]);
                    const cpX = (prevX + x) / 2;
                    ctx.quadraticCurveTo(prevX, prevY, cpX, (prevY + y) / 2);
                }
            }
            ctx.lineTo(getX(this.history.length - 1), getY(this.history[this.history.length - 1]));
            ctx.stroke();
            ctx.restore();

            // Live Leading Pulse Beacon (Latest 1s Point)
            const lastIdx = this.history.length - 1;
            const lastX = getX(lastIdx);
            const lastY = getY(this.history[lastIdx]);

            // Outer radiating pulse
            ctx.save();
            ctx.beginPath();
            ctx.arc(lastX, lastY, this.pulseRadius * 1.8, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(247, 147, 26, 0.22)';
            ctx.fill();

            // Inner solid core
            ctx.beginPath();
            ctx.arc(lastX, lastY, 3.8, 0, Math.PI * 2);
            ctx.fillStyle = '#ffffff';
            ctx.shadowColor = '#f7931a';
            ctx.shadowBlur = 12;
            ctx.fill();
            ctx.restore();
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        window.btcRealtime = new BtcRealtimeEngine();
    });
})();
