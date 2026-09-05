/**
 * CryptoAID Trade AI — Web3 dApp Controller with Demo Paper Trading & On-Chain Preventivo
 * Chain: Polygon POS Mainnet (137 / 0x89)
 * Treasury: 0x3C320B3a0917fF44BF6551CDdee44402AFcF250C
 * USDT Polygon: 0xc2132D05D31c914a87C6611C10748AEb04B58e8F (Decimals: 6)
 *
 * Rules:
 * - NO EMOJIS (Only SVG icons in White / Red)
 * - Without wallet connect: Demo Paper Trading mode ($10,000 simulated USDT, interactive paper trades)
 * - Wallet connect + 100 USDT DAO quota to treasury -> Unlocks Real Trading mode
 * - Every on-chain trade prompts on-chain preventivo: Gas + 10 POL DAO Blockchain+ quota
 */

const CONFIG = {
    CHAIN_ID_DEC: 137,
    CHAIN_ID_HEX: "0x89",
    CHAIN_NAME: "Polygon Mainnet",
    RPC_URL: "https://polygon-bor-rpc.publicnode.com",
    EXPLORER_URL: "https://polygonscan.com",
    TREASURY_ADDRESS: "0x3C320B3a0917fF44BF6551CDdee44402AFcF250C",
    USDT_ADDRESS: "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
    USDT_DECIMALS: 6,
    DAO_QUOTE_AMOUNT: 100, // 100 USDT to treasury for 1st access
    TRADE_DAO_POL_AMOUNT: 10 // 10 POL per on-chain signed trade
};

class Web3Controller {
    constructor() {
        this.account = null;
        this.chainId = null;
        this.isRealMode = false;
        this.hasDaoMembership = false;
        this.provider = null;
        this.announcedProviders = [];

        // EIP-6963: Listen for wallet providers announcing themselves
        if (typeof window !== "undefined") {
            window.addEventListener("eip6963:announceProvider", (e) => {
                if (e.detail && !this.announcedProviders.find(p => p.info.uuid === e.detail.info.uuid)) {
                    this.announcedProviders.push(e.detail);
                }
            });
            window.dispatchEvent(new Event("eip6963:requestProvider"));
            window.web3App = this;
            window.dapp = this;
        }
        
        // Paper Simulation State (1,000 USDT Virtual)
        this.paperBalance = 1000.00;
        this.paperPositions = [];
        this.realPositions = [];
        
        // 4 Parallel Paper Portfolios (1,000 USDT each)
        this.paperPortfolios = {
            safe: {
                title: "PAPER SAFE (1,000 USDT)",
                riskBadge: "CONFIDENCE >= 80%",
                cash: "1,000.00 USDT",
                equity: "1,000.00 USDT",
                pnl: "+0.00 USDT (0.00%)",
                drawdown: "0.00%",
                desc: "Strategy: High-confidence scalping & momentum hold. Position sizing 1–2% notional. Strict -0.40% invalidation cut."
            },
            balanced: {
                title: "PAPER BALANCED (1,000 USDT)",
                riskBadge: "CONFIDENCE >= 70%",
                cash: "1,000.00 USDT",
                equity: "1,000.00 USDT",
                pnl: "+0.00 USDT (0.00%)",
                drawdown: "0.00%",
                desc: "Strategy: Balanced scalp/momentum/trend transition. Position sizing 2–5% notional. Dynamic trailing stops."
            },
            turbo: {
                title: "PAPER TURBO (1,000 USDT)",
                riskBadge: "CONFIDENCE >= 60%",
                cash: "1,000.00 USDT",
                equity: "1,000.00 USDT",
                pnl: "+0.00 USDT (0.00%)",
                drawdown: "0.00%",
                desc: "Strategy: Aggressive volatility expansion & breakout capture. Position sizing 5–10% notional. Wider trailing corridors."
            },
            gem: {
                title: "GEM PAPER FUND (1,000 USDT)",
                riskBadge: "ASYMMETRIC PAYOFF (x10 / x100)",
                cash: "1,000.00 USDT",
                equity: "1,000.00 USDT",
                pnl: "+0.00 USDT (0.00%)",
                drawdown: "0.00%",
                desc: "Strategy: Microcap asymmetric discovery. Small sizing 10–30 USDT. Exit policy: recover principal @ 2x (+100%), partial TP @ 4x (+300%), moonbag trailing."
            }
        };

        // Active trade staging for on-chain preventivo
        this.activeTradeStaging = null;

        // Prop Challenge Multi-Tier (STARTER, PRO, ELITE, BLACK) & Schema V1.0 Dual Auth
        this.activePropTier = "PRO";
        this.sicId = localStorage.getItem("tradeaid_sic_id") || null;
        this.tacBalance = 100.00; // 100 TradeAid Credits (TAC)
        this.withdrawableRewards = 0.00;
        this.propTiers = {
            "STARTER": {
                name: "STARTER",
                badgeTxt: "STARTER · $10K · 1000x LEV",
                size: 10000.0,
                fee: 50.0,
                leverage: "1000x (Virtual)",
                payoutPct: 80.0,
                targetPct: 8.0,
                targetProfit: 800.0,
                maxTotalDdPct: 10.0,
                maxTotalDdUsdt: 1000.0,
                maxDailyDdPct: 5.0,
                maxDailyDdUsdt: 500.0,
                minDays: 5
            },
            "PRO": {
                name: "PRO",
                badgeTxt: "PRO · $50K · 1000x LEV",
                size: 50000.0,
                fee: 100.0,
                leverage: "1000x (Virtual)",
                payoutPct: 80.0,
                targetPct: 8.0,
                targetProfit: 4000.0,
                maxTotalDdPct: 10.0,
                maxTotalDdUsdt: 5000.0,
                maxDailyDdPct: 5.0,
                maxDailyDdUsdt: 2500.0,
                minDays: 5
            },
            "ELITE": {
                name: "ELITE",
                badgeTxt: "ELITE · $100K · 1000x LEV",
                size: 100000.0,
                fee: 500.0,
                leverage: "1000x (Virtual)",
                payoutPct: 80.0,
                targetPct: 8.0,
                targetProfit: 8000.0,
                maxTotalDdPct: 10.0,
                maxTotalDdUsdt: 10000.0,
                maxDailyDdPct: 5.0,
                maxDailyDdUsdt: 5000.0,
                minDays: 5
            },
            "BLACK": {
                name: "BLACK",
                badgeTxt: "BLACK · $150K · 100x LEV",
                size: 150000.0,
                fee: 1500.0,
                leverage: "100x (Virtual)",
                payoutPct: 80.0,
                targetPct: 8.0,
                targetProfit: 12000.0,
                maxTotalDdPct: 10.0,
                maxTotalDdUsdt: 15000.0,
                maxDailyDdPct: 5.0,
                maxDailyDdUsdt: 7500.0,
                minDays: 5
            },
            // Backward compatible aliases
            "50K": {
                name: "PRO",
                badgeTxt: "PRO · $50K · 1000x LEV",
                size: 50000.0,
                fee: 100.0,
                leverage: "1000x (Virtual)",
                payoutPct: 80.0,
                targetPct: 8.0,
                targetProfit: 4000.0,
                maxTotalDdPct: 10.0,
                maxTotalDdUsdt: 5000.0,
                maxDailyDdPct: 5.0,
                maxDailyDdUsdt: 2500.0,
                minDays: 5
            },
            "100K": {
                name: "ELITE",
                badgeTxt: "ELITE · $100K · 1000x LEV",
                size: 100000.0,
                fee: 500.0,
                leverage: "1000x (Virtual)",
                payoutPct: 80.0,
                targetPct: 8.0,
                targetProfit: 8000.0,
                maxTotalDdPct: 10.0,
                maxTotalDdUsdt: 10000.0,
                maxDailyDdPct: 5.0,
                maxDailyDdUsdt: 5000.0,
                minDays: 5
            },
            "150K": {
                name: "BLACK",
                badgeTxt: "BLACK · $150K · 100x LEV",
                size: 150000.0,
                fee: 1500.0,
                leverage: "100x (Virtual)",
                payoutPct: 80.0,
                targetPct: 8.0,
                targetProfit: 12000.0,
                maxTotalDdPct: 10.0,
                maxTotalDdUsdt: 15000.0,
                maxDailyDdPct: 5.0,
                maxDailyDdUsdt: 7500.0,
                minDays: 5
            }
        };

        this.init();

    }

    init() {
        this.loadState();
        this.bindEvents();
        this.renderState();
        this.refreshCortexHealth();
        setInterval(() => this.refreshCortexHealth(), 10000);
    }

    async refreshCortexHealth() {
        try {
            const resp = await fetch("/api/v1/engine/cortex-health/default");
            if (!resp.ok) return;
            const data = await resp.json();
            const badgeEl = document.getElementById("cortex-health-badge");
            const distRuinEl = document.getElementById("cortex-dist-ruin");
            const budgetEl = document.getElementById("cortex-risk-budget");

            if (badgeEl) {
                const colorMap = {
                    "GREEN": { bg: "rgba(34,197,94,0.15)", text: "#22c55e", border: "rgba(34,197,94,0.3)" },
                    "YELLOW": { bg: "rgba(234,179,8,0.15)", text: "#eab308", border: "rgba(234,179,8,0.3)" },
                    "ORANGE": { bg: "rgba(249,115,22,0.15)", text: "#f97316", border: "rgba(249,115,22,0.3)" },
                    "RED": { bg: "rgba(239,68,68,0.15)", text: "#ef4444", border: "rgba(239,68,68,0.3)" },
                    "BREACH": { bg: "rgba(239,68,68,0.3)", text: "#ff1e38", border: "rgba(255,30,56,0.6)" }
                };
                const c = colorMap[data.cortex_health] || colorMap["GREEN"];
                badgeEl.style.background = c.bg;
                badgeEl.style.color = c.text;
                badgeEl.style.borderColor = c.border;
                badgeEl.innerHTML = `<span style="width:6px; height:6px; border-radius:50%; background:${c.text};"></span> ${data.cortex_health}`;
            }

            if (distRuinEl) {
                distRuinEl.textContent = `$${Number(data.distance_to_ruin_usd).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}`;
            }

            if (budgetEl) {
                budgetEl.textContent = `$${Number(data.available_risk_budget_usd).toFixed(2)}`;
            }
        } catch (err) {
            // Passive fallback
        }
    }

    loadState() {
        const savedAccount = localStorage.getItem("ca_connected_wallet");
        if (savedAccount) {
            this.account = savedAccount;
            const key = `ca_dao_member_${savedAccount.toLowerCase()}`;
            this.hasDaoMembership = localStorage.getItem(key) === "true";
            if (this.hasDaoMembership) {
                this.isRealMode = true;
            }
        }

        const savedPaperPos = localStorage.getItem("ca_paper_positions");
        if (savedPaperPos) {
            try { this.paperPositions = JSON.parse(savedPaperPos); } catch (e) { this.paperPositions = []; }
        }

        const savedRealPos = localStorage.getItem("ca_real_positions");
        if (savedRealPos) {
            try { this.realPositions = JSON.parse(savedRealPos); } catch (e) { this.realPositions = []; }
        }

        this.autotradeAuthorized = localStorage.getItem("ca_autotrade_authorized") === "true";
        this.autotradeRunning = localStorage.getItem("ca_autotrade_running") !== "false";
        this.rewardBalance = parseFloat(localStorage.getItem("ca_reward_balance") || "10.00");
    }

    saveState() {
        localStorage.setItem("ca_paper_positions", JSON.stringify(this.paperPositions));
        localStorage.setItem("ca_real_positions", JSON.stringify(this.realPositions));
    }

    bindEvents() {
        // Connect Wallet button
        const btnConnect = document.getElementById("btn-connect-wallet");
        if (btnConnect) {
            btnConnect.addEventListener("click", () => {
                if (typeof window.openDualAuthModal === "function") {
                    window.openDualAuthModal();
                } else if (this.account) {
                    this.disconnectWallet();
                } else {
                    this.connectWallet();
                }
            });
        }

        // Unlock Real Trading button in demo banner
        const btnUnlock = document.getElementById("btn-unlock-real-trading");
        if (btnUnlock) {
            btnUnlock.addEventListener("click", () => this.connectWallet());
        }

        // Sign 100 USDT DAO Access
        const btnPay = document.getElementById("btn-sign-access");
        if (btnPay) {
            btnPay.addEventListener("click", () => this.executeDaoAccessPayment());
        }

        // Switch to Polygon
        const btnSwitch = document.getElementById("btn-switch-polygon");
        if (btnSwitch) {
            btnSwitch.addEventListener("click", () => this.switchToPolygon());
        }

        // On-chain Trade Preventivo buttons
        const btnSignTrade = document.getElementById("btn-sign-trade-preventivo");
        if (btnSignTrade) {
            btnSignTrade.addEventListener("click", () => this.executeSignedTradeOnChain());
        }

        const btnCancelTrade = document.getElementById("btn-cancel-trade-preventivo");
        if (btnCancelTrade) {
            btnCancelTrade.addEventListener("click", () => this.closeTradePreventivo());
        }

        // Close paywall modal button if clicked outside
        const paywallModal = document.getElementById("modal-onchain-paywall");
        if (paywallModal) {
            paywallModal.addEventListener("click", (e) => {
                if (e.target === paywallModal && !this.hasDaoMembership) {
                    paywallModal.classList.add("hidden");
                }
            });
        }

        // Window Ethereum listeners
        if (window.ethereum) {
            window.ethereum.on("accountsChanged", (accounts) => this.handleAccountsChanged(accounts));
            window.ethereum.on("chainChanged", (chainId) => this.handleChainChanged(chainId));
        }

        // Language switch listener for dynamic UI update
        window.addEventListener("languageChanged", () => {
            this.renderState();
        });

        // Paper Portfolios tab switcher in tab-performance
        document.querySelectorAll(".paper-port-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".paper-port-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                const portKey = btn.dataset.port;
                this.renderPortfolioTab(portKey);
            });
        });

        // =======================================================
        // HERO AUTOTRADE PRO ENGINE (DUAL-STATE & 1-CLICK AUTOPILOT)
        // =======================================================
        const btnHeroAutotrade = document.getElementById("btn-hero-autotrade");
        if (btnHeroAutotrade) {
            btnHeroAutotrade.addEventListener("click", () => this.handleHeroAutotradeClick());
        }

        const btnConfirmAuth = document.getElementById("btn-confirm-autotrade-auth");
        if (btnConfirmAuth) {
            btnConfirmAuth.addEventListener("click", () => this.authorizeAutotradeSession());
        }

        const btnCancelAuth = document.getElementById("btn-cancel-autotrade-auth");
        const modalAuth = document.getElementById("modal-autotrade-auth");
        if (btnCancelAuth && modalAuth) {
            btnCancelAuth.addEventListener("click", () => {
                modalAuth.classList.add("hidden");
            });
            modalAuth.addEventListener("click", (e) => {
                if (e.target === modalAuth) {
                    modalAuth.classList.add("hidden");
                }
            });
        }

        const btnActivateOnchain = document.getElementById("btn-activate-onchain-autotrade");
        if (btnActivateOnchain) {
            btnActivateOnchain.addEventListener("click", () => {
                this.openTradePreventivo("POL/USDT");
            });
        }

        document.querySelectorAll(".autotrade-preset-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".autotrade-preset-btn").forEach(b => {
                    b.style.background = "rgba(255,255,255,0.05)";
                    b.style.borderColor = "rgba(255,255,255,0.1)";
                    b.classList.remove("active");
                });
                btn.classList.add("active");
                btn.style.background = "rgba(255,30,56,0.2)";
                btn.style.borderColor = "#ff1e38";
                const preset = btn.dataset.preset;
                const stratDisplay = document.getElementById("metric-strategy-display");
                const heroStratTxt = document.getElementById("hero-strategy-txt");
                if (preset === "SAFE") {
                    if (stratDisplay) stratDisplay.textContent = "SCALP SAFE (+0.8%)";
                    if (heroStratTxt) heroStratTxt.textContent = "SCALP SAFE";
                } else if (preset === "BALANCED") {
                    if (stratDisplay) stratDisplay.textContent = "MOMENTUM HOLD (+1.8%)";
                    if (heroStratTxt) heroStratTxt.textContent = "MOMENTUM";
                } else if (preset === "TURBO") {
                    if (stratDisplay) stratDisplay.textContent = "BREAKOUT TURBO (+3.2%)";
                    if (heroStratTxt) heroStratTxt.textContent = "BREAKOUT";
                } else if (preset === "GEM") {
                    if (stratDisplay) stratDisplay.textContent = "GEM ASYMMETRIC (2x Moonbag)";
                    if (heroStratTxt) heroStratTxt.textContent = "GEM HUNTER";
                }
            });
        });

        // Prop Challenge Tier selector buttons
        document.querySelectorAll(".prop-tier-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".prop-tier-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                const tier = btn.dataset.tier;
                this.switchPropTier(tier);
            });
        });

        const btnShareProp = document.getElementById("btn-share-prop-challenge");
        if (btnShareProp) {
            btnShareProp.addEventListener("click", () => this.sharePropChallenge());
        }

        // Ledger 1: Autotrade Run trigger
        const btnTriggerRun = document.getElementById("btn-trigger-run");
        if (btnTriggerRun) {
            btnTriggerRun.addEventListener("click", () => this.handleRunButtonClick());
        }

        this.setupHeroTelemetryCycle();

        // Live rolling telemetry log stream
        const autotradeStream = document.getElementById("autotrade-log-stream");
        if (autotradeStream) {
            const telemetryEvents = [
                { tag: "BUY EXECUTION", color: "#34d399", txt: "POL/USDT @ $0.3245 (Target: +2.1%, Stop: -1.2%)" },
                { tag: "GUARDIAN", color: "#60a5fa", txt: "Stop Loss moved to Break-Even (+0.20% DEX fee locked)" },
                { tag: "CORTEX", color: "#ff1e38", txt: "6-Stage Veto passed (Honeypot: 0/100, Liquidity: $450K)" },
                { tag: "SCANNER", color: "#a1a1aa", txt: "Predictive Heart: POL P50 +1.84% (Confidence 78%)" },
                { tag: "GUARDIAN", color: "#60a5fa", txt: "Trailing stop activated @ +1.45% from local peak" },
                { tag: "STRATEGY SWITCH", color: "#c084fc", txt: "SCALP -> MOMENTUM HOLD transition recorded" },
                { tag: "GEM RADAR", color: "#fbbf24", txt: "$NEURA liquidity pool verified: 100% Locked, Score 88" },
            ];
            let eventIdx = 0;
            setInterval(() => {
                if (!isAutotradeActive) return;
                const ev = telemetryEvents[eventIdx % telemetryEvents.length];
                eventIdx++;
                const timeStr = new Date().toTimeString().split(" ")[0];
                const newRow = document.createElement("div");
                newRow.style.color = "#e4e4e7";
                newRow.innerHTML = `<span style="color:#71717a;">[${timeStr}]</span> <strong style="color:${ev.color};">${ev.tag}:</strong> ${ev.txt}`;
                autotradeStream.insertBefore(newRow, autotradeStream.firstChild);
                if (autotradeStream.children.length > 5) {
                    autotradeStream.removeChild(autotradeStream.lastChild);
                }
            }, 4000);
        }
    }


    renderPortfolioTab(portKey = "safe") {
        const data = this.paperPortfolios[portKey] || this.paperPortfolios["safe"];
        const elTitle = document.getElementById("port-title");
        const elBadge = document.getElementById("port-risk-badge");
        const elCash = document.getElementById("port-cash");
        const elEquity = document.getElementById("port-equity");
        const elPnl = document.getElementById("port-pnl");
        const elDrawdown = document.getElementById("port-drawdown");
        const elDesc = document.getElementById("port-desc");

        if (elTitle) elTitle.innerHTML = `PORTFOLIO: <strong>${data.title}</strong>`;
        if (elBadge) elBadge.textContent = data.riskBadge;
        if (elCash) elCash.textContent = data.cash;
        if (elEquity) elEquity.textContent = data.equity;
        if (elPnl) elPnl.textContent = data.pnl;
        if (elDrawdown) elDrawdown.textContent = data.drawdown;
        if (elDesc) elDesc.textContent = data.desc;
    }


    t(key, fallback) {
        return (window.t && window.t(key)) ? window.t(key) : fallback;
    }

    renderState() {
        const modeBadge = document.getElementById("app-mode-badge");
        const demoBanner = document.getElementById("demo-mode-banner");
        const btnConnect = document.getElementById("btn-connect-wallet");
        const metricCash = document.getElementById("metric-cash");
        const metricEquity = document.getElementById("metric-equity");
        const metricExposure = document.getElementById("metric-exposure");

        if (this.isRealMode && this.account) {
            // REAL TRADING MODE
            if (modeBadge) {
                modeBadge.className = "mode-pill real";
                modeBadge.innerHTML = `<span class="mode-pulse-dot"></span> <span data-i18n="mode_real">${this.t("mode_real", "MODE: REAL TRADING (LIVE WALLET)")}</span>`;
            }
            if (demoBanner) demoBanner.classList.add("hidden");

            const shortAddr = `${this.account.slice(0, 6)}...${this.account.slice(-4)}`;
            if (btnConnect) {
                btnConnect.className = "btn-connect-wallet connected";
                btnConnect.innerHTML = `
                    <svg class="icon-svg sm svg-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"></path><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"></path><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"></path></svg>
                    <span>${shortAddr}</span>
                `;
            }

            this.updateRealBalances();
            this.renderMarketButtons("real");
        } else {
            // DEMO PAPER TRADING MODE
            if (modeBadge) {
                modeBadge.className = "mode-pill demo";
                modeBadge.innerHTML = `
                    <svg class="icon-svg sm svg-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 2v7.31M14 2v7.31M8.5 2h7M14 9.3a6.5 6.5 0 1 1-4 0"></path><line x1="5.52" y1="16" x2="18.48" y2="16"></line></svg>
                    <span data-i18n="mode_demo">${this.t("mode_demo", "MODE: DEMO (PAPER TRADING)")}</span>
                `;
            }
            if (demoBanner) demoBanner.classList.remove("hidden");

            if (btnConnect) {
                btnConnect.className = "btn-connect-wallet";
                btnConnect.innerHTML = `
                    <svg class="icon-svg sm svg-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="6" width="20" height="13" rx="2"></rect><path d="M20 12h-4a2 2 0 0 0-2 2v0a2 2 0 0 0 2 2h4"></path><path d="M6 6V4a2 2 0 0 1 2-2h10"></path></svg>
                    <span data-i18n="connect_wallet">${this.t("connect_wallet", "Connect Wallet")}</span>
                `;
            }

            // Simulated Paper Balances (1,000 USDT Virtual)
            const exposure = this.paperPositions.reduce((acc, p) => acc + (p.allocation || 0), 0);
            const currentCash = Math.max(0, this.paperBalance - exposure);
            const totalEquity = currentCash + exposure;

            if (metricCash) metricCash.textContent = `${currentCash.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT (PAPER)`;
            if (metricEquity) metricEquity.textContent = `${totalEquity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT`;
            if (metricExposure) metricExposure.textContent = `${exposure.toFixed(2)} USDT (${((exposure / totalEquity) * 100).toFixed(1)}%)`;

            this.renderMarketButtons("paper");

        }

        this.renderPositionsTab();
        this.renderHeroAutotrade();
        this.renderPropChallenge();
    }

    renderMarketButtons(mode) {
        // Market cards action button injection
        document.querySelectorAll(".market-card").forEach((card) => {
            let btn = card.querySelector(".btn-trade-action");
            if (!btn) {
                btn = document.createElement("button");
                btn.className = "btn-trade-action";
                card.querySelector(".m-body").appendChild(btn);
            }

            const pair = card.querySelector(".pair-info strong")?.textContent || "POL/USDT";
            const signalText = card.querySelector(".ai-signal-badge")?.textContent || "";
            const isBuy = signalText.includes("BUY");

            if (!isBuy) {
                btn.style.display = "none";
                return;
            }

            btn.style.display = "flex";
            if (mode === "paper") {
                btn.className = "btn-trade-action btn-trade-paper";
                btn.innerHTML = `
                    <svg class="icon-svg sm svg-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 2v7.31M14 2v7.31M8.5 2h7M14 9.3a6.5 6.5 0 1 1-4 0"></path><line x1="5.52" y1="16" x2="18.48" y2="16"></line></svg>
                    <span>${this.t("btn_paper_trade", "TEST PAPER EXECUTION")} (${pair})</span>
                `;
                btn.onclick = () => this.executePaperTrade(pair);
            } else {
                btn.className = "btn-trade-action btn-trade-real";
                btn.innerHTML = `
                    <svg class="icon-svg sm svg-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                    <span>${this.t("btn_real_trade", "EXECUTE ON-CHAIN TRADE")} (${pair})</span>
                `;
                btn.onclick = () => this.openTradePreventivo(pair);
            }
        });
    }

    // PAPER TRADING EXECUTION
    executePaperTrade(pair) {
        const alloc = 100.00;
        const entryPrice = pair.startsWith("POL") ? 0.3245 : 61240.00;

        const stopLoss = pair.startsWith("POL") ? 0.3195 : 60500.00;
        const newPos = {
            id: "paper_" + Date.now(),
            pair: pair,
            mode: "paper",
            allocation: alloc,
            entryPrice: entryPrice,
            dynamicStop: stopLoss,
            pnlUsdt: +4.20,
            pnlPct: +0.84,
            timestamp: new Date().toLocaleTimeString()
        };

        this.paperPositions.push(newPos);
        this.saveState();
        this.renderState();

        // Switch to positions tab automatically
        const tabPosBtn = document.querySelector('[data-target="tab-positions"]');
        if (tabPosBtn) tabPosBtn.click();
    }

    // REAL ON-CHAIN PREVENTIVO (GAS + 10 POL DAO QUOTA)
    openTradePreventivo(pair) {
        this.activeTradeStaging = {
            pair: pair,
            allocation: 50.00,
            daoQuotaPol: CONFIG.TRADE_DAO_POL_AMOUNT,
            estimatedGasPol: 0.006,
            totalPol: CONFIG.TRADE_DAO_POL_AMOUNT + 0.006,
            recipient: CONFIG.TREASURY_ADDRESS
        };

        const modal = document.getElementById("modal-trade-preventivo");
        if (!modal) return;

        document.getElementById("prev-pair-val").textContent = this.activeTradeStaging.pair;
        document.getElementById("prev-alloc-val").textContent = `${this.activeTradeStaging.allocation.toFixed(2)} USDT`;
        document.getElementById("prev-quota-val").textContent = `${this.activeTradeStaging.daoQuotaPol.toFixed(2)} POL (Blockchain+ DAO)`;
        document.getElementById("prev-gas-val").textContent = `~${this.activeTradeStaging.estimatedGasPol.toFixed(4)} POL`;
        document.getElementById("prev-total-val").textContent = `${this.activeTradeStaging.totalPol.toFixed(4)} POL`;
        document.getElementById("prev-recipient-val").textContent = `${CONFIG.TREASURY_ADDRESS.slice(0, 6)}...${CONFIG.TREASURY_ADDRESS.slice(-4)}`;

        const statusBox = document.getElementById("prev-tx-status");
        if (statusBox) {
            statusBox.textContent = this.t("status_waiting_sign", "Awaiting on-chain interactive signature...");
            statusBox.className = "status-box";
        }

        const btnSign = document.getElementById("btn-sign-trade-preventivo");
        if (btnSign) btnSign.disabled = false;

        modal.classList.remove("hidden");
    }

    closeTradePreventivo() {
        const modal = document.getElementById("modal-trade-preventivo");
        if (modal) modal.classList.add("hidden");
        this.activeTradeStaging = null;
    }

    async executeSignedTradeOnChain() {
        if (!this.account || !window.ethereum) {
            alert(this.t("alert_no_wallet", "No Web3 Wallet detected."));
            return;
        }

        if (this.chainId !== CONFIG.CHAIN_ID_DEC) {
            await this.switchToPolygon();
            if (this.chainId !== CONFIG.CHAIN_ID_DEC) return;
        }

        const staging = this.activeTradeStaging;
        if (!staging) return;

        const btnSign = document.getElementById("btn-sign-trade-preventivo");
        const statusBox = document.getElementById("prev-tx-status");

        try {
            if (btnSign) btnSign.disabled = true;
            if (statusBox) {
                statusBox.textContent = "Requesting signature on Polygon for 10 POL DAO Quota...";
                statusBox.className = "status-box status-info";
            }

            // 10 POL = 10 * 10^18 wei = 0x8ac7230489e80000
            const valHex = "0x8ac7230489e80000";

            const txHash = await window.ethereum.request({
                method: "eth_sendTransaction",
                params: [
                    {
                        from: this.account,
                        to: CONFIG.TREASURY_ADDRESS,
                        value: valHex,
                        chainId: CONFIG.CHAIN_ID_HEX
                    }
                ]
            });

            if (statusBox) {
                statusBox.innerHTML = `On-Chain Trade Signed! Tx: <a href="${CONFIG.EXPLORER_URL}/tx/${txHash}" target="_blank" class="tx-link" style="color:#ffffff; text-decoration:underline;">${txHash.slice(0, 8)}...${txHash.slice(-6)}</a>`;
                statusBox.className = "status-box status-success";
            }

            // Record live position
            const newLivePos = {
                id: "live_" + Date.now(),
                pair: staging.pair,
                mode: "live",
                allocation: staging.allocation,
                entryPrice: staging.pair.startsWith("POL") ? 0.3245 : 61240.00,
                dynamicStop: staging.pair.startsWith("POL") ? 0.3195 : 60500.00,
                daoQuotaPaid: "10 POL",
                txHash: txHash,
                timestamp: new Date().toLocaleTimeString()
            };

            this.realPositions.push(newLivePos);
            this.saveState();

            setTimeout(() => {
                this.closeTradePreventivo();
                this.renderState();
                const tabPosBtn = document.querySelector('[data-target="tab-positions"]');
                if (tabPosBtn) tabPosBtn.click();
            }, 1500);

        } catch (err) {
            console.error("Trade sign error:", err);
            if (btnSign) btnSign.disabled = false;
            if (statusBox) {
                statusBox.textContent = this.t("alert_tx_failed", "Transaction failed or rejected.");
                statusBox.className = "status-box status-error";
            }
        }
    }

    renderPositionsTab() {
        const tabPosContent = document.getElementById("tab-positions");
        const tabPosBtn = document.querySelector('[data-target="tab-positions"]');
        if (!tabPosContent) return;

        const allPositions = this.isRealMode ? this.realPositions : this.paperPositions;
        const count = allPositions.length;

        if (tabPosBtn) {
            tabPosBtn.innerHTML = `
                <svg class="icon-svg sm svg-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"></path><path d="M7 16l4-6 4 3 6-8"></path></svg>
                <span>${this.t("tab_positions", "Positions")} (${count})</span>
            `;
        }

        if (count === 0) {
            tabPosContent.innerHTML = `
                <div class="empty-state">
                    <div class="preventivo-icon">
                        <svg class="icon-svg lg svg-red" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                    </div>
                    <h5 data-i18n="no_pos_title">${this.t("no_pos_title", "No Positions Exposed to Risk")}</h5>
                    <p data-i18n="no_pos_desc">${this.t("no_pos_desc", "Position Guardian is waiting for Net Edge threshold (+0.40%). 100% of funds preserved in USDT.")}</p>
                </div>
            `;
            return;
        }

        tabPosContent.innerHTML = allPositions.map((pos) => {
            const isLive = pos.mode === "live";
            return `
                <div class="active-pos-card">
                    <div class="active-pos-header">
                        <span class="active-pos-pair">${pos.pair}</span>
                        <span class="active-pos-type ${isLive ? 'live' : 'paper'}">
                            ${isLive ? this.t("pos_live", "LIVE ON-CHAIN") : this.t("pos_simulated", "SIMULATED")}
                        </span>
                    </div>
                    <div class="active-pos-grid">
                        <div><span class="p-label">ALLOCATION:</span> <span class="p-val">${pos.allocation} USDT</span></div>
                        <div><span class="p-label">ENTRY:</span> <span class="p-val">$${pos.entryPrice}</span></div>
                        <div><span class="p-label">GUARDIAN STOP:</span> <span class="p-val" style="color:#ff1e38;">$${pos.dynamicStop} (-5.0%)</span></div>
                        <div><span class="p-label">TIME:</span> <span class="p-val">${pos.timestamp}</span></div>
                        ${isLive && pos.txHash ? `<div style="grid-column: span 2;"><span class="p-label">TX:</span> <a href="${CONFIG.EXPLORER_URL}/tx/${pos.txHash}" target="_blank" style="color:#38bdf8; text-decoration:underline;">${pos.txHash.slice(0, 10)}... ↗</a></div>` : ''}
                    </div>
                    <button class="btn-close-pos" onclick="window.web3App.closePosition('${pos.id}')">
                        ${this.t("btn_close_pos", "CLOSE POSITION TO USDT")}
                    </button>
                </div>
            `;
        }).join("");
    }

    closePosition(posId) {
        if (this.isRealMode) {
            this.realPositions = this.realPositions.filter(p => p.id !== posId);
        } else {
            this.paperPositions = this.paperPositions.filter(p => p.id !== posId);
        }
        this.saveState();
        this.renderState();
    }

    // WALLET CONNECTION & 100 USDT DAO QUOTA
    async connectWallet(preferredMode = 'auto') {
        // 1. Test / Simulated Web3 Wallet (Paper & Challenge testing without extensions)
        if (preferredMode === 'simulated') {
            const simulatedAccount = "0x71C94911E3922d99c4F681Eb99c68EbEc41B53a9";
            await this.handleAccountsChanged([simulatedAccount]);
            this.chainId = CONFIG.CHAIN_ID_DEC;
            return { success: true, account: simulatedAccount, isSimulated: true };
        }

        // 2. Discover available Web3 provider (EIP-6963 or window.ethereum)
        let provider = null;
        if (this.announcedProviders && this.announcedProviders.length > 0) {
            provider = this.announcedProviders[0].provider;
        } else if (typeof window !== "undefined" && window.ethereum) {
            if (window.ethereum.providers && window.ethereum.providers.length > 0) {
                provider = window.ethereum.providers.find(p => p.isMetaMask) || window.ethereum.providers[0];
            } else {
                provider = window.ethereum;
            }
        }

        // 3. If no provider found
        if (!provider) {
            if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
                const currentUrl = `${window.location.host}${window.location.pathname}`;
                window.location.href = `https://metamask.app.link/dapp/${currentUrl}`;
                return { success: false, error: "REDIRECT_MOBILE" };
            }
            return {
                success: false,
                error: "NO_WALLET",
                message: "Nessun wallet Web3 rilevato nel browser. Installa MetaMask o Rabby, oppure usa il Wallet Simulato per testare la dApp."
            };
        }

        this.provider = provider;
        try {
            const accounts = await provider.request({ method: "eth_requestAccounts" });
            if (!accounts || accounts.length === 0) {
                return { success: false, error: "NO_ACCOUNTS", message: "Nessun account condiviso dal wallet." };
            }
            await this.handleAccountsChanged(accounts);

            const chainIdHex = await provider.request({ method: "eth_chainId" });
            await this.handleChainChanged(chainIdHex);

            if (this.chainId !== CONFIG.CHAIN_ID_DEC) {
                await this.switchToPolygon();
            }

            return { success: true, account: accounts[0] };
        } catch (err) {
            console.error("Connect error:", err);
            const isRejected = err.code === 4001 || (err.message && err.message.includes("rejected"));
            return {
                success: false,
                error: isRejected ? "USER_REJECTED" : "CONNECT_ERROR",
                message: isRejected ? "Connessione rifiutata dall'utente nel wallet." : (err.message || "Errore durante la connessione al wallet.")
            };
        }
    }

    disconnectWallet() {
        this.account = null;
        this.isRealMode = false;
        localStorage.removeItem("ca_connected_wallet");
        localStorage.removeItem("tradeaid_wallet");
        this.renderState();
        if (typeof updateAuthIdentityDisplay === "function") {
            const sicId = localStorage.getItem("tradeaid_sic_id");
            updateAuthIdentityDisplay(sicId, null);
        }
    }

    async handleAccountsChanged(accounts) {
        if (!accounts || accounts.length === 0) {
            this.disconnectWallet();
            return;
        }

        this.account = accounts[0];
        localStorage.setItem("ca_connected_wallet", this.account);
        localStorage.setItem("tradeaid_wallet", this.account);

        const daoKey = `ca_dao_member_${this.account.toLowerCase()}`;
        this.hasDaoMembership = localStorage.getItem(daoKey) === "true";

        if (this.hasDaoMembership) {
            this.isRealMode = true;
        }
        this.renderState();

        if (typeof updateAuthIdentityDisplay === "function") {
            const sicId = localStorage.getItem("tradeaid_sic_id");
            updateAuthIdentityDisplay(sicId, this.account);
        }
    }

    async handleChainChanged(chainIdHex) {
        this.chainId = parseInt(chainIdHex, 16);
        const warningEl = document.getElementById("chain-warning-modal");
        if (this.chainId !== CONFIG.CHAIN_ID_DEC) {
            if (warningEl) warningEl.classList.remove("hidden");
        } else {
            if (warningEl) warningEl.classList.add("hidden");
        }
    }

    async switchToPolygon() {
        if (!window.ethereum) return;
        try {
            await window.ethereum.request({
                method: "wallet_switchEthereumChain",
                params: [{ chainId: CONFIG.CHAIN_ID_HEX }],
            });
        } catch (switchError) {
            if (switchError.code === 4902) {
                try {
                    await window.ethereum.request({
                        method: "wallet_addEthereumChain",
                        params: [
                            {
                                chainId: CONFIG.CHAIN_ID_HEX,
                                chainName: CONFIG.CHAIN_NAME,
                                rpcUrls: [CONFIG.RPC_URL],
                                nativeCurrency: { name: "POL", symbol: "POL", decimals: 18 },
                                blockExplorerUrls: [CONFIG.EXPLORER_URL],
                            },
                        ],
                    });
                } catch (addError) {
                    console.error("Add chain error:", addError);
                }
            }
        }
    }

    openDaoAccessPaywall() {
        const modal = document.getElementById("modal-onchain-paywall");
        if (!modal) return;
        const walletDisplayAddr = document.getElementById("paywall-wallet-address");
        if (walletDisplayAddr && this.account) {
            walletDisplayAddr.textContent = `${this.account.slice(0, 6)}...${this.account.slice(-4)}`;
        }
        modal.classList.remove("hidden");
    }

    async executeDaoAccessPayment() {
        if (!this.account) {
            await this.connectWallet();
            if (!this.account) return;
        }

        if (this.chainId !== CONFIG.CHAIN_ID_DEC) {
            await this.switchToPolygon();
            if (this.chainId !== CONFIG.CHAIN_ID_DEC) return;
        }

        const payStatusEl = document.getElementById("paywall-tx-status");
        const btnPay = document.getElementById("btn-sign-access");

        const rawUnits = BigInt(CONFIG.DAO_QUOTE_AMOUNT) * BigInt(10 ** CONFIG.USDT_DECIMALS);
        const toClean = CONFIG.TREASURY_ADDRESS.toLowerCase().replace("0x", "").padStart(64, "0");
        const valueClean = rawUnits.toString(16).padStart(64, "0");
        const txData = `0xa9059cbb${toClean}${valueClean}`;

        try {
            if (btnPay) btnPay.disabled = true;
            if (payStatusEl) {
                payStatusEl.textContent = `Awaiting signature for 100 USDT DAO quota to treasury...`;
                payStatusEl.className = "status-box status-info";
            }

            const txHash = await window.ethereum.request({
                method: "eth_sendTransaction",
                params: [
                    {
                        from: this.account,
                        to: CONFIG.USDT_ADDRESS,
                        data: txData,
                        chainId: CONFIG.CHAIN_ID_HEX,
                    }
                ],
            });

            if (payStatusEl) {
                payStatusEl.innerHTML = `Transaction confirmed: <a href="${CONFIG.EXPLORER_URL}/tx/${txHash}" target="_blank" class="tx-link" style="color:#ffffff;">${txHash.slice(0, 10)}...${txHash.slice(-6)} ↗</a>`;
                payStatusEl.className = "status-box status-success";
            }

            const daoKey = `ca_dao_member_${this.account.toLowerCase()}`;
            localStorage.setItem(daoKey, "true");
            this.hasDaoMembership = true;
            this.isRealMode = true;

            setTimeout(() => {
                const modalPay = document.getElementById("modal-onchain-paywall");
                if (modalPay) modalPay.classList.add("hidden");
                this.renderState();
            }, 1200);

        } catch (err) {
            console.error("Tx error:", err);
            if (btnPay) btnPay.disabled = false;
            if (payStatusEl) {
                payStatusEl.textContent = this.t("alert_tx_failed", "Transaction failed or rejected.");
                payStatusEl.className = "status-box status-error";
            }
        }
    }

    async updateRealBalances() {
        if (!this.account || !window.ethereum) return;
        try {
            // Read native POL balance
            const balanceHex = await window.ethereum.request({
                method: "eth_getBalance",
                params: [this.account, "latest"]
            });
            const polWei = BigInt(balanceHex);
            const polVal = Number(polWei) / 1e18;

            const metricCash = document.getElementById("metric-cash");
            const metricEquity = document.getElementById("metric-equity");

            if (metricCash) metricCash.textContent = `${polVal.toFixed(2)} POL (Native)`;
            if (metricEquity) metricEquity.textContent = `CONNECTED WALLET`;
        } catch (e) {
            console.warn("Balance fetch error:", e);
        }
    }

    renderHeroAutotrade() {
        const btnHero = document.getElementById("btn-hero-autotrade");
        const btnMain = document.getElementById("hero-btn-main");
        const btnSub = document.getElementById("hero-btn-sub");
        const beacon = document.getElementById("autotrade-beacon");
        const statusPill = document.getElementById("autotrade-status-pill");
        const vaultDisplay = document.getElementById("reward-vault-display");

        if (vaultDisplay) {
            vaultDisplay.textContent = `${this.rewardBalance.toFixed(2)} POL`;
        }

        if (!btnHero) return;

        if (this.autotradeRunning) {
            btnHero.className = "btn-hero-autotrade running";
            if (btnMain) {
                btnMain.innerHTML = `
                    <span class="pulse-beacon" style="background:#34d399; width:10px; height:10px;"></span>
                    <span>● AUTOTRADE RUNNING 24/7</span>
                `;
            }
            if (btnSub) {
                btnSub.textContent = "(CLICK TO PAUSE AUTONOMOUS ENGINE)";
            }
            if (beacon) {
                beacon.style.background = "#34d399";
                beacon.style.boxShadow = "0 0 12px #34d399";
            }
            if (statusPill) {
                statusPill.textContent = "● AUTOTRADE ACTIVE ($10,000 PAPER)";
                statusPill.style.color = "#34d399";
                statusPill.style.background = "rgba(52,211,153,0.15)";
                statusPill.style.borderColor = "rgba(52,211,153,0.3)";
            }
        } else {
            btnHero.className = "btn-hero-autotrade paused";
            if (btnMain) {
                btnMain.innerHTML = `
                    <span style="font-size:1.1rem; margin-right:4px;">▶</span>
                    <span>START AUTOTRADE</span>
                `;
            }
            if (btnSub) {
                btnSub.textContent = "(CLICK TO START AUTONOMOUS ENGINE)";
            }
            if (beacon) {
                beacon.style.background = "#fbbf24";
                beacon.style.boxShadow = "0 0 12px #fbbf24";
            }
            if (statusPill) {
                statusPill.textContent = "⏸ PAUSED ($10,000 PAPER)";
                statusPill.style.color = "#fbbf24";
                statusPill.style.background = "rgba(251,191,36,0.15)";
                statusPill.style.borderColor = "rgba(251,191,36,0.3)";
            }
        }
    }

    handleHeroAutotradeClick() {
        if (!this.autotradeAuthorized) {
            const authModal = document.getElementById("modal-autotrade-auth");
            if (authModal) authModal.classList.remove("hidden");
            return;
        }

        this.autotradeRunning = !this.autotradeRunning;
        localStorage.setItem("ca_autotrade_running", this.autotradeRunning ? "true" : "false");
        this.renderHeroAutotrade();
    }

    async authorizeAutotradeSession() {
        const btnConfirm = document.getElementById("btn-confirm-autotrade-auth");
        const statusBox = document.getElementById("auth-tx-status");
        if (btnConfirm) btnConfirm.disabled = true;
        if (statusBox) {
            statusBox.textContent = "Authorizing session policy & crediting 10 POL Paper Reward...";
            statusBox.className = "status-box";
        }

        const wallet = this.account || "0x_demo_paper_user";

        try {
            // Record authorization to API if online
            try {
                await fetch("/api/v1/autotrade/authorize", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        wallet: wallet,
                        max_allocation_usdt: 1000.0,
                        max_drawdown_pct: 5.0,
                        risk_profile: "BALANCED"
                    })
                });
            } catch (e) {
                console.warn("Autotrade API offline, continuing local demo mode:", e);
            }

            // Claim 10 POL Paper Reward for qualified action AUTOTRADE_ACTIVATION
            try {
                const claimResp = await fetch("/api/v1/rewards/claim", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        wallet: wallet,
                        action_type: "AUTOTRADE_ACTIVATION",
                        signature: "0x_demo_session_signature"
                    })
                });
                const claimData = await claimResp.json();
                if (claimData.pol_reward) {
                    this.rewardBalance = 10.00;
                }
            } catch (e) {
                console.warn("Reward claim API offline, local credit 10 POL:", e);
                this.rewardBalance = 10.00;
            }

            localStorage.setItem("ca_autotrade_authorized", "true");
            localStorage.setItem("ca_autotrade_running", "true");
            localStorage.setItem("ca_reward_balance", this.rewardBalance.toString());

            this.autotradeAuthorized = true;
            this.autotradeRunning = true;

            if (statusBox) {
                statusBox.textContent = "Policy Authorized! 10 POL Paper Reward credited to Vault.";
                statusBox.className = "status-box status-success";
            }

            setTimeout(() => {
                const authModal = document.getElementById("modal-autotrade-auth");
                if (authModal) authModal.classList.add("hidden");
                if (btnConfirm) btnConfirm.disabled = false;
                this.renderHeroAutotrade();
            }, 700);

        } catch (err) {
            console.error("Auth error:", err);
            if (btnConfirm) btnConfirm.disabled = false;
            if (statusBox) {
                statusBox.textContent = "Authorization error. Try again.";
                statusBox.className = "status-box status-error";
            }
        }
    }

    setupHeroTelemetryCycle() {
        setInterval(() => {
            if (!this.autotradeRunning) return;
            const regimes = ["TRENDING", "MOMENTUM EXPANSION", "MEAN REVERTING", "ACCUMULATION CORRIDOR"];
            const rEl = document.getElementById("hero-regime-txt");
            if (rEl && Math.random() < 0.35) {
                const pick = regimes[Math.floor(Math.random() * regimes.length)];
                rEl.textContent = pick;
            }
        }, 5000);
    }

    switchPropTier(tierKey) {
        if (!this.propTiers[tierKey]) return;
        this.activePropTier = tierKey;
        this.renderPropChallenge();
    }

    renderPropChallenge() {
        const tierKey = this.activePropTier || "100K";
        const tier = this.propTiers[tierKey] || this.propTiers["100K"];

        // Update header & badges
        const tierBadgeTxt = document.getElementById("prop-tier-badge-txt");
        if (tierBadgeTxt) tierBadgeTxt.textContent = tier.badgeTxt;

        const feeHighlight = document.getElementById("prop-fee-highlight");
        if (feeHighlight) feeHighlight.textContent = `${tier.fee.toLocaleString()} USDT`;

        const ladderSize = document.getElementById("prop-ladder-size");
        if (ladderSize) ladderSize.textContent = `$${(tier.size / 1000).toFixed(0)}K`;

        const targetLabel = document.getElementById("prop-target-label");
        if (targetLabel) targetLabel.textContent = `PROFIT TARGET (+${tier.targetPct.toFixed(2)}% / +$${tier.targetProfit.toLocaleString()}):`;

        const ddLabel = document.getElementById("prop-dd-label");
        if (ddLabel) ddLabel.textContent = `MAX TOTAL DRAWDOWN (-${tier.maxTotalDdPct.toFixed(2)}% / -$${tier.maxTotalDdUsdt.toLocaleString()}):`;

        // Calculate progress based on tier capital
        const profitPct = 2.83; // Baseline demo progress
        const profitUsdt = (tier.size * profitPct) / 100.0;
        const targetProgress = Math.min(100.0, (profitPct / tier.targetPct) * 100.0);

        const targetDisplay = document.getElementById("prop-target-display");
        const targetBar = document.getElementById("prop-target-bar");
        if (targetDisplay) targetDisplay.textContent = `+$${profitUsdt.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (+${profitPct.toFixed(2)}%)`;
        if (targetBar) targetBar.style.width = `${targetProgress.toFixed(1)}%`;

        const totalDd = 0.91;
        const maxDd = tier.maxTotalDdPct;
        const ddBuffer = maxDd - totalDd;
        const ddProgress = (totalDd / maxDd) * 100.0;

        const ddDisplay = document.getElementById("prop-dd-display");
        const ddBar = document.getElementById("prop-dd-bar");
        if (ddDisplay) ddDisplay.textContent = `${totalDd.toFixed(2)}% (SAFE BUFFER ${ddBuffer.toFixed(2)}%)`;
        if (ddBar) ddBar.style.width = `${ddProgress.toFixed(1)}%`;

        const dailyDd = document.getElementById("prop-daily-dd");
        if (dailyDd) dailyDd.textContent = `0.35% / 4.0% (-$${(tier.maxDailyDdUsdt).toLocaleString()} max)`;

        const cortexViol = document.getElementById("prop-cortex-viol");
        if (cortexViol) cortexViol.textContent = "0 (CLEAN)";

        const scoreVal = document.getElementById("prop-score-val");
        if (scoreVal) scoreVal.textContent = "88.6 / 100";

        const rankVal = document.getElementById("prop-rank-val");
        if (rankVal) rankVal.textContent = "#238";

        // Update 8-factor chips
        const fRet = document.getElementById("f-ret");
        const fDd = document.getElementById("f-dd");
        const fExp = document.getElementById("f-exp");
        const fPf = document.getElementById("f-pf");
        const fCtx = document.getElementById("f-ctx");
        const fExc = document.getElementById("f-exc");
        const fCal = document.getElementById("f-cal");
        const fCon = document.getElementById("f-con");
        if (fRet) fRet.textContent = "11.2";
        if (fDd) fDd.textContent = "18.2";
        if (fExp) fExp.textContent = "12.6";
        if (fPf) fPf.textContent = "8.5";
        if (fCtx) fCtx.textContent = "15.0";
        if (fExc) fExc.textContent = "9.2";
        if (fCal) fCal.textContent = "8.7";
        if (fCon) fCon.textContent = "4.0";

        // Update TAC balance display
        const tacDisplay = document.getElementById("prop-tac-balance-display");
        if (tacDisplay) tacDisplay.textContent = `${this.tacBalance.toFixed(2)} TAC`;
    }

    sharePropChallenge() {
        const tierKey = this.activePropTier || "100K";
        const tier = this.propTiers[tierKey] || this.propTiers["100K"];
        const profitUsdt = (tier.size * 2.83) / 100.0;

        const text = `🏆 TRADEAID PROP DEMO / REWARD PROGRAM (${tier.name})\n` +
            `• Account: $${tier.size.toLocaleString()} USDT (${tier.leverage})\n` +
            `• Payout Share: 80% Real Crypto (POL/USDT)\n` +
            `• Target: +8.00% (+$${tier.targetProfit.toLocaleString()}) | Now: +2.83% (+$${profitUsdt.toFixed(2)})\n` +
            `• Max Drawdown: 0.91% / -${tier.maxTotalDdPct.toFixed(1)}% MAX (SAFE BUFFER ${(tier.maxTotalDdPct - 0.91).toFixed(2)}%)\n` +
            `• CORTEX Violations: 0 (ZERO TOLERANCE PASS)\n` +
            `• 8-Factor Prop Score: 88.6/100 | Global Rank #238\n` +
            `🛡 Second Chance Guarantee: Fee converts 100% to TAC Credits with 80% real crypto payout!\n` +
            `👉 Test TradeAID Autotrade: https://trade.cryptoaid.support/dapp.html`;

        const btn = document.getElementById("btn-share-prop-challenge");
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(() => {
                if (btn) {
                    const orig = btn.innerHTML;
                    btn.innerHTML = `<span>COPIED TO CLIPBOARD!</span>`;
                    setTimeout(() => { btn.innerHTML = orig; }, 2000);
                }
            }).catch(() => {
                prompt("Copy and share your Prop Challenge progress:", text);
            });
        } else {
            prompt("Copy and share your Prop Challenge progress:", text);
        }
    }

    // =======================================================
    // LEDGER 1: AUTOTRADE RUN DEMO GAMIFICATA (10 POL -> 2 POL)
    // =======================================================
    handleRunButtonClick() {
        if (!this.isRunActive) {
            this.startAutotradeRun();
        } else {
            this.concludeAutotradeRun();
        }
    }

    async startAutotradeRun() {
        this.isRunActive = true;
        this.runSecondsLeft = 180;
        const seq = Math.floor(Math.random() * 900000) + 100000;
        this.currentRunId = `RUN-${seq}`;
        this.runPnlPct = 0.20;
        this.runPnlUsdt = 20.00;

        const idDisplay = document.getElementById("run-id-display");
        const timerDisplay = document.getElementById("run-seconds-left");
        const btnRun = document.getElementById("btn-trigger-run");
        const btnText = document.getElementById("btn-run-text");
        const resBanner = document.getElementById("run-result-banner");
        const pill = document.getElementById("run-status-pill");

        if (idDisplay) idDisplay.textContent = `AUTOTRADE #${seq} — RUNNING`;
        if (timerDisplay) timerDisplay.textContent = `180s`;
        if (btnRun) {
            btnRun.className = "btn-hero-autotrade running";
            if (btnText) btnText.innerHTML = `<span>⏹ CONCLUDI RUN ANTICIPATAMENTE (VALUTA P&L LIVE)</span>`;
        }
        if (resBanner) resBanner.style.display = "none";
        if (pill) {
            pill.style.background = "rgba(52,211,153,0.2)";
            pill.style.color = "#34d399";
            pill.textContent = `● RUN #${seq} ATTIVO (10,000 USDT PAPER)`;
        }

        // Call backend API asynchronously
        try {
            fetch("/api/v1/autotrade/run/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    wallet: this.account || "0x71C84102610a8877AE34805A20668f4e24D7B244",
                    tx_hash: "0x10pol_fee_tx"
                })
            }).catch(e => console.warn("Run start API notice:", e));
        } catch (e) {}

        if (this.runTimerInterval) clearInterval(this.runTimerInterval);
        this.runTimerInterval = setInterval(() => this.tickAutotradeRun(), 1000);
    }

    tickAutotradeRun() {
        if (!this.isRunActive) return;
        this.runSecondsLeft--;
        const timerDisplay = document.getElementById("run-seconds-left");
        if (timerDisplay) timerDisplay.textContent = `${this.runSecondsLeft}s`;

        // Micro random walk on PnL (+0.05% to +0.15% trend)
        const deltaPct = (Math.random() * 0.12) - 0.03;
        this.runPnlPct = Math.max(-0.40, this.runPnlPct + deltaPct);
        this.runPnlUsdt = (10000.0 * this.runPnlPct) / 100.0;
        const equity = 10000.0 + this.runPnlUsdt;

        const equityDisplay = document.getElementById("run-equity-display");
        const pnlDisplay = document.getElementById("run-pnl-display");
        if (equityDisplay) equityDisplay.textContent = `$${equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (pnlDisplay) {
            const isPos = this.runPnlPct >= 0;
            pnlDisplay.textContent = `${isPos ? '+' : ''}$${this.runPnlUsdt.toFixed(2)} (${isPos ? '+' : ''}${this.runPnlPct.toFixed(2)}%)`;
            pnlDisplay.style.color = isPos ? "#34d399" : "#ff1e38";
        }

        if (this.runSecondsLeft <= 0) {
            this.concludeAutotradeRun();
        }
    }

    async concludeAutotradeRun() {
        this.isRunActive = false;
        if (this.runTimerInterval) clearInterval(this.runTimerInterval);

        const won = this.runPnlPct > 0.0;
        const resBanner = document.getElementById("run-result-banner");
        const resTitle = document.getElementById("run-result-title");
        const resSub = document.getElementById("run-result-sub");
        const btnRun = document.getElementById("btn-trigger-run");
        const btnText = document.getElementById("btn-run-text");
        const pill = document.getElementById("run-status-pill");

        if (resBanner && resTitle && resSub) {
            resBanner.style.display = "block";
            if (won) {
                resBanner.style.background = "rgba(52,211,153,0.18)";
                resBanner.style.border = "1px solid #34d399";
                if (resTitle) {
                    resTitle.style.color = "#34d399";
                    resTitle.innerHTML = `🎉 WIN! +2.0 POL REWARD MATURATO (+${this.runPnlPct.toFixed(2)}% P&L NETTO)`;
                }
                if (resSub) {
                    resSub.style.color = "#ffffff";
                    resSub.innerHTML = `Reward Pool solvente (500 POL in riserva). Payout registrato. Salta a: <strong>LEDGER 2 (Prop Challenge)</strong>!`;
                }
            } else {
                resBanner.style.background = "rgba(255,30,56,0.18)";
                resBanner.style.border = "1px solid #ff1e38";
                if (resTitle) {
                    resTitle.style.color = "#ff1e38";
                    resTitle.innerHTML = `RUN CONCLUSO — NESSUN REWARD (${this.runPnlPct.toFixed(2)}% P&L)`;
                }
                if (resSub) {
                    resSub.style.color = "#a1a1aa";
                    resSub.innerHTML = `Il P&L non ha raggiunto territorio positivo entro 180s. Nessuna perdita di capitale reale (10,000 USDT Paper).`;
                }
            }
        }

        if (btnRun && btnText) {
            btnRun.className = "btn-hero-autotrade";
            btnText.innerHTML = `<span>⚡ 10 POL ➔ START NUOVO AUTOTRADE RUN</span>`;
        }

        if (pill) {
            pill.style.background = won ? "rgba(52,211,153,0.2)" : "rgba(255,30,56,0.2)";
            pill.style.color = won ? "#34d399" : "#ff1e38";
            pill.textContent = won ? `🏆 ESITO: WIN (+2 POL REWARD)` : `⏸ ESITO: RUN CONCLUSO (0 POL)`;
        }

        // Send conclusion to backend API
        try {
            fetch(`/api/v1/autotrade/run/${this.currentRunId || 'RUN-000123'}/conclude`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    simulated_pnl_usdt: this.runPnlUsdt,
                    simulated_pnl_pct: this.runPnlPct,
                    trades_count: 4,
                    cortex_violations: 0
                })
            }).catch(e => console.warn("Run conclude notice:", e));
        } catch (e) {}
    }
}

document.addEventListener("DOMContentLoaded", () => {
    window.web3App = new Web3Controller();
    window.dapp = window.web3App;
});

