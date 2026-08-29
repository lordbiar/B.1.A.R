/**
 * BIAR Protocol - Main application logic.
 * Security: all user-controlled data rendered via textContent (XSS-safe),
 * order inputs validated client-side before submission.
 */

const AppState = {
  markets: [],
  walletAddress: null,
  currentMarketId: null,
};

// ---------- helpers ----------

function formatMoney(n) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${Number(n).toFixed(2)}`;
}

function showToast(message, isError = false) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'fixed bottom-6 right-6 z-[100] px-4 py-3 rounded-lg shadow-lg transition-opacity duration-300';
    document.body.appendChild(toast);
  }
  toast.textContent = message; // XSS-safe
  toast.style.background = isError ? '#dc2626' : '#1e293b';
  toast.style.border = isError ? '1px solid #ef4444' : '1px solid #6366f1';
  toast.style.opacity = '1';
  setTimeout(() => { toast.style.opacity = '0'; }, 3500);
}

// ---------- market rendering ----------

function renderMarkets() {
  const grid = document.getElementById('marketsGrid');
  if (!grid) return;
  grid.textContent = '';

  if (!AppState.markets.length) {
    const empty = document.createElement('p');
    empty.className = 'text-gray-400 col-span-full text-center py-12';
    empty.textContent = 'No active markets yet. Create the first one!';
    grid.appendChild(empty);
    return;
  }

  AppState.markets.forEach((m) => {
    const card = document.createElement('div');
    card.className = 'bg-dark-800 rounded-xl p-6 card-hover transition-all duration-300 cursor-pointer market-card-gradient';
    card.addEventListener('click', () => openOrderModal(m.id));

    const title = document.createElement('h3');
    title.className = 'font-semibold text-lg mb-2 line-clamp-2';
    title.textContent = m.title; // XSS-safe

    const category = document.createElement('span');
    category.className = 'inline-block text-xs px-2 py-1 rounded bg-dark-700 text-gray-300 mb-4';
    category.textContent = m.category;

    const outcomesWrap = document.createElement('div');
    m.outcomes.forEach((name, i) => {
      const price = m.prices[i] ?? 0;
      const pct = Math.round(price * 100);

      const row = document.createElement('div');
      row.className = 'mb-3';

      const labelRow = document.createElement('div');
      labelRow.className = 'flex justify-between text-sm mb-1';

      const nameSpan = document.createElement('span');
      nameSpan.textContent = name;
      const priceSpan = document.createElement('span');
      priceSpan.className = 'font-semibold number-transition';
      priceSpan.textContent = `${pct}%`;
      priceSpan.dataset.outcome = `${m.id}-${i}`;

      labelRow.appendChild(nameSpan);
      labelRow.appendChild(priceSpan);

      const barOuter = document.createElement('div');
      barOuter.className = 'h-2 bg-dark-700 rounded-full overflow-hidden';
      const bar = document.createElement('div');
      bar.className = 'h-full gradient-bg outcome-bar rounded-full';
      bar.style.width = `${pct}%`;
      bar.dataset.bar = `${m.id}-${i}`;
      barOuter.appendChild(bar);

      row.appendChild(labelRow);
      row.appendChild(barOuter);
      outcomesWrap.appendChild(row);
    });

    const volume = document.createElement('p');
    volume.className = 'text-xs text-gray-400 mt-2';
    volume.textContent = `Volume: ${formatMoney(m.total_volume)}`;

    card.appendChild(title);
    card.appendChild(category);
    card.appendChild(outcomesWrap);
    card.appendChild(volume);
    grid.appendChild(card);
  });
}

async function loadMarkets() {
  try {
    const category = document.getElementById('categoryFilter')?.value || '';
    AppState.markets = await ApiClient.getMarkets(category);
    renderMarkets();
  } catch (e) {
    showToast(`Failed to load markets: ${e.message}`, true);
  }
}

async function loadStats() {
  try {
    const stats = await ApiClient.getStats();
    setText('activeMarkets', String(stats.active_markets));
    setText('totalVolume', formatMoney(stats.total_volume));
    setText('totalTrades', String(stats.total_trades));
  } catch (e) {
    /* stats are non-critical */
  }
}

// ---------- order modal ----------

function openOrderModal(marketId) {
  const market = AppState.markets.find((m) => m.id === marketId);
  if (!market) return;
  AppState.currentMarketId = marketId;

  setText('modalMarketTitle', market.title);

  const select = document.getElementById('outcomeSelect');
  select.textContent = '';
  market.outcomes.forEach((name, i) => {
    const opt = document.createElement('option');
    opt.value = String(i);
    opt.textContent = `${name} — ${Math.round((market.prices[i] ?? 0) * 100)}%`;
    select.appendChild(opt);
  });

  document.getElementById('orderModal').classList.remove('hidden');
  updateOrderEstimate();
}

function closeOrderModal() {
  document.getElementById('orderModal').classList.add('hidden');
  AppState.currentMarketId = null;
}

function updateOrderEstimate() {
  const market = AppState.markets.find((m) => m.id === AppState.currentMarketId);
  if (!market) return;
  const outcomeIdx = parseInt(document.getElementById('outcomeSelect').value, 10);
  const shares = parseFloat(document.getElementById('orderAmount').value) || 0;

  if (shares <= 0) {
    setText('estShares', '--');
    setText('currentPrice', '--');
    setText('slippageEst', '--');
    return;
  }

  const price = market.prices[outcomeIdx] ?? 0;
  setText('currentPrice', `${Math.round(price * 100)}¢`);
  setText('estShares', shares.toFixed(2));

  // Rough slippage estimate: grows with size relative to liquidity
  const slip = Math.min((shares / (market.liquidity_b * 10)) * 100, 25);
  const slipEl = document.getElementById('slippageEst');
  slipEl.textContent = `~${slip.toFixed(2)}%`;
  slipEl.className = slip > 10 ? 'text-red-400' : slip > 3 ? 'text-yellow-400' : 'text-green-400';
}

async function submitOrder() {
  const market = AppState.markets.find((m) => m.id === AppState.currentMarketId);
  if (!market) return;

  const outcomeIndex = parseInt(document.getElementById('outcomeSelect').value, 10);
  const shares = parseFloat(document.getElementById('orderAmount').value);

  // Client-side validation mirrors backend rules
  if (!Number.isFinite(shares) || shares <= 0) {
    showToast('Enter a valid share amount', true);
    return;
  }
  if (shares > 100000) {
    showToast('Amount exceeds maximum trade size', true);
    return;
  }

  const btn = document.querySelector('#orderModal button[onclick="submitOrder()"]');
  btn.disabled = true;
  btn.textContent = 'Submitting...';

  try {
    const trade = await ApiClient.placeOrder(AppState.currentMarketId, {
      trader: AppState.walletAddress || 'anonymous',
      outcome_index: outcomeIndex,
      side: 'buy',
      shares,
      max_slippage: 0.25,
    });
    showToast(`Order filled: ${trade.shares} shares @ ${(trade.price * 100).toFixed(1)}¢`);
    closeOrderModal();
    await loadMarkets();
  } catch (e) {
    showToast(e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Confirm Order';
  }
}

// ---------- wallet ----------

async function connectWallet() {
  if (typeof window.ethereum === 'undefined') {
    showToast('MetaMask not detected. Trading as guest.', true);
    return;
  }
  try {
    const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
    AppState.walletAddress = accounts[0];
    setText('connectWallet', `${AppState.walletAddress.slice(0, 6)}...${AppState.walletAddress.slice(-4)}`);
    showToast('Wallet connected');
  } catch (e) {
    showToast('Wallet connection rejected', true);
  }
}

// ---------- init ----------

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('connectWallet')?.addEventListener('click', connectWallet);
  document.getElementById('connectWalletMobile')?.addEventListener('click', connectWallet);
  document.getElementById('categoryFilter')?.addEventListener('change', loadMarkets);
  document.getElementById('orderAmount')?.addEventListener('input', updateOrderEstimate);
  document.getElementById('outcomeSelect')?.addEventListener('change', updateOrderEstimate);

  // Mobile menu toggle
  document.getElementById('mobileMenuBtn')?.addEventListener('click', () => {
    document.getElementById('mobileMenu')?.classList.toggle('hidden');
  });

  loadMarkets();
  loadStats();
  wsClient.connectToFeed();

  // Real-time updates via WebSocket
  wsClient.subscribe('*', (data) => {
    if (data.type === 'prices' && data.prices) {
      const market = AppState.markets.find((m) => m.id === data.market_id);
      if (market) {
        market.prices = data.prices;
        data.prices.forEach((p, i) => {
          const pct = Math.round(p * 100);
          const el = document.querySelector(`[data-outcome="${data.market_id}-${i}"]`);
          const bar = document.querySelector(`[data-bar="${data.market_id}-${i}"]`);
          if (el) el.textContent = `${pct}%`;
          if (bar) bar.style.width = `${pct}%`;
        });
      }
    }
    if (data.type === 'trade') {
      loadStats();
    }
  });

  // Periodic stats refresh
  setInterval(loadStats, 15000);
});