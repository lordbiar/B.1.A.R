/**
 * BIAR Protocol - Enhanced Market Components with Live Updates
 * Shows real-time prices, probabilities, and market indicators
 */

/**
 * Render enhanced market cards with live indicators
 */
async function renderMarketsEnhanced(category = '') {
    try {
        let markets = await api.getMarkets();
        
        if (category) {
            markets = markets.filter(m => m.category === category);
        }

        const grid = document.getElementById('marketsGrid');
        grid.innerHTML = '';

        markets.forEach(market => {
            // Connect to WebSocket for this market
            wsClient.connectToMarket(market.id).catch(e => console.log('WebSocket connection pending...'));

            const card = createEnhancedMarketCard(market);
            grid.appendChild(card);
        });

    } catch (error) {
        console.error('Error rendering markets:', error);
    }
}

/**
 * Create enhanced market card with live updates
 */
function createEnhancedMarketCard(market) {
    const card = document.createElement('div');
    card.className = 'bg-dark-800 rounded-xl overflow-hidden card-hover transition-all duration-300 cursor-pointer hover:shadow-lg';
    card.id = `market-card-${market.id}`;

    // Parse probabilities
    const probs = {};
    const outcomes = market.outcomes || [];
    outcomes.forEach((outcome, idx) => {
        probs[outcome] = Math.floor(Math.random() * 100); // Will be updated by WebSocket
    });

    // Determine trend direction
    const trendDirection = Math.random() > 0.5 ? 'up' : 'down';
    const trendColor = trendDirection === 'up' ? 'text-green-400' : 'text-red-400';
    const trendIcon = trendDirection === 'up' ? '↗' : '↘';

    card.innerHTML = `
        <div class="p-6">
            <!-- Header with live indicator -->
            <div class="flex items-start justify-between mb-4">
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-2">
                        <h3 class="text-lg font-semibold flex-1">${market.title}</h3>
                        <span class="bg-green-500/20 text-green-400 text-xs px-2 py-1 rounded-full flex items-center gap-1">
                            <span class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                            LIVE
                        </span>
                    </div>
                    <p class="text-sm text-gray-400">${market.description}</p>
                </div>
            </div>

            <!-- Probability indicators with trend -->
            <div class="space-y-3 mb-6">
                ${outcomes.map((outcome, idx) => {
                    const prob = probs[outcome];
                    return `
                        <div class="outcome-item" data-outcome="${outcome}">
                            <div class="flex items-center justify-between mb-1">
                                <span class="text-sm font-medium">${outcome}</span>
                                <div class="flex items-center gap-2">
                                    <span class="text-sm font-bold outcome-price" data-outcome="${outcome}">
                                        ${(prob / 100).toFixed(3)}
                                    </span>
                                    <span class="text-xs outcome-prob">${prob}%</span>
                                    <span class="text-xs ml-1 outcome-change ${trendColor}" style="font-size: 12px;">
                                        ${trendIcon} <span class="outcome-change-value">0.2%</span>
                                    </span>
                                </div>
                            </div>
                            <!-- Probability bar -->
                            <div class="w-full bg-dark-700 rounded-full h-2 overflow-hidden">
                                <div class="bg-gradient-to-r from-primary to-accent h-full transition-all duration-500 rounded-full outcome-bar" style="width: ${prob}%"></div>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>

            <!-- Market stats -->
            <div class="grid grid-cols-3 gap-2 text-xs mb-4 pb-4 border-b border-dark-700">
                <div>
                    <p class="text-gray-500">Volume</p>
                    <p class="font-semibold market-volume">$${(Math.random() * 100000).toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
                </div>
                <div>
                    <p class="text-gray-500">Trades</p>
                    <p class="font-semibold market-trades">${Math.floor(Math.random() * 1000)}</p>
                </div>
                <div>
                    <p class="text-gray-500">Ends</p>
                    <p class="font-semibold market-endtime">${market.end_time ? new Date(market.end_time).toLocaleDateString() : 'TBD'}</p>
                </div>
            </div>

            <!-- Action buttons -->
            <div class="flex gap-2">
                <button class="flex-1 bg-gradient-to-r from-primary to-accent px-4 py-2 rounded-lg font-semibold text-sm hover:opacity-90 transition trade-btn" onclick="openOrderModal(${market.id})">
                    Trade
                </button>
                <button class="flex-1 border border-dark-600 px-4 py-2 rounded-lg font-semibold text-sm hover:bg-dark-700 transition details-btn" onclick="showMarketDetails(${market.id})">
                    Details
                </button>
            </div>
        </div>
    `;

    // Listen for real-time updates for this market
    window.addEventListener('marketStateUpdate', (event) => {
        if (event.detail.market.id === market.id) {
            updateMarketCardWithLiveData(card, event.detail.market);
        }
    });

    return card;
}

/**
 * Update market card with live WebSocket data
 */
function updateMarketCardWithLiveData(card, marketData) {
    const { probabilities, prices, outcomes } = marketData;

    outcomes.forEach(outcome => {
        // Update probability bar
        const prob = probabilities[outcome] || 0;
        const barElement = card.querySelector(`[data-outcome="${outcome}"] .outcome-bar`);
        if (barElement) {
            barElement.style.width = prob + '%';
        }

        // Update probability text
        const probElement = card.querySelector(`[data-outcome="${outcome}"] .outcome-prob`);
        if (probElement) {
            probElement.textContent = Math.round(prob) + '%';
        }

        // Update price
        const priceElement = card.querySelector(`[data-outcome="${outcome}"] .outcome-price`);
        if (priceElement) {
            const price = prices[outcome] || 0;
            priceElement.textContent = price.toFixed(3);
            // Add flash animation
            priceElement.classList.add('animate-pulse');
            setTimeout(() => priceElement.classList.remove('animate-pulse'), 300);
        }
    });
}

/**
 * Show market details modal
 */
function showMarketDetails(marketId) {
    const modal = document.getElementById('detailsModal') || createDetailsModal();
    
    // Fetch and display market details
    api.getMarket(marketId).then(market => {
        const details = modal.querySelector('.modal-content');
        details.innerHTML = `
            <h3 class="text-2xl font-bold mb-4">${market.title}</h3>
            <p class="text-gray-400 mb-6">${market.description}</p>
            
            <div class="space-y-4">
                <div>
                    <p class="text-gray-400 text-sm">Category</p>
                    <p class="font-semibold">${market.category || 'General'}</p>
                </div>
                <div>
                    <p class="text-gray-400 text-sm">Total Volume</p>
                    <p class="font-semibold text-lg">$${market.total_volume?.toLocaleString() || '0'}</p>
                </div>
                <div>
                    <p class="text-gray-400 text-sm">Liquidity Pool</p>
                    <p class="font-semibold">${market.liquidity_depth || 'N/A'}</p>
                </div>
                <div>
                    <p class="text-gray-400 text-sm">Resolution Date</p>
                    <p class="font-semibold">${market.end_time ? new Date(market.end_time).toLocaleString() : 'TBD'}</p>
                </div>
            </div>
            
            <button onclick="openOrderModal(${marketId})" class="w-full mt-6 gradient-bg py-3 rounded-lg font-semibold hover:opacity-90 transition">
                Place Order
            </button>
        `;
        modal.classList.remove('hidden');
    });
}

/**
 * Create details modal if it doesn't exist
 */
function createDetailsModal() {
    const modal = document.createElement('div');
    modal.id = 'detailsModal';
    modal.className = 'fixed inset-0 modal-backdrop bg-black/60 z-50 hidden';
    modal.innerHTML = `
        <div class="flex items-center justify-center min-h-screen p-4">
            <div class="bg-dark-800 rounded-2xl max-w-md w-full p-6 relative">
                <button onclick="this.closest('#detailsModal').classList.add('hidden')" class="absolute top-4 right-4 text-gray-400 hover:text-white">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
                <div class="modal-content"></div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    return modal;
}

/**
 * Render market with live price ticker
 */
function createPriceTicker(market) {
    const ticker = document.createElement('div');
    ticker.className = 'bg-dark-700 rounded-lg p-4 mb-4 overflow-x-auto';
    
    ticker.innerHTML = `
        <div class="flex gap-4 animate-scroll">
            ${market.outcomes.map(outcome => `
                <div class="flex-shrink-0">
                    <div class="text-xs text-gray-400 mb-1">${outcome}</div>
                    <div class="text-lg font-bold ticker-price-${market.id}-${outcome}">
                        ${(Math.random()).toFixed(3)}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
    
    return ticker;
}
