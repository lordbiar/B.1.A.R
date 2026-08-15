/**
 * BIAR Protocol - Main Application with Real-Time Updates
 * Initializes the dashboard with WebSocket-powered live data
 */

// Global state
const AppState = {
    walletConnected: false,
    walletAddress: null,
    currentMarket: null,
    markets: [],
    wsConnected: false,
    portfolioValue: 0
};

/**
 * Initialize the application
 */
async function initApp() {
    console.log('🚀 BIAR Protocol Dashboard initializing...');
    
    // Load saved wallet
    const savedWallet = localStorage.getItem('walletAddress');
    if (savedWallet) {
        AppState.walletAddress = savedWallet;
        AppState.walletConnected = true;
        updateConnectButton();
    }
    
    // Initialize components
    await loadStats();
    await renderMarketsEnhanced();
    
    // Connect WebSocket for real-time updates
    await initializeWebSocket();
    
    // Setup event listeners
    setupEventListeners();
    
    console.log('✅ Dashboard initialized successfully with live updates');
}

/**
 * Initialize WebSocket connections
 */
async function initializeWebSocket() {
    try {
        // Connect to global market feed for all market updates
        await wsClient.connectToFeed();
        AppState.wsConnected = true;
        console.log('✓ WebSocket connected for live market feed');
        
        // If wallet is connected, also connect to user portfolio
        if (AppState.walletConnected && AppState.walletAddress) {
            await wsClient.connectToUserPortfolio(AppState.walletAddress);
            console.log('✓ User portfolio WebSocket connected');
        }
    } catch (error) {
        console.warn('WebSocket connection failed, will retry:', error);
        // Retry after delay
        setTimeout(initializeWebSocket, 5000);
    }
}

/**
 * Load platform statistics
 */
async function loadStats() {
    try {
        const stats = await api.getStats();
        
        document.getElementById('activeMarkets').textContent = stats.active_markets || '--';
        document.getElementById('totalVolume').textContent = `$${(stats.total_volume || 0).toLocaleString()}`;
        document.getElementById('totalTrades').textContent = Math.floor((stats.total_volume || 0) / 100);
        
        if (AppState.walletConnected && AppState.walletAddress) {
            try {
                const positions = await api.getUserPositions(AppState.walletAddress);
                const portfolioValue = positions.reduce((sum, pos) => sum + (pos.shares * pos.average_cost), 0);
                AppState.portfolioValue = portfolioValue;
                document.getElementById('portfolioValue').textContent = `$${portfolioValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
            } catch (e) {
                document.getElementById('portfolioValue').textContent = '$0';
            }
        }
    } catch (error) {
        console.log('Stats not available, using defaults');
        document.getElementById('activeMarkets').textContent = '3';
        document.getElementById('totalVolume').textContent = '$464,000';
        document.getElementById('totalTrades').textContent = '4,640';
    }
}

/**
 * Setup global event listeners
 */
function setupEventListeners() {
    // Wallet connect buttons
    const connectBtn = document.getElementById('connectWallet');
    const connectBtnMobile = document.getElementById('connectWalletMobile');
    if (connectBtn) connectBtn.addEventListener('click', handleWalletConnect);
    if (connectBtnMobile) connectBtnMobile.addEventListener('click', handleWalletConnect);
    
    // Mobile menu toggle
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const mobileMenu = document.getElementById('mobileMenu');
    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenu.classList.toggle('hidden');
        });
    }
    
    // Update WebSocket status indicator
    const wsStatus = document.getElementById('wsStatus');
    const updateWSStatus = (connected) => {
        if (wsStatus) {
            if (connected) {
                wsStatus.innerHTML = '<span class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span><span class="text-green-400">Live</span>';
            } else {
                wsStatus.innerHTML = '<span class="w-2 h-2 bg-yellow-400 rounded-full"></span><span class="text-yellow-400">Connecting...</span>';
            }
        }
    };
    
    // Listen for market state updates (indicates WebSocket is working)
    window.addEventListener('marketStateUpdate', () => {
        updateWSStatus(true);
    });
    
    // Listen for real-time probability updates
    window.addEventListener('probabilityUpdate', (event) => {
        console.log('📊 Probability updated:', event.detail);
        // Update UI elements with new probabilities
    });
    
    // Listen for real-time price updates
    window.addEventListener('priceUpdate', (event) => {
        console.log('💹 Price tick:', event.detail.market_id, event.detail.prices);
    });
    
    // Listen for portfolio updates
    window.addEventListener('portfolioUpdate', (event) => {
        console.log('💼 Portfolio updated:', event.detail);
        updatePortfolioDisplay(event.detail.portfolio);
    });
    
    // Listen for notifications
    window.addEventListener('notification', (event) => {
        showNotification(event.detail.message, event.detail.type);
    });
    
    // Handle category filter
    const categoryFilter = document.getElementById('categoryFilter');
    if (categoryFilter) {
        categoryFilter.addEventListener('change', async (e) => {
            await renderMarketsEnhanced(e.target.value);
        });
    }
}

/**
 * Update portfolio display with real-time data
 */
function updatePortfolioDisplay(portfolio) {
    if (portfolio && portfolio.positions) {
        const totalValue = portfolio.positions.reduce((sum, pos) => sum + pos.current_value, 0);
        AppState.portfolioValue = totalValue;
        const portfolioElement = document.getElementById('portfolioValue');
        if (portfolioElement) {
            portfolioElement.textContent = `$${totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
            portfolioElement.classList.add('animate-pulse');
            setTimeout(() => portfolioElement.classList.remove('animate-pulse'), 500);
        }
    }
}

/**
 * Show notification to user
 */
function showNotification(message, type = 'info') {
    const notificationDiv = document.createElement('div');
    notificationDiv.className = `fixed top-4 right-4 px-6 py-3 rounded-lg text-white z-50 ${
        type === 'success' ? 'bg-green-500' :
        type === 'error' ? 'bg-red-500' :
        type === 'warning' ? 'bg-yellow-500' :
        'bg-blue-500'
    }`;
    notificationDiv.textContent = message;
    document.body.appendChild(notificationDiv);
    
    setTimeout(() => {
        notificationDiv.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => notificationDiv.remove(), 300);
    }, 3000);
}

/**
 * Handle wallet connection
 */
async function handleWalletConnect() {
    if (typeof window.ethereum !== 'undefined') {
        try {
            // Request account access
            const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
            const address = accounts[0];
            
            AppState.walletAddress = address;
            AppState.walletConnected = true;
            localStorage.setItem('walletAddress', address);
            
            updateConnectButton();
            loadStats();
            
            console.log('Wallet connected:', address);
        } catch (error) {
            console.error('Wallet connection failed:', error);
            // Fallback to demo mode
            useDemoWallet();
        }
    } else {
        // No Web3 provider, use demo wallet
        useDemoWallet();
    }
}

/**
 * Use a demo wallet for testing without MetaMask
 */
function useDemoWallet() {
    const demoAddress = '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb';
    AppState.walletAddress = demoAddress;
    AppState.walletConnected = true;
    localStorage.setItem('walletAddress', demoAddress);
    updateConnectButton();
    console.log('Using demo wallet:', demoAddress);
}

/**
 * Update connect button state
 */
function updateConnectButton() {
    const btn = document.getElementById('connectWallet');
    if (!btn) return;
    
    if (AppState.walletConnected && AppState.walletAddress) {
        const shortAddr = `${AppState.walletAddress.slice(0, 6)}...${AppState.walletAddress.slice(-4)}`;
        btn.textContent = shortAddr;
        btn.classList.add('bg-green-600');
    } else {
        btn.textContent = 'Connect Wallet';
        btn.classList.remove('bg-green-600');
    }
}

/**
 * Format address for display
 */
function formatAddress(address) {
    if (!address) return '';
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

/**
 * Refresh all data
 */
async function refreshData() {
    await loadStats();
    await renderMarkets(document.getElementById('categoryFilter')?.value || '');
}

// Auto-refresh every 30 seconds
setInterval(refreshData, 30000);

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

// Export for debugging
window.BIAR = {
    state: AppState,
    api,
    refreshData,
    initApp
};
