/**
 * BIAR Protocol - Market Components
 * Functions for rendering and interacting with markets
 */

// Sample market data for demo (when API is not available)
const sampleMarkets = [
    {
        id: 1,
        title: "Will Bitcoin reach $100K by end of 2024?",
        description: "Predict whether BTC will hit the six-figure milestone before December 31, 2024.",
        category: "crypto",
        outcomes: ["YES", "NO"],
        status: "active",
        end_time: "2024-12-31T23:59:59Z",
        total_volume: 125000,
        probabilities: { YES: 0.62, NO: 0.38 }
    },
    {
        id: 2,
        title: "Fed Interest Rate Decision - March 2024",
        description: "What will the Federal Reserve decide on interest rates at the March meeting?",
        category: "finance",
        outcomes: ["Hold", "Raise", "Cut"],
        status: "active",
        end_time: "2024-03-20T19:00:00Z",
        total_volume: 89000,
        probabilities: { Hold: 0.75, Raise: 0.10, Cut: 0.15 }
    },
    {
        id: 3,
        title: "Super Bowl 2024 Winner",
        description: "Which team will win Super Bowl LVIII?",
        category: "sports",
        outcomes: ["Chiefs", "49ers", "Ravens", "Other"],
        status: "active",
        end_time: "2024-02-11T23:30:00Z",
        total_volume: 250000,
        probabilities: { Chiefs: 0.35, "49ers": 0.30, Ravens: 0.20, Other: 0.15 }
    }
];

let currentMarket = null;

/**
 * Render market cards to the grid
 */
async function renderMarkets(categoryFilter = '') {
    const grid = document.getElementById('marketsGrid');
    if (!grid) return;

    let markets = [];
    
    try {
        markets = await api.getMarkets({ category: categoryFilter || undefined });
    } catch (error) {
        console.log('Using sample data (API not available)');
        markets = sampleMarkets.filter(m => !categoryFilter || m.category === categoryFilter);
    }

    if (markets.length === 0) {
        grid.innerHTML = `
            <div class="col-span-full text-center py-12">
                <p class="text-gray-400 text-lg">No active markets found</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = markets.map(market => `
        <div class="bg-dark-800 rounded-xl p-6 card-hover transition-all duration-300 border border-dark-700">
            <div class="flex items-start justify-between mb-4">
                <span class="px-3 py-1 bg-primary/20 text-primary text-sm rounded-full capitalize">${market.category}</span>
                <span class="text-green-400 text-sm flex items-center gap-1">
                    <span class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                    Active
                </span>
            </div>
            
            <h3 class="text-xl font-bold mb-2 line-clamp-2">${market.title}</h3>
            <p class="text-gray-400 text-sm mb-4 line-clamp-2">${market.description || ''}</p>
            
            <div class="mb-4">
                <p class="text-xs text-gray-500 mb-2">Current Probabilities</p>
                <div class="space-y-2">
                    ${renderProbabilityBars(market.outcomes, market.probabilities)}
                </div>
            </div>
            
            <div class="flex items-center justify-between pt-4 border-t border-dark-700">
                <div>
                    <p class="text-xs text-gray-500">Volume</p>
                    <p class="font-semibold">$${formatNumber(market.total_volume)}</p>
                </div>
                <div>
                    <p class="text-xs text-gray-500">Ends In</p>
                    <p class="font-semibold">${formatTimeRemaining(market.end_time)}</p>
                </div>
            </div>
            
            <button onclick="openOrderModal(${market.id})" 
                class="w-full mt-4 gradient-bg py-3 rounded-lg font-semibold hover:opacity-90 transition">
                Trade
            </button>
        </div>
    `).join('');
}

/**
 * Render probability bars for outcomes
 */
function renderProbabilityBars(outcomes, probabilities) {
    if (!probabilities) {
        return outcomes.map(outcome => `
            <div class="flex items-center gap-2">
                <span class="text-sm w-16">${outcome}</span>
                <div class="flex-1 bg-dark-700 rounded-full h-2">
                    <div class="gradient-bg h-2 rounded-full" style="width: 50%"></div>
                </div>
                <span class="text-sm">50%</span>
            </div>
        `).join('');
    }

    return Object.entries(probabilities).map(([outcome, prob]) => `
        <div class="flex items-center gap-2">
            <span class="text-sm w-16">${outcome}</span>
            <div class="flex-1 bg-dark-700 rounded-full h-2">
                <div class="gradient-bg h-2 rounded-full" style="width: ${prob * 100}%"></div>
            </div>
            <span class="text-sm">${(prob * 100).toFixed(1)}%</span>
        </div>
    `).join('');
}

/**
 * Open order modal for a market
 */
async function openOrderModal(marketId) {
    try {
        currentMarket = await api.getMarket(marketId);
    } catch (error) {
        currentMarket = sampleMarkets.find(m => m.id === marketId);
    }

    if (!currentMarket) return;

    const modal = document.getElementById('orderModal');
    const titleEl = document.getElementById('modalMarketTitle');
    const outcomeSelect = document.getElementById('outcomeSelect');

    titleEl.textContent = currentMarket.title;
    
    outcomeSelect.innerHTML = currentMarket.outcomes.map(outcome => `
        <option value="${outcome}">${outcome}</option>
    `).join('');

    modal.classList.remove('hidden');

    // Update estimates when inputs change
    updateOrderEstimates();
}

/**
 * Close order modal
 */
function closeOrderModal() {
    const modal = document.getElementById('orderModal');
    modal.classList.add('hidden');
    currentMarket = null;
}

/**
 * Update order estimate calculations
 */
async function updateOrderEstimates() {
    if (!currentMarket) return;

    const amount = parseFloat(document.getElementById('orderAmount').value) || 0;
    const outcome = document.getElementById('outcomeSelect').value;

    if (amount <= 0 || !currentMarket) {
        document.getElementById('estShares').textContent = '--';
        document.getElementById('currentPrice').textContent = '--';
        document.getElementById('slippageEst').textContent = '--';
        return;
    }

    try {
        const sim = await api.simulateSlippage(currentMarket.id, outcome, amount);
        
        document.getElementById('estShares').textContent = sim.shares_received.toFixed(4);
        document.getElementById('currentPrice').textContent = `$${sim.effective_price.toFixed(4)}`;
        document.getElementById('slippageEst').textContent = `${sim.slippage_percentage.toFixed(2)}%`;
        
        // Color code slippage
        const slippageEl = document.getElementById('slippageEst');
        if (sim.slippage_percentage > 5) {
            slippageEl.className = 'text-red-400';
        } else if (sim.slippage_percentage > 2) {
            slippageEl.className = 'text-yellow-400';
        } else {
            slippageEl.className = 'text-green-400';
        }
    } catch (error) {
        // Fallback calculation
        const price = currentMarket.probabilities?.[outcome] || 0.5;
        const shares = amount / price;
        document.getElementById('estShares').textContent = shares.toFixed(4);
        document.getElementById('currentPrice').textContent = `$${price.toFixed(4)}`;
        document.getElementById('slippageEst').textContent = '~1.00%';
    }
}

/**
 * Submit an order
 */
async function submitOrder() {
    if (!currentMarket) return;

    const amount = parseFloat(document.getElementById('orderAmount').value);
    const outcome = document.getElementById('outcomeSelect').value;
    const userAddress = localStorage.getItem('walletAddress') || '0x' + '1'.repeat(40);

    if (!amount || amount <= 0) {
        alert('Please enter a valid amount');
        return;
    }

    try {
        const result = await api.placeOrder(currentMarket.id, {
            user_address: userAddress,
            outcome,
            side: 'buy',
            amount,
            slippage_tolerance: 0.05
        });

        alert(`Order executed! Received ${result.shares_received.toFixed(4)} ${outcome} shares`);
        closeOrderModal();
        renderMarkets();
    } catch (error) {
        alert(error.message || 'Order failed');
    }
}

/**
 * Format number with commas
 */
function formatNumber(num) {
    return num.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

/**
 * Format time remaining
 */
function formatTimeRemaining(endTime) {
    const end = new Date(endTime);
    const now = new Date();
    const diff = end - now;

    if (diff <= 0) return 'Ended';

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

    if (days > 0) return `${days}d ${hours}h`;
    return `${hours}h`;
}

// Note: market rendering is handled by app.js (loadMarkets/renderMarkets).
// This file provides helper functions (formatNumber, formatTimeRemaining, etc.)
// and the legacy renderMarkets() for backward compatibility.
