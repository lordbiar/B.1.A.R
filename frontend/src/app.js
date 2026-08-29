/**
 * BIAR Protocol - Main application logic.
 * Security: all user-controlled data rendered via textContent (XSS-safe),
 * order inputs validated client-side before submission.
 */

const AppState = {
  markets: [],
  walletAddress: null,
  currentMarketId: null,
  activeCategory: '',
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

function formatCountdown(endTime) {
  if (!endTime) return '—';
  const end = new Date(endTime);
  const now = new Date();
  const diff = end - now;
  if (diff <= 0) return 'Ended';
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function isUrgent(endTime) {
  if (!endTime) return false;
  const diff = new Date(endTime) - new Date();
  return diff > 0 && diff < 6 * 3600000; // less than 6 hours
}

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
    card.className = 'bg-dark-800 rounded-xl p-5 card-hover transition-all duration-300 market-card-gradient border border-dark-700';

    // Header: category + countdown
    const header = document.createElement('div');
    header.className = 'flex items-center justify-between mb-3';
    const category = document.createElement('span');
    category.className = 'text-xs px-2 py-1 rounded bg-dark-700 text-gray-300 capitalize';
    category.textContent = m.category;
    const countdown = document.createElement('span');
    const urgent = isUrgent(m.end_time);
    countdown.className = `countdown-badge ${urgent ? 'countdown-urgent' : 'countdown-normal'}`;
    countdown.textContent = '⏱ ' + formatCountdown(m.end_time);
    header.appendChild(category);
    header.appendChild(countdown);

    // Title
    const title = document.createElement('h3');
    title.className = 'font-semibold text-base mb-3 line-clamp-2 leading-snug';
    title.textContent = m.title; // XSS-safe

    // YES/NO price buttons (Polymarket-style)
    const outcomesWrap = document.createElement('div');
    outcomesWrap.className = 'space-y-2 mb-3';
    m.outcomes.forEach((name, i) => {
      const price = m.prices[i] ?? 0;
      const pct = Math.round(price * 100);
      const isYes = name.toLowerCase() === 'yes' || i === 0;

      const btn = document.createElement('div');
      btn.className = `outcome-btn ${isYes ? 'outcome-btn-yes' : 'outcome-btn-no'}`;
      btn.innerHTML = '';
      const nameSpan = document.createElement('span');
      nameSpan.textContent = name;
      const priceSpan = document.createElement('span');
      priceSpan.textContent = `${pct}¢`;
      btn.appendChild(nameSpan);
      btn.appendChild(priceSpan);
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        openOrderModal(m.id, i);
      });
      outcomesWrap.appendChild(btn);
    });

    // Footer: volume + liquidity
    const footer = document.createElement('div');
    footer.className = 'flex items-center justify-between text-xs text-gray-400 pt-3 border-t border-dark-700';
    const volSpan = document.createElement('span');
    volSpan.textContent = `Vol: ${formatMoney(m.total_volume)}`;
    const liqSpan = document.createElement('span');
    liqSpan.textContent = `Liq: ${formatMoney(m.liquidity_b || 200)}`;
    footer.appendChild(volSpan);
    footer.appendChild(liqSpan);

    card.appendChild(header);
    card.appendChild(title);
    card.appendChild(outcomesWrap);
    card.appendChild(footer);
    card.addEventListener('click', () => openOrderModal(m.id));
    grid.appendChild(card);
  });
}

function renderFeaturedMarket() {
  const container = document.getElementById('featuredMarket');
  if (!container || !AppState.markets.length) return;

  // Pick the market with highest volume as featured
  const featured = [...AppState.markets].sort((a, b) => b.total_volume - a.total_volume)[0];
  if (!featured) return;

  setText('featuredTitle', featured.title);
  setText('featuredDesc', featured.description || '');
  setText('featuredVolume', formatMoney(featured.total_volume));
  setText('featuredEndsIn', formatCountdown(featured.end_time));

  const outcomesEl = document.getElementById('featuredOutcomes');
  if (outcomesEl) {
    outcomesEl.textContent = '';
    featured.outcomes.forEach((name, i) => {
      const price = featured.prices[i] ?? 0;
      const pct = Math.round(price * 100);
      const isYes = name.toLowerCase() === 'yes' || i === 0;

      const btn = document.createElement('div');
      btn.className = `outcome-btn ${isYes ? 'outcome-btn-yes' : 'outcome-btn-no'}`;
      const nameSpan = document.createElement('span');
      nameSpan.textContent = name;
      const priceSpan = document.createElement('span');
      priceSpan.textContent = `${pct}¢`;
      btn.appendChild(nameSpan);
      btn.appendChild(priceSpan);
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        openOrderModal(featured.id, i);
      });
      outcomesEl.appendChild(btn);
    });
  }
}

async function loadMarkets() {
  try {
    const res = await ApiClient.getMarkets(AppState.activeCategory);
    // API now returns a paginated envelope { items, total, page, ... }
    AppState.markets = Array.isArray(res) ? res : res.items;
    renderMarkets();
    renderFeaturedMarket();
  } catch (e) {
    showToast(`Failed to load markets: ${e.message}`, true);
  }
}

function initCategoryTabs() {
  const tabs = document.querySelectorAll('.category-tab');
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      tabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      AppState.activeCategory = tab.dataset.category || '';
      loadMarkets();
    });
  });
}

async function loadStats() {
  try {
    const stats = await ApiClient.getStats();
    setText('activeMarkets', String(stats.active_markets));
    setText('totalVolume', formatMoney(stats.total_volume));
    setText('totalTrades', String(stats.total_trades));
    // Also update the ticker bar
    setText('tickerVolume', formatMoney(stats.total_volume));
    setText('tickerActive', String(stats.active_markets));
    setText('tickerTrades', String(stats.total_trades));
  } catch (e) {
    /* stats are non-critical */
  }
}

// ---------- order modal ----------

function openOrderModal(marketId, preselectOutcome) {
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

  // Pre-select outcome if clicked from a YES/NO button
  if (preselectOutcome !== undefined) {
    select.value = String(preselectOutcome);
  }

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
    }, window.walletAuth?.token);
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

// ---------- wallet (SIWE-style auth via components/auth.js) ----------

function initAuthUI() {
  const auth = window.walletAuth;
  AppState.walletAddress = auth.isAuthenticated ? auth.address : null;
  renderAuthUI('authContainer');
  renderAuthUI('authContainerMobile');
}

// ---------- init ----------

document.addEventListener('DOMContentLoaded', () => {
  initAuthUI();
  initCategoryTabs();
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