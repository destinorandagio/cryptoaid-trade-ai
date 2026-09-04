/**
 * TradeAID Web3 dApp — Complete Multi-Language Internationalization (i18n)
 * Supported Languages:
 *   en (English - Default)
 *   it (Italiano)
 *   zh (中文 - 简体)
 *   es (Español)
 *   de (Deutsch)
 *   fr (Français)
 *   ja (日本語)
 *   pt (Português)
 *   ru (Русский)
 *   ar (العربية)
 */

const TRANSLATIONS = {
    en: {
        page_title: "TradeAID Web3 dApp — Autonomous Cockpit",
        nav_back_title: "Back to Landing Page",
        connect_wallet: "⚡ Connect Wallet",
        disconnect: "Disconnect",
        chain_warning: "⚠️ Wrong Network: Detected network different from Polygon POS (137).",
        btn_switch_polygon: "Switch to Polygon",
        
        // Institutional
        powered_by: "Powered by",
        audited_by: "Audited & Certified by",
        engineered_by: "Engineered by",
        native_on: "Native on",
        
        // Paywall Modal
        paywall_tag: "ON-CHAIN SIGNATURE QUOTE",
        dao_title: "TRADEAID DAO QUOTA ACTIVATION (1st ACCESS)",
        dao_desc: "Includes permanent DAO Founders membership and full unlock of TradeAID autonomous cockpit.",
        session_title: "SESSION ACCESS PASS (USDT ON POLYGON)",
        session_desc: "Session fee for autonomous execution and 24/7 Position Guardian protection.",
        quote_req_amount: "REQUIRED AMOUNT:",
        quote_recipient: "RECIPIENT (TREASURY):",
        quote_network: "BLOCKCHAIN NETWORK:",
        quote_your_wallet: "YOUR WALLET:",
        wallet_not_connected: "Not Connected",
        status_waiting_sign: "Awaiting interactive signature...",
        btn_sign_execute: "✍️ SIGN & EXECUTE ON POLYGON (USDT)",
        zero_custody_notice: "🔒 Non-Custodial: Direct ERC-20 transaction via your wallet.",
        
        // Cockpit Status
        guardian_status: "POSITION GUARDIAN: <strong>ACTIVE 24/7</strong>",
        guardian_ceiling: "CEILING: -5.0%",
        metric_cash: "LIQUID BALANCE",
        metric_equity: "TOTAL EQUITY",
        metric_net_edge: "MIN NET EDGE",
        metric_exposure: "ACTIVE EXPOSURE",
        
        // Tabs
        tab_scanner: "📡 Scanner",
        tab_positions: "📈 Positions (0)",
        tab_strategies: "🧠 Strategies",
        tab_security: "🚨 Security",
        
        // Tab 1: Scanner
        scanner_title: "POLYGON MARKETS MONITORED",
        live_tick: "LIVE TICK: 10s",
        trending: "TRENDING",
        ranging: "RANGING",
        signal_buy_pol: "AI SIGNAL: BUY (Conf. 85%)",
        signal_no_trade: "AI SIGNAL: NO_TRADE",
        signal_buy_wbtc: "AI SIGNAL: BUY (Conf. 78%)",
        est_net_edge: "Est. Net Edge:",
        dynamic_stop: "Dynamic Stop:",
        awaiting_range: "Awaiting range breakout",
        be_lock: "Break-Even Lock:",
        gating_filter: "(Gating Filter)",
        
        // Tab 2: Positions
        no_pos_title: "No Positions Exposed to Risk",
        no_pos_desc: "Position Guardian is waiting for Net Edge threshold (+0.40%). 100% of funds preserved in USDT.",
        
        // Tab 3: Strategies
        strat_1_title: "Scalping Strategy (1m/3m/5m)",
        strat_1_desc: "Max spread filter 0.15% | Micro-momentum",
        strat_2_title: "Trend Following (EMA 12/26 + MACD)",
        strat_2_desc: "Macro trend breakout identification",
        strat_3_title: "Breakout & Donchian Channels",
        strat_3_desc: "High expansion volatility",
        strat_4_title: "Mean Reversion (Z-Score + RSI Divergence)",
        strat_4_desc: "Quick reversal on overbought/oversold",
        strat_weight: "WEIGHT:",
        
        // Tab 4: Security
        kill_switch_title: "EMERGENCY KILL SWITCH",
        kill_switch_desc: "In case of emergency or market anomaly, immediately closes all positions and liquidates 100% to USDT in your wallet.",
        kill_switch_btn: "🛑 ACTIVATE INSTANT KILL SWITCH",
        cortex_title: "AUDITED & CERTIFIED BY CORTEX",
        cortex_desc: "Continuous heuristic security tests on bor RPC, anti-honeypot gate, and formal smart contract verification.",
        cortex_pill_1: "✓ FORMAL VERIFICATION: PASSED",
        cortex_pill_2: "✓ FAIL-CLOSED PROTOCOL: ACTIVE",
        neuralog_title: "ENGINEERED BY NEURALOG · POWERED BY BLOCKCHAIN+",
        neuralog_desc: "Quant Engine powered by proprietary Neuralog statistical models, Blockchain+ decentralized routing, and native Polygon (137) finality.",
        
        // Footer
        ticker_engine: "TRADEAID · Powered by Blockchain+ · Audited by Cortex · Engineered by Neuralog · Polygon 137",
        
        // Alerts
        alert_no_wallet: "No Web3 Wallet detected. Please install MetaMask, Rabby, or open in Trust Wallet / Phantom mobile browser.",
        alert_connect_rejected: "Connection rejected by user.",
        alert_tx_submitted: "Transaction submitted! Tx Hash: ",
        alert_tx_confirmed: "Payment confirmed on-chain! Cockpit unlocked.",
        alert_tx_failed: "Transaction failed or rejected.",
        alert_kill_confirm: "Caution: Do you want to trigger the Emergency Kill Switch and liquidate all positions to USDT?",
        alert_kill_done: "Kill Switch ACTIVATED. All positions liquidated to USDT."
    },
    it: {
        page_title: "TradeAID Web3 dApp — Cockpit Autonomo",
        nav_back_title: "Torna alla Landing Page",
        connect_wallet: "⚡ Connetti Wallet",
        disconnect: "Disconnetti",
        chain_warning: "⚠️ Rete Errata: Rilevata rete diversa da Polygon POS (137).",
        btn_switch_polygon: "Passa a Polygon",
        
        powered_by: "Powered by",
        audited_by: "Audited & Certified by",
        engineered_by: "Engineered by",
        native_on: "Native on",
        
        paywall_tag: "PREVENTIVO DI FIRMA ON-CHAIN",
        dao_title: "ATTIVAZIONE QUOTA DAO TRADEAID (1° ACCESSO)",
        dao_desc: "Include membership permanente DAO Founders e sblocco totale del Cockpit autonomo TradeAID.",
        session_title: "SESSION ACCESS PASS (USDT SU POLYGON)",
        session_desc: "Quota di sessione per l'esecuzione autonoma e il presidio Position Guardian 24/7.",
        quote_req_amount: "IMPORTO RICHIESTO:",
        quote_recipient: "DESTINATARIO (TREASURY):",
        quote_network: "RETE BLOCKCHAIN:",
        quote_your_wallet: "IL TUO WALLET:",
        wallet_not_connected: "Non Connesso",
        status_waiting_sign: "In attesa di firma interattiva...",
        btn_sign_execute: "✍️ FIRMA ED ESEGUI SU POLYGON (USDT)",
        zero_custody_notice: "🔒 Non-Custodial: Transazione diretta ERC-20 tramite il tuo wallet.",
        
        guardian_status: "POSITION GUARDIAN: <strong>ATTIVO 24/7</strong>",
        guardian_ceiling: "CEILING: -5.0%",
        metric_cash: "SALDO LIQUIDO",
        metric_equity: "EQUITY TOTALE",
        metric_net_edge: "NET EDGE MINIMO",
        metric_exposure: "ESPOSIZIONE ATTIVA",
        
        tab_scanner: "📡 Scanner",
        tab_positions: "📈 Posizioni (0)",
        tab_strategies: "🧠 Strategie",
        tab_security: "🚨 Sicurezza",
        
        scanner_title: "MERCATI POLYGON SOTTO CONTROLLO",
        live_tick: "LIVE TICK: 10s",
        trending: "TRENDING",
        ranging: "RANGING",
        signal_buy_pol: "SEGNALE AI: BUY (Conf. 85%)",
        signal_no_trade: "SEGNALE AI: NO_TRADE",
        signal_buy_wbtc: "SEGNALE AI: BUY (Conf. 78%)",
        est_net_edge: "Net Edge Stimato:",
        dynamic_stop: "Stop Dinamico:",
        awaiting_range: "Attesa rottura range",
        be_lock: "Break-Even Lock:",
        gating_filter: "(Filtro Gating)",
        
        no_pos_title: "Nessuna Posizione Esposta al Rischio",
        no_pos_desc: "Il Position Guardian è in attesa del superamento del threshold di Net Edge (+0.40%). 100% dei fondi preservati in USDT.",
        
        strat_1_title: "Scalping Strategy (1m/3m/5m)",
        strat_1_desc: "Filtro spread massimo 0.15% | Micro-momentum",
        strat_2_title: "Trend Following (EMA 12/26 + MACD)",
        strat_2_desc: "Identificazione breakout di trend macro",
        strat_3_title: "Breakout & Donchian Channels",
        strat_3_desc: "Volatilità ad alta espansione",
        strat_4_title: "Mean Reversion (Z-Score + RSI Divergence)",
        strat_4_desc: "Reversione rapida su ipercomprato/ipervenduto",
        strat_weight: "PESO:",
        
        kill_switch_title: "KILL SWITCH DI EMERGENZA",
        kill_switch_desc: "In caso di emergenza o anomalia di mercato, chiude all'istante tutte le posizioni e le liquida al 100% in USDT sul tuo wallet.",
        kill_switch_btn: "🛑 ATTIVA KILL SWITCH ISTANTANEO",
        cortex_title: "AUDITED & CERTIFIED BY CORTEX",
        cortex_desc: "Test euristici di sicurezza eseguiti su bor RPC, anti-honeypot gate e verifica formale smart contract.",
        cortex_pill_1: "✓ FORMAL VERIFICATION: PASSED",
        cortex_pill_2: "✓ FAIL-CLOSED PROTOCOL: ACTIVE",
        neuralog_title: "ENGINEERED BY NEURALOG · POWERED BY BLOCKCHAIN+",
        neuralog_desc: "Quant Engine alimentato da modelli statistici proprietari Neuralog, routing decentralizzato Blockchain+ e finalità nativa su Polygon (137).",
        
        ticker_engine: "TRADEAID · Powered by Blockchain+ · Audited by Cortex · Engineered by Neuralog · Polygon 137",
        
        alert_no_wallet: "Nessun Web3 Wallet rilevato. Installa MetaMask, Rabby o apri la dApp nel browser del tuo wallet mobile.",
        alert_connect_rejected: "Connessione rifiutata dall'utente.",
        alert_tx_submitted: "Transazione inviata! Tx Hash: ",
        alert_tx_confirmed: "Pagamento confermato on-chain! Cockpit sbloccato.",
        alert_tx_failed: "Transazione fallita o rifiutata.",
        alert_kill_confirm: "Attenzione: Vuoi attivare il Kill Switch di emergenza e liquidare tutte le posizioni in USDT?",
        alert_kill_done: "Kill Switch ATTIVATO. Tutte le posizioni liquidate in USDT."
    },
    zh: {
        page_title: "TradeAID Web3 去中心化应用 — 自动交易驾驶舱",
        nav_back_title: "返回主页",
        connect_wallet: "⚡ 连接钱包",
        disconnect: "断开连接",
        chain_warning: "⚠️ 网络错误：检测到非 Polygon POS (137) 网络。",
        btn_switch_polygon: "切换至 Polygon",
        
        powered_by: "技术支持",
        audited_by: "审计与认证",
        engineered_by: "工程研发",
        native_on: "原生运行于",
        
        paywall_tag: "链上签名核准单",
        dao_title: "激活 TRADEAID DAO 配额 (首次访问)",
        dao_desc: "包含永久 DAO 创始人席位并完全解锁 TradeAID 自动算法交易驾驶舱。",
        session_title: "会话访问通行证 (USDT ON POLYGON)",
        session_desc: "自主执行和全天候持仓守护者（Position Guardian）保护的会话费用。",
        quote_req_amount: "所需金额：",
        quote_recipient: "接收地址（国库）：",
        quote_network: "区块链网络：",
        quote_your_wallet: "您的钱包：",
        wallet_not_connected: "未连接",
        status_waiting_sign: "等待交互式签名...",
        btn_sign_execute: "✍️ 在 POLYGON 上签名并执行 (USDT)",
        zero_custody_notice: "🔒 非托管模式：通过您的私人钱包直接进行 ERC-20 转账。",
        
        guardian_status: "持仓守护者：<strong>全天候 24/7 运行中</strong>",
        guardian_ceiling: "最大止损硬顶: -5.0%",
        metric_cash: "可用流动余额",
        metric_equity: "总资产净值",
        metric_net_edge: "最小净数学优势",
        metric_exposure: "当前活动敞口",
        
        tab_scanner: "📡 扫描仪",
        tab_positions: "📈 当前持仓 (0)",
        tab_strategies: "🧠 策略矩阵",
        tab_security: "🚨 安全与熔断",
        
        scanner_title: "POLYGON 监控市场行情",
        live_tick: "实时跳动: 10秒",
        trending: "趋势行情",
        ranging: "震荡盘整",
        signal_buy_pol: "AI 信号：买入 (置信度 85%)",
        signal_no_trade: "AI 信号：观望 (NO_TRADE)",
        signal_buy_wbtc: "AI 信号：买入 (置信度 78%)",
        est_net_edge: "预估净优势:",
        dynamic_stop: "动态止损位:",
        awaiting_range: "等待区间突破",
        be_lock: "保本锁定位:",
        gating_filter: "(门控过滤拦截)",
        
        no_pos_title: "当前无风险暴露持仓",
        no_pos_desc: "持仓守护者正在等待超过最小净优势阈值 (+0.40%)。100% 资金以 USDT 形式安全储存。",
        
        strat_1_title: "超短线高频剥头皮 (1分/3分/5分)",
        strat_1_desc: "最大点差过滤 0.15% | 微动量捕获",
        strat_2_title: "趋势跟踪引擎 (EMA 12/26 + MACD)",
        strat_2_desc: "宏观趋势多周期突破识别",
        strat_3_title: "唐奇安通道与突破策略",
        strat_3_desc: "高波动性扩张突破",
        strat_4_title: "均值回归系统 (Z-Score + RSI 背离)",
        strat_4_desc: "超买超卖极端行情极速反转",
        strat_weight: "权重比:",
        
        kill_switch_title: "紧急熔断断路器 (KILL SWITCH)",
        kill_switch_desc: "遇突发黑天鹅或市场异常时，立即平掉全部仓位并 100% 兑换为 USDT 归集至您的私人钱包。",
        kill_switch_btn: "🛑 立即触发紧急熔断断路器",
        cortex_title: "由 CORTEX 审计与形式化验证",
        cortex_desc: "对 bor RPC 节点、防貔貅蜜罐网关与智能合约进行持续启发式安全审查与形式化验证。",
        cortex_pill_1: "✓ 形式化验证：已通过",
        cortex_pill_2: "✓ 故障闭锁协议：运行中",
        neuralog_title: "NEURALOG 量化研发 · BLOCKCHAIN+ 驱动",
        neuralog_desc: "基于 Neuralog 专有微观结构模型、Blockchain+ 去中心化路由及 Polygon (137) 极速结算。",
        
        ticker_engine: "TRADEAID · Blockchain+ 驱动 · Cortex 审计 · Neuralog 研发 · Polygon 137 原生",
        
        alert_no_wallet: "未检测到 Web3 钱包。请安装 MetaMask、Rabby 或在手机钱包（Trust Wallet、Phantom）内置浏览器中打开。",
        alert_connect_rejected: "用户取消了钱包连接请求。",
        alert_tx_submitted: "交易已广播上链！交易哈希: ",
        alert_tx_confirmed: "链上支付确认成功！交易驾驶舱已解锁。",
        alert_tx_failed: "交易失败或已被用户拒绝。",
        alert_kill_confirm: "警告：您确定要触发紧急熔断开关并将全部持仓立即清算为 USDT 吗？",
        alert_kill_done: "紧急熔断已触发！全部持仓已 100% 清算为 USDT。"
    },
    es: {
        page_title: "TradeAID Web3 dApp — Cockpit Autónomo",
        nav_back_title: "Volver a la página principal",
        connect_wallet: "⚡ Conectar Billetera",
        disconnect: "Desconectar",
        chain_warning: "⚠️ Red Incorrecta: Se detectó una red diferente a Polygon POS (137).",
        btn_switch_polygon: "Cambiar a Polygon",
        
        powered_by: "Desarrollado por",
        audited_by: "Auditado y Certificado por",
        engineered_by: "Diseñado por",
        native_on: "Nativo en",
        
        paywall_tag: "COTIZACIÓN DE FIRMA ON-CHAIN",
        dao_title: "ACTIVACIÓN CUOTA DAO TRADEAID (1° ACCESO)",
        dao_desc: "Incluye membresía permanente de Fundadores DAO y desbloqueo total del cockpit autónomo TradeAID.",
        session_title: "PASE DE ACCESO DE SESIÓN (USDT EN POLYGON)",
        session_desc: "Tarifa de sesión para ejecución autónoma y protección Position Guardian 24/7.",
        quote_req_amount: "IMPORTE REQUERIDO:",
        quote_recipient: "DESTINATARIO (TESORERÍA):",
        quote_network: "RED BLOCKCHAIN:",
        quote_your_wallet: "TU BILLETERA:",
        wallet_not_connected: "No Conectada",
        status_waiting_sign: "Esperando firma interactiva...",
        btn_sign_execute: "✍️ FIRMAR Y EJECUTAR EN POLYGON (USDT)",
        zero_custody_notice: "🔒 No-Custodial: Transacción directa ERC-20 desde tu billetera.",
        
        guardian_status: "POSITION GUARDIAN: <strong>ACTIVO 24/7</strong>",
        guardian_ceiling: "LÍMITE MÁXIMO: -5.0%",
        metric_cash: "SALDO LÍQUIDO",
        metric_equity: "PATRIMONIO TOTAL",
        metric_net_edge: "VENTAJA NETA MÍNIMA",
        metric_exposure: "EXPOSICIÓN ACTIVA",
        
        tab_scanner: "📡 Escáner",
        tab_positions: "📈 Posiciones (0)",
        tab_strategies: "🧠 Estrategias",
        tab_security: "🚨 Seguridad",
        
        scanner_title: "MERCADOS POLYGON BAJO VIGILANCIA",
        live_tick: "TICK EN VIVO: 10s",
        trending: "TENDENCIA",
        ranging: "RANGO",
        signal_buy_pol: "SEÑAL IA: COMPRAR (Conf. 85%)",
        signal_no_trade: "SEÑAL IA: SIN OPERACIÓN",
        signal_buy_wbtc: "SEÑAL IA: COMPRAR (Conf. 78%)",
        est_net_edge: "Ventaja Neta Estimada:",
        dynamic_stop: "Stop Dinámico:",
        awaiting_range: "Esperando ruptura de rango",
        be_lock: "Bloqueo Break-Even:",
        gating_filter: "(Filtro de Control)",
        
        no_pos_title: "Sin Posiciones Expuestas al Riesgo",
        no_pos_desc: "Position Guardian espera que se supere el umbral de Ventaja Neta (+0.40%). 100% de fondos preservados en USDT.",
        
        strat_1_title: "Estrategia Scalping (1m/3m/5m)",
        strat_1_desc: "Filtro spread máx 0.15% | Micro-impulso",
        strat_2_title: "Seguimiento de Tendencia (EMA 12/26 + MACD)",
        strat_2_desc: "Identificación de rupturas de tendencia macro",
        strat_3_title: "Ruptura y Canales Donchian",
        strat_3_desc: "Alta volatilidad expansiva",
        strat_4_title: "Reversión a la Media (Z-Score + RSI)",
        strat_4_desc: "Reversión rápida en sobrecompra/sobreventa",
        strat_weight: "PESO:",
        
        kill_switch_title: "BOTÓN DE APAGADO DE EMERGENCIA",
        kill_switch_desc: "En caso de emergencia o anomalía, cierra inmediatamente todas las posiciones liquidando el 100% a USDT en tu billetera.",
        kill_switch_btn: "🛑 ACTIVAR INTERRUPTOR DE EMERGENCIA",
        cortex_title: "AUDITADO Y CERTIFICADO POR CORTEX",
        cortex_desc: "Pruebas heurísticas continuas en RPC bor, puerta anti-honeypot y verificación formal de contratos inteligentes.",
        cortex_pill_1: "✓ VERIFICACIÓN FORMAL: APROBADA",
        cortex_pill_2: "✓ PROTOCOLO FAIL-CLOSED: ACTIVO",
        neuralog_title: "DISEÑADO POR NEURALOG · POTENCIADO POR BLOCKCHAIN+",
        neuralog_desc: "Motor cuantitativo impulsado por modelos estadísticos Neuralog, enrutamiento Blockchain+ y finalidad Polygon (137).",
        
        ticker_engine: "TRADEAID · Desarrollado por Blockchain+ · Auditado por Cortex · Diseñado por Neuralog · Polygon 137",
        
        alert_no_wallet: "No se detectó billetera Web3. Instala MetaMask, Rabby o abre en navegador móvil (Trust Wallet, Phantom).",
        alert_connect_rejected: "Conexión rechazada por el usuario.",
        alert_tx_submitted: "¡Transacción enviada! Hash: ",
        alert_tx_confirmed: "¡Pago confirmado on-chain! Cockpit desbloqueado.",
        alert_tx_failed: "Transacción fallida o rechazada.",
        alert_kill_confirm: "¿Deseas activar el interruptor de emergencia y liquidar todas las posiciones en USDT?",
        alert_kill_done: "Interruptor de emergencia ACTIVADO. Posiciones liquidadas en USDT."
    },
    de: {
        page_title: "TradeAID Web3 dApp — Autonomes Cockpit",
        nav_back_title: "Zurück zur Landingpage",
        connect_wallet: "⚡ Wallet Verbinden",
        disconnect: "Trennen",
        chain_warning: "⚠️ Falsches Netzwerk: Anderes Netzwerk als Polygon POS (137) erkannt.",
        btn_switch_polygon: "Zu Polygon wechseln",
        
        powered_by: "Unterstützt von",
        audited_by: "Geprüft & Zertifiziert von",
        engineered_by: "Entwickelt von",
        native_on: "Nativ auf",
        
        paywall_tag: "ON-CHAIN SIGNATURANGEBOT",
        dao_title: "TRADEAID DAO-QUOTE AKTIVIERUNG (1. ZUGANG)",
        dao_desc: "Beinhaltet lebenslange DAO-Gründer-Mitgliedschaft und vollständige Freischaltung des TradeAID Cockpits.",
        session_title: "SITZUNGS-ZUGANGSPASS (USDT AUF POLYGON)",
        session_desc: "Sitzungsgebühr für autonome Ausführung und 24/7 Position Guardian Schutz.",
        quote_req_amount: "ERFORDERLICHER BETRAG:",
        quote_recipient: "EMPFÄNGER (TREASURY):",
        quote_network: "BLOCKCHAIN-NETZWERK:",
        quote_your_wallet: "DEINE WALLET:",
        wallet_not_connected: "Nicht verbunden",
        status_waiting_sign: "Warten auf interaktive Signatur...",
        btn_sign_execute: "✍️ AUF POLYGON SIGNIEREN & AUSFÜHREN (USDT)",
        zero_custody_notice: "🔒 Non-Custodial: Direkte ERC-20 Transaktion über deine Wallet.",
        
        guardian_status: "POSITION GUARDIAN: <strong>24/7 AKTIV</strong>",
        guardian_ceiling: "OBERGRENZE: -5.0%",
        metric_cash: "LIQUIDES GUTHABEN",
        metric_equity: "GESAMTKAPITAL",
        metric_net_edge: "MIN. NET EDGE",
        metric_exposure: "AKTIVE EXPOSITION",
        
        tab_scanner: "📡 Scanner",
        tab_positions: "📈 Positionen (0)",
        tab_strategies: "🧠 Strategien",
        tab_security: "🚨 Sicherheit",
        
        scanner_title: "ÜBERWACHTE POLYGON-MÄRKTE",
        live_tick: "LIVE TICK: 10s",
        trending: "TRENDING",
        ranging: "SEITWÄRTS",
        signal_buy_pol: "KI-SIGNAL: KAUFEN (Konf. 85%)",
        signal_no_trade: "KI-SIGNAL: KEIN HANDEL",
        signal_buy_wbtc: "KI-SIGNAL: KAUFEN (Konf. 78%)",
        est_net_edge: "Geschätzter Net Edge:",
        dynamic_stop: "Dynamischer Stop:",
        awaiting_range: "Warten auf Ausbruch",
        be_lock: "Break-Even-Schutz:",
        gating_filter: "(Gating-Filter)",
        
        no_pos_title: "Keine Positionen mit Risiko belegt",
        no_pos_desc: "Position Guardian wartet auf Überschreitung der Net Edge Schwelle (+0.40%). 100% des Kapitals in USDT gesichert.",
        
        strat_1_title: "Scalping-Strategie (1m/3m/5m)",
        strat_1_desc: "Max. Spread-Filter 0.15% | Mikro-Momentum",
        strat_2_title: "Trendfolge (EMA 12/26 + MACD)",
        strat_2_desc: "Erkennung von Makro-Trendausbrüchen",
        strat_3_title: "Ausbruch & Donchian-Kanäle",
        strat_3_desc: "Hohe Expansionsvolatilität",
        strat_4_title: "Mean Reversion (Z-Score + RSI)",
        strat_4_desc: "Schnelle Umkehr bei Überkauft/Überverkauft",
        strat_weight: "GEWICHTUNG:",
        
        kill_switch_title: "NOTFALL-NOT-AUS-SCHALTER",
        kill_switch_desc: "Schließt im Notfall sofort alle Positionen und liquidiert 100% in USDT auf deiner Wallet.",
        kill_switch_btn: "🛑 NOT-AUS-SCHALTER AUSLÖSEN",
        cortex_title: "GEPRÜFT & ZERTIFIZIERT VON CORTEX",
        cortex_desc: "Kontinuierliche heuristische Sicherheitstests auf bor RPC, Anti-Honeypot-Gate und formale Smart-Contract-Prüfung.",
        cortex_pill_1: "✓ FORMALE PRÜFUNG: BESTANDEN",
        cortex_pill_2: "✓ FAIL-CLOSED PROTOKOLL: AKTIV",
        neuralog_title: "ENTWICKELT VON NEURALOG · POWERED BY BLOCKCHAIN+",
        neuralog_desc: "Quant-Engine auf Basis statistischer Modelle von Neuralog, Blockchain+ Routing und nativer Polygon-Finalität (137).",
        
        ticker_engine: "TRADEAID · Powered by Blockchain+ · Audited by Cortex · Engineered by Neuralog · Polygon 137",
        
        alert_no_wallet: "Keine Web3 Wallet gefunden. Bitte MetaMask, Rabby installieren oder in mobiler Wallet öffnen.",
        alert_connect_rejected: "Verbindung vom Nutzer abgelehnt.",
        alert_tx_submitted: "Transaktion gesendet! Hash: ",
        alert_tx_confirmed: "Zahlung on-chain bestätigt! Cockpit freigeschaltet.",
        alert_tx_failed: "Transaktion fehlgeschlagen oder abgelehnt.",
        alert_kill_confirm: "Achtung: Möchtest du den Not-Aus-Schalter aktivieren und alle Positionen in USDT liquidieren?",
        alert_kill_done: "Not-Aus-Schalter AKTIVIERT. Alle Positionen in USDT liquidiert."
    },
    fr: {
        page_title: "TradeAID Web3 dApp — Cockpit Autonome",
        nav_back_title: "Retour à la page d'accueil",
        connect_wallet: "⚡ Connecter Portefeuille",
        disconnect: "Déconnecter",
        chain_warning: "⚠️ Mauvais Réseau : Réseau différent de Polygon POS (137) détecté.",
        btn_switch_polygon: "Passer à Polygon",
        
        powered_by: "Propulsé par",
        audited_by: "Audité et Certifié par",
        engineered_by: "Conçu par",
        native_on: "Natif sur",
        
        paywall_tag: "DEVIS DE SIGNATURE ON-CHAIN",
        dao_title: "ACTIVATION DE LA QUOTE DAO TRADEAID (1er ACCÈS)",
        dao_desc: "Comprend l'adhésion permanente DAO Founders et le déverrouillage total du cockpit autonome TradeAID.",
        session_title: "PASS D'ACCÈS DE SESSION (USDT SUR POLYGON)",
        session_desc: "Frais de session pour l'exécution autonome et la protection Position Guardian 24/7.",
        quote_req_amount: "MONTANT REQUIS :",
        quote_recipient: "DESTINATAIRE (TRÉSORERIE) :",
        quote_network: "RÉSEAU BLOCKCHAIN :",
        quote_your_wallet: "VOTRE PORTEFEUILLE :",
        wallet_not_connected: "Non Connecté",
        status_waiting_sign: "En attente de signature interactive...",
        btn_sign_execute: "✍️ SIGNER ET EXÉCUTER SUR POLYGON (USDT)",
        zero_custody_notice: "🔒 Non-Custodial : Transaction directe ERC-20 via votre portefeuille.",
        
        guardian_status: "POSITION GUARDIAN : <strong>ACTIF 24/7</strong>",
        guardian_ceiling: "PLAFOND : -5.0%",
        metric_cash: "SOLDE LIQUIDE",
        metric_equity: "ACTIF TOTAL",
        metric_net_edge: "NET EDGE MINIMAL",
        metric_exposure: "EXPOSITION ACTIVE",
        
        tab_scanner: "📡 Scanner",
        tab_positions: "📈 Positions (0)",
        tab_strategies: "🧠 Stratégies",
        tab_security: "🚨 Sécurité",
        
        scanner_title: "MARCHÉS POLYGON SURVEILLÉS",
        live_tick: "TICK EN DIRECT : 10s",
        trending: "TENDANCE",
        ranging: "CONSOLIDATION",
        signal_buy_pol: "SIGNAL IA : ACHAT (Conf. 85%)",
        signal_no_trade: "SIGNAL IA : AUCUN TRADE",
        signal_buy_wbtc: "SIGNAL IA : ACHAT (Conf. 78%)",
        est_net_edge: "Net Edge Estimé :",
        dynamic_stop: "Stop Dynamique :",
        awaiting_range: "En attente de cassure",
        be_lock: "Verrouillage Break-Even :",
        gating_filter: "(Filtre de Contrôle)",
        
        no_pos_title: "Aucune Position Exposée au Risque",
        no_pos_desc: "Position Guardian attend le dépassement du seuil Net Edge (+0.40%). 100% des fonds sécurisés en USDT.",
        
        strat_1_title: "Stratégie Scalping (1m/3m/5m)",
        strat_1_desc: "Filtre spread max 0.15% | Micro-momentum",
        strat_2_title: "Suivi de Tendance (EMA 12/26 + MACD)",
        strat_2_desc: "Identification des ruptures de tendance macro",
        strat_3_title: "Cassure & Canaux de Donchian",
        strat_3_desc: "Forte volatilité d'expansion",
        strat_4_title: "Retour à la Moyenne (Z-Score + RSI)",
        strat_4_desc: "Inversion rapide sur surachat/survente",
        strat_weight: "POIDS :",
        
        kill_switch_title: "ARRÊT D'URGENCE (KILL SWITCH)",
        kill_switch_desc: "En cas d'urgence ou d'anomalie, ferme immédiatement toutes les positions et liquide 100% en USDT sur votre portefeuille.",
        kill_switch_btn: "🛑 DÉCLENCHER L'ARRÊT D'URGENCE",
        cortex_title: "AUDITÉ & CERTIFIÉ PAR CORTEX",
        cortex_desc: "Tests de sécurité continus sur RPC bor, porte anti-honeypot et vérification formelle des contrats intelligents.",
        cortex_pill_1: "✓ VÉRIFICATION FORMELLE : VALIDÉE",
        cortex_pill_2: "✓ PROTOCOLE FAIL-CLOSED : ACTIF",
        neuralog_title: "CONÇU PAR NEURALOG · PROPULSÉ PAR BLOCKCHAIN+",
        neuralog_desc: "Moteur quantitatif alimenté par les modèles statistiques Neuralog, routage Blockchain+ et finalité native Polygon (137).",
        
        ticker_engine: "TRADEAID · Propulsé par Blockchain+ · Audité par Cortex · Conçu par Neuralog · Polygon 137",
        
        alert_no_wallet: "Aucun portefeuille Web3 détecté. Installez MetaMask, Rabby ou ouvrez dans votre portefeuille mobile.",
        alert_connect_rejected: "Connexion refusée par l'utilisateur.",
        alert_tx_submitted: "Transaction soumise ! Hash : ",
        alert_tx_confirmed: "Paiement confirmé sur la blockchain ! Cockpit déverrouillé.",
        alert_tx_failed: "Échec de la transaction ou refusée.",
        alert_kill_confirm: "Attention : Voulez-vous activer l'arrêt d'urgence et liquider toutes les positions en USDT ?",
        alert_kill_done: "Arrêt d'urgence ACTIVÉ. Toutes les positions ont été liquidées en USDT."
    },
    ja: {
        page_title: "TradeAID Web3 dApp — 自律型コックピット",
        nav_back_title: "ランディングページに戻る",
        connect_wallet: "⚡ ウォレット接続",
        disconnect: "切断",
        chain_warning: "⚠️ ネットワークエラー: Polygon POS (137) 以外のネットワークが検出されました。",
        btn_switch_polygon: "Polygonに切り替え",
        
        powered_by: "技術提供:",
        audited_by: "監査・認証:",
        engineered_by: "開発設計:",
        native_on: "ネイティブ稼働:",
        
        paywall_tag: "オンチェーン署名見積書",
        dao_title: "TRADEAID DAO クォータ有効化 (初回アクセス)",
        dao_desc: "恒久的なDAO創設者メンバーシップとTradeAID自律型コックピットの完全アンロックが含まれます。",
        session_title: "セッションアクセスパス (POLYGON上のUSDT)",
        session_desc: "自律実行および24時間365日のPosition Guardian保護のためのセッション利用枠。",
        quote_req_amount: "必要金額:",
        quote_recipient: "送金先 (トレジャリー):",
        quote_network: "ブロックチェーンネットワーク:",
        quote_your_wallet: "お客様のウォレット:",
        wallet_not_connected: "未接続",
        status_waiting_sign: "署名リクエスト待機中...",
        btn_sign_execute: "✍️ POLYGONで署名・実行 (USDT)",
        zero_custody_notice: "🔒 ノンカストディアル: ウォレットから直接実行されるERC-20取引。",
        
        guardian_status: "ポジションガーディアン: <strong>24/7 稼働中</strong>",
        guardian_ceiling: "最大許容損失: -5.0%",
        metric_cash: "流動性残高",
        metric_equity: "総資産評価額",
        metric_net_edge: "最小ネットエッジ",
        metric_exposure: "現在ポジション露出",
        
        tab_scanner: "📡 スキャナー",
        tab_positions: "📈 保有ポジション (0)",
        tab_strategies: "🧠 戦略一覧",
        tab_security: "🚨 セキュリティ",
        
        scanner_title: "監視対象 POLYGON マーケット",
        live_tick: "ライブ更新: 10秒",
        trending: "トレンド",
        ranging: "レンジ相場",
        signal_buy_pol: "AIシグナル: 買い (信頼度 85%)",
        signal_no_trade: "AIシグナル: 見送り (NO_TRADE)",
        signal_buy_wbtc: "AIシグナル: 買い (信頼度 78%)",
        est_net_edge: "推定ネットエッジ:",
        dynamic_stop: "動的ストップロス:",
        awaiting_range: "ブレイクアウト待機中",
        be_lock: "損益分岐点ロック:",
        gating_filter: "(ゲートフィルター作動)",
        
        no_pos_title: "リスクにさらされているポジションはありません",
        no_pos_desc: "Position Guardianはネットエッジ閾値(+0.40%)の超過を待機しています。資金は100% USDTで保全されています。",
        
        strat_1_title: "スキャルピング戦略 (1分/3分/5分足)",
        strat_1_desc: "最大スプレッド0.15%制限 | マイクロモメンタム",
        strat_2_title: "トレンドフォロー (EMA 12/26 + MACD)",
        strat_2_desc: "マクロトレンドのブレイクアウト検出",
        strat_3_title: "ドンチャンチャネル・ブレイクアウト",
        strat_3_desc: "ボラティリティ急拡大追従",
        strat_4_title: "平均回帰 (Z-Score + RSIダイバージェンス)",
        strat_4_desc: "買われすぎ・売られすぎからの即時反転",
        strat_weight: "配分比重:",
        
        kill_switch_title: "緊急停止キルスイッチ",
        kill_switch_desc: "緊急時や市場急変時、全ポジションを即座に成行決済し、100% USDTでウォレットに退避します。",
        kill_switch_btn: "🛑 緊急キルスイッチを発動",
        cortex_title: "CORTEX によるセキュリティ監査・認証済",
        cortex_desc: "bor RPC、ハニーポット防止ゲート、スマートコントラクト形式手法検証を常時実施。",
        cortex_pill_1: "✓ 形式手法検証: 合格",
        cortex_pill_2: "✓ フェイルクローズ制御: 有効",
        neuralog_title: "NEURALOG エンジニアリング · BLOCKCHAIN+ 提供",
        neuralog_desc: "Neuralog統計モデル、Blockchain+分散型ルーティング、Polygon(137)即時ファイナリティを統合。",
        
        ticker_engine: "TRADEAID · Powered by Blockchain+ · Audited by Cortex · Engineered by Neuralog · Polygon 137",
        
        alert_no_wallet: "Web3ウォレットが見つかりません。MetaMask等をインストールするか、対応モバイルウォレットでお開きください。",
        alert_connect_rejected: "ユーザーによって接続が拒否されました。",
        alert_tx_submitted: "トランザクション送信完了！ Tx Hash: ",
        alert_tx_confirmed: "オンチェーン決済が承認されました！ コックピットがアンロックされました。",
        alert_tx_failed: "トランザクションが失敗したか、拒否されました。",
        alert_kill_confirm: "警告: 緊急キルスイッチを発動し、全ポジションをUSDTに即座清算しますか？",
        alert_kill_done: "キルスイッチが作動しました。全ポジションがUSDTに清算されました。"
    },
    pt: {
        page_title: "TradeAID Web3 dApp — Cockpit Autônomo",
        nav_back_title: "Voltar para a Landing Page",
        connect_wallet: "⚡ Conectar Carteira",
        disconnect: "Desconectar",
        chain_warning: "⚠️ Rede Incorreta: Rede diferente da Polygon POS (137) detectada.",
        btn_switch_polygon: "Mudar para Polygon",
        
        powered_by: "Desenvolvido por",
        audited_by: "Auditado e Certificado por",
        engineered_by: "Projetado por",
        native_on: "Nativo em",
        
        paywall_tag: "COTAÇÃO DE ASSINATURA ON-CHAIN",
        dao_title: "ATIVAÇÃO DE COTA DAO TRADEAID (1° ACESSO)",
        dao_desc: "Inclui associação vitalícia de Fundadores DAO e desbloqueio total do cockpit autônomo TradeAID.",
        session_title: "PASSE DE ACESSO DE SESSÃO (USDT NA POLYGON)",
        session_desc: "Taxa de sessão para execução autônoma e proteção Position Guardian 24/7.",
        quote_req_amount: "VALOR NECESSÁRIO:",
        quote_recipient: "DESTINATÁRIO (TESOURARIA):",
        quote_network: "REDE BLOCKCHAIN:",
        quote_your_wallet: "SUA CARTEIRA:",
        wallet_not_connected: "Não Conectada",
        status_waiting_sign: "Aguardando assinatura interativa...",
        btn_sign_execute: "✍️ ASSINAR E EXECUTAR NA POLYGON (USDT)",
        zero_custody_notice: "🔒 Não-Custodial: Transação direta ERC-20 via sua carteira.",
        
        guardian_status: "POSITION GUARDIAN: <strong>ATIVO 24/7</strong>",
        guardian_ceiling: "TETO MÁXIMO: -5.0%",
        metric_cash: "SALDO LÍQUIDO",
        metric_equity: "PATRIMÔNIO TOTAL",
        metric_net_edge: "NET EDGE MÍNIMO",
        metric_exposure: "EXPOSIÇÃO ATIVA",
        
        tab_scanner: "📡 Scanner",
        tab_positions: "📈 Posições (0)",
        tab_strategies: "🧠 Estratégias",
        tab_security: "🚨 Segurança",
        
        scanner_title: "MERCADOS POLYGON MONITORADOS",
        live_tick: "TICK AO VIVO: 10s",
        trending: "TENDÊNCIA",
        ranging: "LATERAL",
        signal_buy_pol: "SINAL IA: COMPRA (Conf. 85%)",
        signal_no_trade: "SINAL IA: SEM OPERAÇÃO",
        signal_buy_wbtc: "SINAL IA: COMPRA (Conf. 78%)",
        est_net_edge: "Net Edge Estimado:",
        dynamic_stop: "Stop Dinâmico:",
        awaiting_range: "Aguardando rompimento",
        be_lock: "Trava de Break-Even:",
        gating_filter: "(Filtro Gating)",
        
        no_pos_title: "Nenhuma Posição Exposta ao Risco",
        no_pos_desc: "O Position Guardian aguarda superação da margem de Net Edge (+0.40%). 100% dos fundos preservados em USDT.",
        
        strat_1_title: "Estratégia Scalping (1m/3m/5m)",
        strat_1_desc: "Filtro spread máx 0.15% | Micro-momentum",
        strat_2_title: "Seguimento de Tendência (EMA 12/26 + MACD)",
        strat_2_desc: "Identificação de rompimentos de tendência macro",
        strat_3_title: "Rompimento & Canais Donchian",
        strat_3_desc: "Alta volatilidade de expansão",
        strat_4_title: "Reversão à Média (Z-Score + RSI)",
        strat_4_desc: "Reversão rápida em sobrecompra/sobrevenda",
        strat_weight: "PESO:",
        
        kill_switch_title: "INTERRUPTOR DE EMERGÊNCIA (KILL SWITCH)",
        kill_switch_desc: "Em caso de emergência ou anomalia, encerra imediatamente todas as posições liquidando 100% em USDT na sua carteira.",
        kill_switch_btn: "🛑 ATIVAR INTERRUPTOR DE EMERGÊNCIA",
        cortex_title: "AUDITADO E CERTIFICADO POR CORTEX",
        cortex_desc: "Testes heurísticos contínuos em RPC bor, gate anti-honeypot e verificação formal de contratos inteligentes.",
        cortex_pill_1: "✓ VERIFICAÇÃO FORMAL: APROVADA",
        cortex_pill_2: "✓ PROTOCOLO FAIL-CLOSED: ATIVO",
        neuralog_title: "PROJETADO POR NEURALOG · POWERED BY BLOCKCHAIN+",
        neuralog_desc: "Motor quantitativo baseado em modelos estatísticos Neuralog, roteamento Blockchain+ e finalização nativa na Polygon (137).",
        
        ticker_engine: "TRADEAID · Desenvolvido por Blockchain+ · Auditado por Cortex · Projetado por Neuralog · Polygon 137",
        
        alert_no_wallet: "Nenhuma carteira Web3 detectada. Instale o MetaMask, Rabby ou abra no navegador da sua carteira móvel.",
        alert_connect_rejected: "Conexão rejeitada pelo usuário.",
        alert_tx_submitted: "Transação enviada! Hash: ",
        alert_tx_confirmed: "Pagamento confirmado on-chain! Cockpit desbloqueado.",
        alert_tx_failed: "Transação falhou ou foi rejeitada.",
        alert_kill_confirm: "Atenção: Deseja acionar o Kill Switch e liquidar todas as posições em USDT?",
        alert_kill_done: "Kill Switch ATIVADO. Todas as posições liquidadas em USDT."
    },
    ru: {
        page_title: "TradeAID Web3 dApp — Автономный Кокпит",
        nav_back_title: "Назад на главную",
        connect_wallet: "⚡ Подключить Кошелек",
        disconnect: "Отключить",
        chain_warning: "⚠️ Неверная Сеть: Обнаружена сеть, отличная от Polygon POS (137).",
        btn_switch_polygon: "Переключить на Polygon",
        
        powered_by: "При поддержке",
        audited_by: "Аудит и Сертификация от",
        engineered_by: "Разработано",
        native_on: "Нативно в",
        
        paywall_tag: "ОН-ЧЕЙН РАСЧЕТ ПОДПИСИ",
        dao_title: "АКТИВАЦИЯ КВОТЫ TRADEAID DAO (1-й ДОСТУП)",
        dao_desc: "Включает пожизненное членство в DAO Founders и полную разблокировку автономного кокпита TradeAID.",
        session_title: "СЕССИОННЫЙ ПРОПУСК (USDT В POLYGON)",
        session_desc: "Комиссия сессии за автономное исполнение и круглосуточную защиту Position Guardian 24/7.",
        quote_req_amount: "ТРЕБУЕМАЯ СУММА:",
        quote_recipient: "ПОЛУЧАТЕЛЬ (КАЗНАЧЕЙСТВО):",
        quote_network: "СЕТЬ БЛОКЧЕЙН:",
        quote_your_wallet: "ВАШ КОШЕЛЕК:",
        wallet_not_connected: "Не подключен",
        status_waiting_sign: "Ожидание интерактивной подписи...",
        btn_sign_execute: "✍️ ПОДПИСАТЬ И ВЫПОЛНИТЬ В POLYGON (USDT)",
        zero_custody_notice: "🔒 Без кастодиальности: Прямая транзакция ERC-20 с вашего кошелька.",
        
        guardian_status: "POSITION GUARDIAN: <strong>АКТИВЕН 24/7</strong>",
        guardian_ceiling: "ЛИМИТ: -5.0%",
        metric_cash: "ЛИКВИДНЫЙ БАЛАНС",
        metric_equity: "ОБЩИЙ КАПИТАЛ",
        metric_net_edge: "МИН. ЧИСТЫЙ ЭДЖ",
        metric_exposure: "АКТИВНАЯ ЭКСПОЗИЦИЯ",
        
        tab_scanner: "📡 Сканер",
        tab_positions: "📈 Позиции (0)",
        tab_strategies: "🧠 Стратегии",
        tab_security: "🚨 Безопасность",
        
        scanner_title: "ОТСЛЕЖИВАЕМЫЕ РЫНКИ POLYGON",
        live_tick: "ОБНОВЛЕНИЕ: 10с",
        trending: "ТРЕНД",
        ranging: "ФЛЭТ",
        signal_buy_pol: "СИГНАЛ ИИ: BUY (Доверие 85%)",
        signal_no_trade: "СИГНАЛ ИИ: БЕЗ СДЕЛОК",
        signal_buy_wbtc: "СИГНАЛ ИИ: BUY (Доверие 78%)",
        est_net_edge: "Расчетный чистый эдж:",
        dynamic_stop: "Динамический стоп:",
        awaiting_range: "Ожидание пробоя диапазона",
        be_lock: "Фиксация безубытка:",
        gating_filter: "(Гейтинг-фильтр)",
        
        no_pos_title: "Нет открытых рисковых позиций",
        no_pos_desc: "Position Guardian ожидает превышения порога Net Edge (+0.40%). 100% средств сохранены в USDT.",
        
        strat_1_title: "Скальпинг (1м/3м/5м)",
        strat_1_desc: "Фильтр спреда макс 0.15% | Микро-моментум",
        strat_2_title: "Следование за трендом (EMA 12/26 + MACD)",
        strat_2_desc: "Определение пробоев макротрендов",
        strat_3_title: "Пробой и каналы Дончиана",
        strat_3_desc: "Торговля на высокой волатильности",
        strat_4_title: "Возврат к среднему (Z-Score + RSI)",
        strat_4_desc: "Быстрый разворот при перекупленности/перепроданности",
        strat_weight: "ВЕС:",
        
        kill_switch_title: "АВАРИЙНЫЙ ВЫКЛЮЧАТЕЛЬ (KILL SWITCH)",
        kill_switch_desc: "В случае экстренной ситуации немедленно закрывает все позиции и на 100% конвертирует в USDT на ваш кошелек.",
        kill_switch_btn: "🛑 ЗАПУСТИТЬ АВАРИЙНЫЙ KILL SWITCH",
        cortex_title: "АУДИТИРОВАНО И СЕРТИФИЦИРОВАНО CORTEX",
        cortex_desc: "Непрерывные эвристические проверки bor RPC, шлюз против honeypot и формальная верификация контрактов.",
        cortex_pill_1: "✓ ФОРМАЛЬНАЯ ВЕРИФИКАЦИЯ: ПРОЙДЕНА",
        cortex_pill_2: "✓ ПРОТОКОЛ FAIL-CLOSED: АКТИВЕН",
        neuralog_title: "РАЗРАБОТКА NEURALOG · POWERED BY BLOCKCHAIN+",
        neuralog_desc: "Квант-движок на основе статистических моделей Neuralog, децентрализованный роутинг Blockchain+ и финализация Polygon (137).",
        
        ticker_engine: "TRADEAID · Powered by Blockchain+ · Audited by Cortex · Engineered by Neuralog · Polygon 137",
        
        alert_no_wallet: "Web3 кошелек не найден. Установите MetaMask, Rabby или откройте во встроенном браузере мобильного кошелька.",
        alert_connect_rejected: "Подключение отклонено пользователем.",
        alert_tx_submitted: "Транзакция отправлена! Хеш: ",
        alert_tx_confirmed: "Оплата подтверждена в блокчейне! Кокпит разблокирован.",
        alert_tx_failed: "Ошибка транзакции или отмена пользователем.",
        alert_kill_confirm: "Внимание: Активировать аварийный Kill Switch и ликвидировать все позиции в USDT?",
        alert_kill_done: "Kill Switch АКТИВИРОВАН. Все позиции ликвидированы в USDT."
    },
    ar: {
        page_title: "TradeAID Web3 dApp — مقصورة القيادة المستقلة",
        nav_back_title: "العودة إلى الصفحة الرئيسية",
        connect_wallet: "⚡ ربط المحفظة",
        disconnect: "فصل",
        chain_warning: "⚠️ شبكة غير صحيحة: تم اكتشاف شبكة مختلفة عن Polygon POS (137).",
        btn_switch_polygon: "التبديل إلى Polygon",
        
        powered_by: "مدعوم من",
        audited_by: "تدقيق واعتماد بواسطة",
        engineered_by: "هندسة وتطوير",
        native_on: "أصلي على",
        
        paywall_tag: "عرض توقيع على البلوكشين",
        dao_title: "تفعيل حصة TRADEAID DAO (الوصول الأول)",
        dao_desc: "يتضمن عضوية مؤسسي DAO الدائمة وفتحاً كاملاً لمقصورة قيادة TradeAID المستقلة.",
        session_title: "تصريح دخول الجلسة (USDT على POLYGON)",
        session_desc: "رسوم الجلسة للتنفيذ المستقل وحماية Position Guardian على مدار الساعة.",
        quote_req_amount: "المبلغ المطلوب:",
        quote_recipient: "المستلم (الخزينة):",
        quote_network: "شبكة البلوكشين:",
        quote_your_wallet: "محفظتك:",
        wallet_not_connected: "غير متصل",
        status_waiting_sign: "في انتظار التوقيع التفاعلي...",
        btn_sign_execute: "✍️ التوقيع والتنفيذ على POLYGON (USDT)",
        zero_custody_notice: "🔒 غير وصائية: معاملة ERC-20 مباشرة عبر محفظتك الشخصية.",
        
        guardian_status: "حارس المركز: <strong>نشط 24/7</strong>",
        guardian_ceiling: "الحد الأقصى للإيقاف: -5.0%",
        metric_cash: "الرصيد المتاح",
        metric_equity: "إجمالي حقوق الملكية",
        metric_net_edge: "الحد الأدنى للميزة الصافية",
        metric_exposure: "التعرض النشط",
        
        tab_scanner: "📡 الماسح",
        tab_positions: "📈 الصفقات (0)",
        tab_strategies: "🧠 الاستراتيجيات",
        tab_security: "🚨 الأمان والإنقاذ",
        
        scanner_title: "أسواق POLYGON الخاضعة للمراقبة",
        live_tick: "تحديث مباشر: 10 ثوانٍ",
        trending: "اتجاه صاعد/هابط",
        ranging: "تداول عرضي",
        signal_buy_pol: "إشارة AI: شراء (ثقة 85%)",
        signal_no_trade: "إشارة AI: لا تداول",
        signal_buy_wbtc: "إشارة AI: شراء (ثقة 78%)",
        est_net_edge: "الميزة الصافية المقدرة:",
        dynamic_stop: "وقف الخسارة الديناميكي:",
        awaiting_range: "في انتظار كسر النطاق",
        be_lock: "قفل نقطة التعادل:",
        gating_filter: "(تصفية الصمام الأمني)",
        
        no_pos_title: "لا توجد مراكز معرضة للمخاطر",
        no_pos_desc: "ينتظر Position Guardian تجاوز حد الميزة الصافية (+0.40%). 100% من الأموال محفوظة بأمان في USDT.",
        
        strat_1_title: "استراتيجية السكالبينج (1د/3د/5د)",
        strat_1_desc: "تصفية الفارق الأقصى 0.15% | زخم دقيق",
        strat_2_title: "تتبع الاتجاه (EMA 12/26 + MACD)",
        strat_2_desc: "تحديد اختراقات الاتجاه الكلي",
        strat_3_title: "قنوات دونكايان والاختراق",
        strat_3_desc: "تقلبات توسعية عالية",
        strat_4_title: "الارتداد للمتوسط (Z-Score + RSI)",
        strat_4_desc: "انعكاس سريع عند ذروة الشراء/البيع",
        strat_weight: "الوزن النسبي:",
        
        kill_switch_title: "مفتاح الإيقاف الطارئ (KILL SWITCH)",
        kill_switch_desc: "في حالات الطوارئ أو الشذوذ السوقي، يغلق فوراً جميع المراكز ويحولها بنسبة 100% إلى USDT في محفظتك.",
        kill_switch_btn: "🛑 تفعيل مفتاح الإيقاف الفوري",
        cortex_title: "تم التدقيق والاعتماد بواسطة CORTEX",
        cortex_desc: "اختبارات أمنية استكشافية مستمرة على عقدة bor RPC، وبوابة مكافحة العقود الخبيثة، والتحقق الرسمي من العقود الذكية.",
        cortex_pill_1: "✓ التحقق الرسمي: ناجح ومؤكد",
        cortex_pill_2: "✓ بروتوكول الإغلاق الوقائي: نشط",
        neuralog_title: "هندسة NEURALOG · مدعوم من BLOCKCHAIN+",
        neuralog_desc: "محرك كمي يعمل بنماذج Neuralog الإحصائية، وتوجيه لا مركزي من Blockchain+، وحتمية Polygon (137).",
        
        ticker_engine: "TRADEAID · مدعوم من Blockchain+ · معتمد من Cortex · هندسة Neuralog · أصلي على Polygon 137",
        
        alert_no_wallet: "لم يتم العثور على محفظة Web3. يرجى تثبيت MetaMask أو الفتح في متصفح محفظة الهاتف.",
        alert_connect_rejected: "تم رفض الاتصال من قبل المستخدم.",
        alert_tx_submitted: "تم إرسال المعاملة للبلوكشين! الرمز: ",
        alert_tx_confirmed: "تم تأكيد الدفع على البلوكشين! تم فتح مقصورة القيادة.",
        alert_tx_failed: "فشلت المعاملة أو تم رفضها.",
        alert_kill_confirm: "تنبيه: هل تريد تفعيل مفتاح الإيقاف الطارئ وتصفية جميع المراكز إلى USDT؟",
        alert_kill_done: "تم تفعيل مفتاح الإيقاف الطارئ. تمت تصفية جميع المراكز إلى USDT."
    }
};

class I18nManager {
    constructor() {
        this.currentLang = localStorage.getItem("tradeaid_lang") || "en"; // Default is strictly English
    }

    init() {
        this.applyLanguage(this.currentLang);
        this.bindSwitcher();
    }

    bindSwitcher() {
        const selectEl = document.getElementById("lang-select");
        if (selectEl) {
            selectEl.value = this.currentLang;
            selectEl.addEventListener("change", (e) => {
                this.setLanguage(e.target.value);
            });
        }
    }

    setLanguage(lang) {
        if (!TRANSLATIONS[lang]) {
            console.warn(`Language ${lang} not supported, falling back to en`);
            lang = "en";
        }
        this.currentLang = lang;
        localStorage.setItem("tradeaid_lang", lang);
        const selectEl = document.getElementById("lang-select");
        if (selectEl && selectEl.value !== lang) {
            selectEl.value = lang;
        }
        this.applyLanguage(lang);
    }

    t(key) {
        const dict = TRANSLATIONS[this.currentLang] || TRANSLATIONS.en;
        return dict[key] !== undefined ? dict[key] : (TRANSLATIONS.en[key] || key);
    }

    applyLanguage(lang) {
        const dict = TRANSLATIONS[lang] || TRANSLATIONS.en;
        
        // Document lang and direction
        document.documentElement.lang = lang;
        document.documentElement.dir = (lang === "ar") ? "rtl" : "ltr";
        
        // Page title
        if (dict.page_title) {
            document.title = dict.page_title;
        }

        // Apply all data-i18n elements
        document.querySelectorAll("[data-i18n]").forEach((el) => {
            const key = el.getAttribute("data-i18n");
            if (dict[key] !== undefined) {
                // If element contains markup like <strong> or <span>, use innerHTML, else textContent
                if (dict[key].includes("<") && dict[key].includes(">")) {
                    el.innerHTML = dict[key];
                } else {
                    el.textContent = dict[key];
                }
            }
        });

        // Apply attributes like data-i18n-title or data-i18n-placeholder
        document.querySelectorAll("[data-i18n-title]").forEach((el) => {
            const key = el.getAttribute("data-i18n-title");
            if (dict[key] !== undefined) {
                el.setAttribute("title", dict[key]);
            }
        });

        // Dispatch custom event for dynamic components (web3-dapp.js)
        window.dispatchEvent(new CustomEvent("languageChanged", { detail: { lang, dict } }));
    }
}

// Global instance
window.i18n = new I18nManager();
window.t = (key) => window.i18n.t(key);

document.addEventListener("DOMContentLoaded", () => {
    window.i18n.init();
});
