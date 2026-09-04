/**
 * CryptoAID Trade AI — Web3 dApp Controller
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
    }

    checkExistingSession() {
        const savedAccount = localStorage.getItem("ca_connected_wallet");
        if (savedAccount) {
            this.account = savedAccount;
            this.checkDaoStatus(savedAccount);
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

        if (quoteTypeEl && quoteAmountEl && quoteDescEl) {
            if (!this.hasDaoMembership) {
                quoteTypeEl.textContent = "ATTIVAZIONE QUOTA DAO TRADEAID (1° ACCESSO)";
                quoteAmountEl.textContent = "100.00 USDT";
                quoteDescEl.textContent = "Include membership permanente DAO Founders e sblocco totale dei motori algoritmici.";
            } else {
                quoteTypeEl.textContent = "SESSION ACCESS PASS (USDT ON POLYGON)";
                quoteAmountEl.textContent = "5.00 USDT";
                quoteDescEl.textContent = "Quota di sessione per l'esecuzione autonoma e il presidio Position Guardian 24/7.";
            }
        }
    }

    async connectWallet() {
        const statusEl = document.getElementById("wallet-status-msg");
        if (!window.ethereum) {
            if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
                // Mobile deep link to MetaMask / Trust Wallet
                const dappUrl = encodeURIComponent(window.location.href);
                window.location.href = `https://metamask.app.link/dapp/${window.location.host}${window.location.pathname}`;
                return;
            }
            alert("Nessun Web3 Wallet rilevato. Installa MetaMask, Rabby o apri la dApp nel browser del tuo wallet mobile (TrustWallet, Phantom, MetaMask).");
            return;
        }

        try {
            if (statusEl) statusEl.textContent = "Connessione in corso...";
            const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
            await this.handleAccountsChanged(accounts);

            const chainId = await window.ethereum.request({ method: "eth_chainId" });
            await this.handleChainChanged(chainId);
        } catch (err) {
            console.error("Connect error:", err);
            if (statusEl) statusEl.textContent = "Connessione rifiutata dall'utente.";
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
            // Error code 4902 means the chain has not been added to MetaMask
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
        if (btnConnect) {
            btnConnect.innerHTML = `⚡ Connetti Web3 Wallet`;
            btnConnect.classList.remove("connected");
        }
    }

    async executeAccessPayment() {
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
        // Method signature: 0xa9059cbb
        const toClean = CONFIG.TREASURY_ADDRESS.toLowerCase().replace("0x", "").padStart(64, "0");
        const valueClean = rawUnits.toString(16).padStart(64, "0");
        const txData = `0xa9059cbb${toClean}${valueClean}`;

        try {
            if (btnPay) btnPay.disabled = true;
            if (payStatusEl) {
                payStatusEl.textContent = `Richiesta firma on-chain per ${amountUsdt} USDT...`;
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
                payStatusEl.innerHTML = `Transazione confermata: <a href="${CONFIG.EXPLORER_URL}/tx/${txHash}" target="_blank" class="tx-link">${txHash.slice(0, 10)}...${txHash.slice(-6)} ↗</a>`;
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
                alert(`Accesso Confermato! Transazione Polygon registrata: ${txHash.slice(0, 12)}... Benvenuto nel Cockpit TradeAID.`);
            }, 1200);

        } catch (err) {
            console.error("Tx error:", err);
            if (btnPay) btnPay.disabled = false;
            if (payStatusEl) {
                payStatusEl.textContent = `Firma respinta o errore: ${err.message || err}`;
                payStatusEl.className = "status-error";
            }
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    window.web3App = new Web3Controller();
});
