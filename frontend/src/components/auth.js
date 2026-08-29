/**
 * BIAR Protocol - Wallet authentication client (SIWE-style sign-in).
 *
 * Flow:
 *   1. requestNonce(address)  -> server returns challenge message + nonce
 *   2. User signs message with wallet (MetaMask personal_sign)
 *   3. verifySignature(address, signature, nonce) -> JWT session token
 *   4. Token stored in localStorage; attached as Bearer header on requests.
 */

const AUTH_API = "/api/v1/auth";

class WalletAuth {
  constructor() {
    this.token = localStorage.getItem("biar_token") || null;
    this.address = localStorage.getItem("biar_address") || null;
    this.provider = null;
  }

  get isAuthenticated() {
    return Boolean(this.token && this.address);
  }

  /**
   * Connect MetaMask (or any EIP-1193 injected provider).
   */
  async connectWallet() {
    if (!window.ethereum) {
      throw new Error(
        "No Ethereum wallet detected. Please install MetaMask to sign in."
      );
    }
    this.provider = window.ethereum;
    const accounts = await this.provider.request({
      method: "eth_requestAccounts",
    });
    if (!accounts || accounts.length === 0) {
      throw new Error("No accounts authorized");
    }
    this.address = accounts[0];
    return this.address;
  }

  /**
   * Full sign-in flow: connect -> nonce -> sign -> verify -> store token.
   */
  async signIn() {
    const address = await this.connectWallet();

    // 1. Request challenge
    const res = await fetch(`${AUTH_API}/nonce`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address }),
    });
    if (!res.ok) throw new Error("Failed to request sign-in challenge");
    const { nonce, message } = await res.json();

    // 2. Sign challenge with wallet
    const signature = await this.provider.request({
      method: "personal_sign",
      params: [message, address],
    });

    // 3. Verify and obtain session token
    const verifyRes = await fetch(`${AUTH_API}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address, signature, nonce }),
    });
    if (!verifyRes.ok) {
      const err = await verifyRes.json().catch(() => ({}));
      throw new Error(err.detail || "Signature verification failed");
    }
    const { token, address: verified } = await verifyRes.json();

    // 4. Persist session
    this.token = token;
    this.address = verified;
    localStorage.setItem("biar_token", token);
    localStorage.setItem("biar_address", verified);

    return verified;
  }

  /**
   * Sign out: clear local session.
   */
  signOut() {
    this.token = null;
    this.address = null;
    localStorage.removeItem("biar_token");
    localStorage.removeItem("biar_address");
  }

  /**
   * Authenticated fetch wrapper: attaches Bearer token, handles 401s.
   */
  async apiFetch(url, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
      // Session expired -> clear and surface error
      this.signOut();
      throw new Error("Session expired. Please sign in again.");
    }
    return res;
  }

  /**
   * Fetch the current user's portfolio.
   */
  async getPortfolio() {
    const res = await this.apiFetch("/api/v1/portfolio");
    if (!res.ok) throw new Error("Failed to load portfolio");
    return res.json();
  }

  /**
   * Claim winnings for a resolved market.
   */
  async claimWinnings(marketId) {
    const res = await this.apiFetch(`/api/v1/markets/${marketId}/claim`, {
      method: "POST",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Claim failed");
    }
    return res.json();
  }

  /**
   * Place a limit order (requires auth).
   */
  async placeLimitOrder(marketId, { outcome_index, side, quantity, limit_price }) {
    const res = await this.apiFetch(`/api/v1/markets/${marketId}/limit-order`, {
      method: "POST",
      body: JSON.stringify({ outcome_index, side, quantity, limit_price }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Limit order failed");
    }
    return res.json();
  }

  /**
   * Cancel a limit order (requires auth).
   */
  async cancelLimitOrder(orderRef) {
    const res = await this.apiFetch(`/api/v1/limit-orders/${orderRef}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Cancel failed");
    return res.json();
  }
}

// Global singleton
window.walletAuth = new WalletAuth();

/**
 * UI: render the sign-in button / account chip into a container.
 */
function renderAuthUI(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const auth = window.walletAuth;

  if (auth.isAuthenticated) {
    const short = `${auth.address.slice(0, 6)}...${auth.address.slice(-4)}`;
    container.innerHTML = `
      <div class="flex items-center gap-2 bg-dark-800 border border-dark-600 rounded-lg px-3 py-1.5">
        <span class="w-2 h-2 bg-emerald-400 rounded-full"></span>
        <span class="text-sm text-gray-300 font-medium">${short}</span>
        <button id="portfolio-btn" class="text-xs text-emerald-400 hover:text-emerald-300 font-medium ml-1">Portfolio</button>
        <button id="signout-btn" class="text-xs text-gray-500 hover:text-gray-300 font-medium ml-1">Sign out</button>
      </div>`;
    document.getElementById("signout-btn").onclick = () => {
      auth.signOut();
      location.reload();
    };
    document.getElementById("portfolio-btn").onclick = () =>
      showPortfolio();
  } else {
    container.innerHTML = `
      <button id="signin-btn" class="gradient-bg px-4 py-2 rounded-lg text-sm font-semibold hover:opacity-90 transition">Connect Wallet</button>`;
    document.getElementById("signin-btn").onclick = async () => {
      try {
        await auth.signIn();
        renderAuthUI(containerId);
      } catch (e) {
        alert(e.message);
      }
    };
  }
}

/**
 * Portfolio modal: positions, PnL, claim buttons.
 */
async function showPortfolio() {
  const auth = window.walletAuth;
  let data;
  try {
    data = await auth.getPortfolio();
  } catch (e) {
    alert(e.message);
    return;
  }

  const rows = data.positions
    .map(
      (p) => `
      <tr>
        <td>${p.market_title}</td>
        <td>${p.outcome_name}</td>
        <td>${p.shares.toFixed(2)}</td>
        <td>$${p.cost_basis.toFixed(2)}</td>
        <td>$${p.value.toFixed(2)}</td>
        <td class="${p.unrealized_pnl >= 0 ? "pos" : "neg"}">
          ${p.unrealized_pnl >= 0 ? "+" : ""}$${p.unrealized_pnl.toFixed(2)}
        </td>
        ${
          p.claimable > 0
            ? `<td><button class="btn btn-sm btn-primary" onclick="claimWinnings(${p.market_id})">Claim $${p.claimable.toFixed(2)}</button></td>`
            : "<td></td>"
        }
      </tr>`
    )
    .join("");

  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal portfolio-modal">
      <div class="modal-header">
        <h2>Portfolio</h2>
        <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
      </div>
      <div class="portfolio-summary">
        <div><span>Total Value</span><strong>$${data.total_value.toFixed(2)}</strong></div>
        <div><span>Cost Basis</span><strong>$${data.total_cost_basis.toFixed(2)}</strong></div>
        <div><span>Unrealized PnL</span><strong class="${data.total_unrealized_pnl >= 0 ? "pos" : "neg"}">$${data.total_unrealized_pnl.toFixed(2)}</strong></div>
        <div><span>Realized PnL</span><strong class="${data.total_realized_pnl >= 0 ? "pos" : "neg"}">$${data.total_realized_pnl.toFixed(2)}</strong></div>
      </div>
      <table class="portfolio-table">
        <thead>
          <tr><th>Market</th><th>Outcome</th><th>Shares</th><th>Cost</th><th>Value</th><th>PnL</th><th></th></tr>
        </thead>
        <tbody>${rows || '<tr><td colspan="7">No positions yet</td></tr>'}</tbody>
      </table>
    </div>`;
  document.body.appendChild(modal);
}

async function claimWinnings(marketId) {
  try {
    const result = await window.walletAuth.claimWinnings(marketId);
    alert(`Claimed $${result.payout.toFixed(2)}`);
    document.querySelector(".modal-overlay")?.remove();
    showPortfolio();
  } catch (e) {
    alert(e.message);
  }
}

window.showPortfolio = showPortfolio;
window.claimWinnings = claimWinnings;
window.renderAuthUI = renderAuthUI;