/**
 * CryptoAID Trade AI — PWA Cockpit Frontend Engine
 */

const API_BASE = "/api/v1";

// Application State
let currentTab = "home";
let systemState = null;
let portfolioData = null;
let scannerData = null;
let autotradeActive = true;

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  registerServiceWorker();
  loadAllData();

  // Background refresh every 15 seconds
  setInterval(() => {
    refreshActiveView();
  }, 15000);
});

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch((err) => {
      console.log("SW registration notice:", err);
    });
  }
}

function initNavigation() {
  const tabs = document.querySelectorAll(".nav-tab, .bottom-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      if (target) switchTab(target);
    });
  });
}

function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll(".nav-tab, .bottom-tab").forEach((t) => {
    t.classList.toggle("active", t.getAttribute("data-tab") === tabId);
  });
  document.querySelectorAll(".view-section").forEach((sec) => {
    sec.classList.toggle("active", sec.id === `view-${tabId}`);
  });
  refreshActiveView();
}

async function loadAllData() {
  await Promise.all([
    fetchSystemStatus(),
    fetchMarkets(),
    fetchPortfolio(),
    fetchPositions(),
    fetchPerformance(),
    fetchStrategies(),
  ]);
  renderHome();
}

async function refreshActiveView() {
  if (currentTab === "home") {
    await Promise.all([fetchSystemStatus(), fetchPortfolio(), fetchPositions()]);
    renderHome();
  } else if (currentTab === "markets") {
    await fetchMarkets();
  } else if (currentTab === "scanner") {
    await runScanner();
  } else if (currentTab === "signals") {
    await fetchSignals();
  } else if (currentTab === "positions") {
    await fetchPositions();
  } else if (currentTab === "portfolio") {
    await Promise.all([fetchPortfolio(), fetchTrades()]);
  } else if (currentTab === "strategies") {
    await fetchStrategies();
  } else if (currentTab === "performance") {
    await fetchPerformance();
  } else if (currentTab === "risk") {
    await fetchRiskStatus();
  } else if (currentTab === "status") {
    await fetchSystemStatus();
  }
}

async function fetchSystemStatus() {
  try {
    const res = await fetch(`${API_BASE}/status`);
    if (res.ok) {
      systemState = await res.json();
      updateSystemHeader();
    }
  } catch (err) {
    console.error("Status fetch error:", err);
  }
}

function updateSystemHeader() {
  if (!systemState) return;
  const ksIndicator = document.getElementById("header-ks-status");
  if (ksIndicator) {
    if (systemState.kill_switch) {
      ksIndicator.textContent = "🚨 KILL SWITCH ACTIVE";
      ksIndicator.className = "val-red";
    } else {
      ksIndicator.textContent = systemState.live_trading_enabled ? "LIVE ONLINE" : "ONLINE (PAPER)";
      ksIndicator.className = "val-green";
    }
  }

  const modeBadge = document.getElementById("runtime-mode-badge");
  if (modeBadge) {
    modeBadge.textContent = systemState.live_trading_enabled ? "POLYGON DEX • LIVE" : "POLYGON DEX • PAPER";
    modeBadge.className = systemState.live_trading_enabled ? "mode-badge val-red" : "mode-badge";
  }
}

async function fetchMarkets() {
  try {
    const res = await fetch(`${API_BASE}/markets`);
    if (res.ok) {
      const markets = await res.json();
      renderMarketsTable(markets);
    }
  } catch (err) {
    console.error("Markets error:", err);
  }
}

function renderMarketsTable(markets) {
  const tbody = document.getElementById("markets-table-body");
  if (!tbody) return;
  tbody.innerHTML = markets.map((m) => {
    const pStr = m.price < 10 ? `$${m.price.toFixed(4)}` : `$${m.price.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
    const chgClass = m.change_24h_pct >= 0 ? "val-green" : "val-red";
    return `
      <tr>
        <td><b>${m.symbol}</b></td>
        <td>${pStr}</td>
        <td>${(m.spread || 0).toFixed(4)}</td>
        <td>$${(m.volume_24h || 0).toLocaleString()}</td>
        <td class="${chgClass}">${m.change_24h_pct >= 0 ? '+' : ''}${m.change_24h_pct.toFixed(2)}%</td>
      </tr>
    `;
  }).join("");
}

async function runScanner() {
  const container = document.getElementById("scanner-results-container");
  if (container) {
    container.innerHTML = '<div style="color: var(--cyan-neon); text-align: center; padding: 20px;">Scanning Polygon liquidity & Multi-Agent signals...</div>';
  }
  try {
    const res = await fetch(`${API_BASE}/scan`);
    if (res.ok) {
      scannerData = await res.json();
      renderScannerResults(scannerData);
    }
  } catch (err) {
    console.error("Scanner error:", err);
  }
}

function renderScannerResults(results) {
  const container = document.getElementById("scanner-results-container");
  if (!container) return;
  container.innerHTML = results.map((item) => {
    const pStr = item.price < 10 ? `$${item.price.toFixed(4)}` : `$${item.price.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
    const sigClass = item.ai_signal === "BUY" ? "val-green" : (item.ai_signal === "SELL" ? "val-red" : "text-muted");
    const gateBadge = item.cryptoaid_risk.passed ? '<span class="val-green">✅ RISK PASS</span>' : '<span class="val-red">❌ REJECTED</span>';
    return `
      <div class="metric-card" style="margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <div style="font-size: 16px; font-weight: 700;">${item.symbol} <span style="font-size: 13px; font-weight: 400; color: var(--text-secondary);">${pStr}</span></div>
          <div>${gateBadge}</div>
        </div>
        <div style="font-size: 13px; margin-bottom: 6px;">
          Consensus: <b class="${sigClass}">${item.ai_signal}</b> (${(item.ai_confidence * 100).toFixed(0)}% confidence)
        </div>
        <div style="font-size: 12px; color: var(--text-muted);">
          SL: $${item.recommended_stop_loss || 'Dynamic'} | TP: $${item.recommended_take_profit || 'Dynamic'} | Volatility: ${(item.volatility_24h || 0).toFixed(2)}
        </div>
      </div>
    `;
  }).join("");
}

async function fetchSignals() {
  const container = document.getElementById("signals-container");
  try {
    const res = await fetch(`${API_BASE}/signals`);
    if (res.ok) {
      const signals = await res.json();
      if (!signals || signals.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 30px;">Zero signals currently pass positive net edge & risk criteria. Capital safely preserved in USDT.</div>';
        return;
      }
      container.innerHTML = signals.map((s) => `
        <div class="metric-card" style="margin-bottom: 12px; border-left: 4px solid var(--emerald-green);">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 16px; font-weight: 700;">${s.symbol} — <span class="val-green">${s.ai_signal}</span></div>
            <div class="val-cyan" style="font-weight: 700;">${(s.ai_confidence * 100).toFixed(0)}% Confidence</div>
          </div>
          <div style="font-size: 13px; margin-top: 8px; color: var(--text-secondary);">
            Entry: $${s.price.toFixed(2)} | Target: $${s.recommended_take_profit || 'Dynamic'} | Stop: $${s.recommended_stop_loss || '5% Ceiling'}
          </div>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Signals error:", err);
  }
}

async function fetchPositions() {
  try {
    const res = await fetch(`${API_BASE}/positions`);
    if (res.ok) {
      const positions = await res.json();
      renderPositionsTable(positions);
      const openCount = document.getElementById("home-open-positions");
      if (openCount) openCount.textContent = `${positions.length} / 4`;
    }
  } catch (err) {
    console.error("Positions error:", err);
  }
}

function renderPositionsTable(positions) {
  const tbody = document.getElementById("guardian-positions-body");
  if (!tbody) return;
  if (!positions || positions.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">No active positions. Capital 100% in USDT.</td></tr>';
    return;
  }
  tbody.innerHTML = positions.map((p) => {
    const pnlClass = p.unrealized_pnl >= 0 ? "val-green" : "val-red";
    return `
      <tr>
        <td><b>${p.asset}</b></td>
        <td>${p.side}</td>
        <td>${p.size}</td>
        <td>$${p.entry_price.toFixed(4)}</td>
        <td>$${p.current_price.toFixed(4)}</td>
        <td class="${pnlClass}"><b>$${p.unrealized_pnl.toFixed(2)} (${p.unrealized_pnl_pct.toFixed(2)}%)</b></td>
        <td>SL: $${p.sl || 0} | TP: $${p.tp || 0}</td>
      </tr>
    `;
  }).join("");
}

async function fetchPortfolio() {
  try {
    const res = await fetch(`${API_BASE}/portfolio`);
    if (res.ok) {
      portfolioData = await res.json();
      const acc = portfolioData.account || {};
      const eq = document.getElementById("home-portfolio-val");
      if (eq) eq.textContent = `$${(acc.total_equity || 1000).toLocaleString(undefined, {minimumFractionDigits: 2})}`;

      const dPnl = document.getElementById("home-daily-pnl");
      if (dPnl) {
        const pVal = acc.daily_realized_pnl || 0.0;
        dPnl.textContent = `${pVal >= 0 ? '+' : ''}$${pVal.toFixed(2)}`;
        dPnl.className = pVal >= 0 ? "metric-value val-green" : "metric-value val-red";
      }

      const cVal = document.getElementById("port-cash-val");
      if (cVal) cVal.textContent = `$${(acc.cash_balance || 1000).toLocaleString(undefined, {minimumFractionDigits: 2})}`;

      const mVal = document.getElementById("port-margin-val");
      if (mVal) mVal.textContent = `$${(acc.allocated_margin || 0).toFixed(2)}`;

      const rVal = document.getElementById("port-realized-val");
      if (rVal) rVal.textContent = `$${(acc.daily_realized_pnl || 0).toFixed(2)}`;

      const ddVal = document.getElementById("port-dd-val");
      if (ddVal) ddVal.textContent = `${(acc.current_drawdown_pct || 0).toFixed(1)}%`;
    }
  } catch (err) {
    console.error("Portfolio error:", err);
  }
}

async function fetchTrades() {
  try {
    const res = await fetch(`${API_BASE}/trades?limit=10`);
    if (res.ok) {
      const trades = await res.json();
      const tbody = document.getElementById("trades-table-body");
      if (!tbody) return;
      if (!trades || trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">No trade fills recorded yet.</td></tr>';
        return;
      }
      tbody.innerHTML = trades.map((t) => `
        <tr>
          <td>${t.executed_at.substring(0, 19)}</td>
          <td><b>${t.asset}</b></td>
          <td>${t.side}</td>
          <td>$${t.price.toFixed(4)}</td>
          <td>${t.size}</td>
          <td>$${t.fees.toFixed(4)}</td>
        </tr>
      `).join("");
    }
  } catch (err) {
    console.error("Trades error:", err);
  }
}

async function fetchStrategies() {
  try {
    const res = await fetch(`${API_BASE}/strategies`);
    if (res.ok) {
      const strategies = await res.json();
      const container = document.getElementById("strategies-list-container");
      if (!container) return;
      container.innerHTML = strategies.map((s) => `
        <div class="metric-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 15px; font-weight: 700;">${s.name}</div>
            <div class="val-cyan" style="font-size: 12px; font-weight: 700;">Weight: ${s.weight}x</div>
          </div>
          <div style="font-size: 12px; color: var(--text-secondary);">${s.description}</div>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Strategies error:", err);
  }
}

async function fetchPerformance() {
  try {
    const res = await fetch(`${API_BASE}/performance`);
    if (res.ok) {
      const perf = await res.json();
      const wr = document.getElementById("perf-winrate");
      if (wr) wr.textContent = `${perf.win_rate_pct.toFixed(1)}%`;

      const wl = document.getElementById("perf-wl");
      if (wl) wl.textContent = `${perf.winning_trades} Wins / ${perf.losing_trades} Losses`;

      const pf = document.getElementById("perf-profit-factor");
      if (pf) pf.textContent = perf.profit_factor.toFixed(2);

      const sh = document.getElementById("perf-sharpe");
      if (sh) sh.textContent = perf.sharpe_ratio.toFixed(2);

      const dd = document.getElementById("perf-maxdd");
      if (dd) dd.textContent = `${perf.max_drawdown_pct.toFixed(1)}%`;
    }
  } catch (err) {
    console.error("Performance error:", err);
  }
}

async function fetchRiskStatus() {
  try {
    const res = await fetch(`${API_BASE}/risk`);
    if (res.ok) {
      const data = await res.json();
      console.log("Risk parameters verified:", data.rules);
    }
  } catch (err) {
    console.error("Risk error:", err);
  }
}

function renderHome() {
  // Triggers updates on cards
}

async function toggleAutotrade() {
  autotradeActive = !autotradeActive;
  try {
    await fetch(`${API_BASE}/autotrade?enabled=${autotradeActive}`, { method: "POST" });
  } catch (e) {
    console.error(e);
  }
  const btn = document.getElementById("btn-toggle-autotrade");
  if (btn) {
    btn.textContent = autotradeActive ? "AUTOTRADE: ON" : "AUTOTRADE: PAUSED";
    btn.className = autotradeActive ? "btn-cta" : "btn-cta val-red";
  }
}

async function triggerEmergencyKillSwitch() {
  if (!confirm("CONFIRM: Are you sure you want to trigger the EMERGENCY KILL SWITCH? All open positions will be immediately liquidated back to USDT.")) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/kill-switch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "TRIGGER", reason: "Operator PWA Emergency Action" }),
    });
    const data = await res.json();
    alert(`KILL SWITCH TRIGGERED! Closed ${data.closed_positions_count || 0} active positions.`);
    await refreshActiveView();
  } catch (err) {
    alert(`Kill switch error: ${err}`);
  }
}

async function resetEmergencyKillSwitch() {
  try {
    await fetch(`${API_BASE}/kill-switch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "RESET", reason: "Operator PWA Reset" }),
    });
    alert("Kill switch disarmed. System ready.");
    await refreshActiveView();
  } catch (err) {
    alert(`Reset error: ${err}`);
  }
}
