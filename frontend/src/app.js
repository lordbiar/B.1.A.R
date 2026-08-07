/**
 * BIAR Protocol - Main Application
 * Initializes the dashboard and handles global state
 */

// Global state
const AppState = {
    walletConnected: false,
    walletAddress: null,
    currentMarket: null,
    markets: []
};

/**
 * Initialize the application
 */
async function initApp() {
    console.log('BIAR Protocol Dashboard initializing...');
    
    // Load saved wallet
    const savedWallet = localStorage.getItem('walletAddress');
    if (savedWallet) {
        AppState.walletAddress = savedWallet;
        AppState.walletConnected = true;
        updateConnectButton();
    }
    
    // Initialize components
    await loadStats();
    await renderMarkets();
    
    // Setup event listeners
    setupEventListeners();
    
    console.log('Dashboard initialized successfully');
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
    // Wallet connect button
    const connectBtn = document.getElementById('connectWallet');
    if (connectBtn) {
        connectBtn.addEventListener('click', handleWalletConnect);
    }
    
    // Listen for probability updates
    window.addEventListener('probabilityUpdate', (event) => {
        console.log('Probability updated:', event.detail);
        // Could update UI elements here
    });
    
    // Handle category filter
    const categoryFilter = document.getElementById('categoryFilter');
    if (categoryFilter) {
        categoryFilter.addEventListener('change', async (e) => {
            await renderMarkets(e.target.value);
        });
    }
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
