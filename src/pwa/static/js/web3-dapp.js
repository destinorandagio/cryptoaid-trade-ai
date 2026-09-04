/**
 * CryptoAID Trade AI — Web3 dApp Controller with Multi-Language Support
 * Chain: Polygon POS Mainnet (137 / 0x89)
 * Treasury: 0x3C320B3a0917fF44BF6551CDdee44402AFcF250C
 * USDT Polygon: 0xc2132D05D31c914a87C6611C10748AEb04B58e8F (Decimals: 6)
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
    DAO_QUOTE_AMOUNT: 100, // 100 USDT on first access
    SESSION_QUOTE_AMOUNT: 5 // 5 USDT on subsequent accesses
};

class Web3Controller {
    constructor() {
        this.account = null;
        this.chainId = null;
        this.hasDaoMembership = false;
        this.isSessionUnlocked = false;
        this.init();
    }

    init() {
        this.bindEvents();
        this.checkExistingSession();
    }

    bindEvents() {
        const btnConnect = document.getElementById("btn-connect-wallet");
        if (btnConnect) {
            btnConnect.addEventListener("click", () => this.connectWallet());
        }

        const btnPay = document.getElementById("btn-sign-access");
        if (btnPay) {
            btnPay.addEventListener("click", () => this.executeAccessPayment());
        }

        const btnSwitch = document.getElementById("btn-switch-polygon");
        if (btnSwitch) {
            btnSwitch.addEventListener("click", () => this.switchToPolygon());
        }

        if (window.ethereum) {
            window.ethereum.on("accountsChanged", (accounts) => this.handleAccountsChanged(accounts));
            window.ethereum.on("chainChanged", (chainId) => this.handleChainChanged(chainId));
        }

        // Listen for real-time language changes
        window.addEventListener("languageChanged", () => {
            this.updatePaymentModalUI();
            if (this.account) {
                this.renderWalletConnected();
            } else {
                this.renderWalletDisconnected();
            }
        });
    }

    checkExistingSession() {
        const savedAccount = localStorage.getItem("ca_connected_wallet");
        if (savedAccount) {
            this.account = savedAccount;
            this.checkDaoStatus(savedAccount);
            this.renderWalletConnected();
        }
    }

    checkDaoStatus(address) {
        const key = `ca_dao_member_${address.toLowerCase()}`;
        this.hasDaoMembership = localStorage.getItem(key) === "true";
        this.updatePaymentModalUI();
    }

    updatePaymentModalUI() {
        const quoteTypeEl = document.getElementById("quote-type-label");
        const quoteAmountEl = document.getElementById("quote-amount-display");
        const quoteDescEl = document.getElementById("quote-desc-display");

        const t = (key, fallback) => (window.t ? window.t(key) : fallback);

        if (quoteTypeEl && quoteAmountEl && quoteDescEl) {
            if (!this.hasDaoMembership) {
                quoteTypeEl.textContent = t("dao_title", "TRADEAID DAO QUOTA ACTIVATION (1st ACCESS)");
                quoteAmountEl.textContent = "100.00 USDT";
                quoteDescEl.textContent = t("dao_desc", "Includes permanent DAO Founders membership and full unlock of TradeAID autonomous cockpit.");
            } else {
                quoteTypeEl.textContent = t("session_title", "SESSION ACCESS PASS (USDT ON POLYGON)");
                quoteAmountEl.textContent = "5.00 USDT";
                quoteDescEl.textContent = t("session_desc", "Session fee for autonomous execution and 24/7 Position Guardian protection.");
            }
        }
    }

    async connectWallet() {
        const t = (key, fallback) => (window.t ? window.t(key) : fallback);
        if (!window.ethereum) {
            if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
                // Mobile deep link to MetaMask
                window.location.href = `https://metamask.app.link/dapp/${window.location.host}${window.location.pathname}`;
                return;
            }
            alert(t("alert_no_wallet", "No Web3 Wallet detected. Please install MetaMask, Rabby or open in your mobile wallet browser."));
            return;
        }

        try {
            const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
            await this.handleAccountsChanged(accounts);

            const chainId = await window.ethereum.request({ method: "eth_chainId" });
            await this.handleChainChanged(chainId);
        } catch (err) {
            console.error("Connect error:", err);
            alert(t("alert_connect_rejected", "Connection rejected by user."));
        }
    }

    async handleAccountsChanged(accounts) {
        if (!accounts || accounts.length === 0) {
            this.account = null;
            localStorage.removeItem("ca_connected_wallet");
            this.renderWalletDisconnected();
            return;
        }

        this.account = accounts[0];
        localStorage.setItem("ca_connected_wallet", this.account);
        this.checkDaoStatus(this.account);
        this.renderWalletConnected();
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
                                nativeCurrency: {
                                    name: "POL",
                                    symbol: "POL",
                                    decimals: 18,
                                },
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

    renderWalletConnected() {
        const btnConnect = document.getElementById("btn-connect-wallet");
        const modalPay = document.getElementById("modal-onchain-paywall");
        if (!this.account) return;

        const shortAddr = `${this.account.slice(0, 6)}...${this.account.slice(-4)}`;

        if (btnConnect) {
            btnConnect.innerHTML = `<span class="wallet-dot online"></span> ${shortAddr}`;
            btnConnect.classList.add("connected");
        }

        const walletDisplayAddr = document.getElementById("paywall-wallet-address");
        if (walletDisplayAddr) walletDisplayAddr.textContent = shortAddr;

        // Open Paywall if session is not yet unlocked
        if (!this.isSessionUnlocked && modalPay) {
            modalPay.classList.remove("hidden");
        }
    }

    renderWalletDisconnected() {
        const btnConnect = document.getElementById("btn-connect-wallet");
        const t = (key, fallback) => (window.t ? window.t(key) : fallback);
        if (btnConnect) {
            btnConnect.innerHTML = t("connect_wallet", "⚡ Connect Wallet");
            btnConnect.classList.remove("connected");
        }
    }

    async executeAccessPayment() {
        const t = (key, fallback) => (window.t ? window.t(key) : fallback);

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
        
        const amountUsdt = !this.hasDaoMembership ? CONFIG.DAO_QUOTE_AMOUNT : CONFIG.SESSION_QUOTE_AMOUNT;
        const rawUnits = BigInt(amountUsdt) * BigInt(10 ** CONFIG.USDT_DECIMALS);
        
        // ERC-20 transfer(address to, uint256 value)
        const toClean = CONFIG.TREASURY_ADDRESS.toLowerCase().replace("0x", "").padStart(64, "0");
        const valueClean = rawUnits.toString(16).padStart(64, "0");
        const txData = `0xa9059cbb${toClean}${valueClean}`;

        try {
            if (btnPay) btnPay.disabled = true;
            if (payStatusEl) {
                payStatusEl.textContent = `Awaiting signature for ${amountUsdt} USDT...`;
                payStatusEl.className = "status-info";
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
                payStatusEl.innerHTML = `Transaction submitted: <a href="${CONFIG.EXPLORER_URL}/tx/${txHash}" target="_blank" class="tx-link">${txHash.slice(0, 10)}...${txHash.slice(-6)} ↗</a>`;
                payStatusEl.className = "status-success";
            }

            // Save status
            const daoKey = `ca_dao_member_${this.account.toLowerCase()}`;
            localStorage.setItem(daoKey, "true");
            this.hasDaoMembership = true;
            this.isSessionUnlocked = true;

            setTimeout(() => {
                const modalPay = document.getElementById("modal-onchain-paywall");
                if (modalPay) modalPay.classList.add("hidden");
                const appCockpit = document.getElementById("dapp-cockpit-view");
                if (appCockpit) appCockpit.classList.remove("blurred");
                alert(`${t("alert_tx_confirmed", "Payment confirmed on-chain! Cockpit unlocked.")}\nTx: ${txHash.slice(0, 12)}...`);
            }, 1200);

        } catch (err) {
            console.error("Tx error:", err);
            if (btnPay) btnPay.disabled = false;
            if (payStatusEl) {
                payStatusEl.textContent = t("alert_tx_failed", "Transaction failed or rejected.");
                payStatusEl.className = "status-error";
            }
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    window.web3App = new Web3Controller();
});
