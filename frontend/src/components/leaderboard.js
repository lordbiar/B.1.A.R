/**
 * BIAR Protocol - Leaderboard System
 * Rank traders by profitability, volume, win rate, and streak
 */

class LeaderboardManager {
    constructor() {
        this.traders = [];
        this.refreshInterval = 5000; // Update every 5 seconds
    }

    /**
     * Load leaderboard data
     */
    async loadLeaderboard(timeframe = '24h', category = 'profit') {
        // In production, fetch from API
        // For now, generate sample data
        this.traders = this.generateSampleLeaderboard();
        
        // Sort by category
        this.sortLeaderboard(category);
        
        return this.traders;
    }

    /**
     * Generate sample leaderboard data
     */
    generateSampleLeaderboard() {
        const names = ['AlphaTrade', 'BetaVision', 'GammaMind', 'DeltaForce', 'EpsilonPro', 
                      'ZetaQuant', 'EtaBot', 'ThetaLeads', 'IotaMaster', 'KappaKing'];
        
        return names.map((name, idx) => ({
            rank: idx + 1,
            address: `0x${Math.random().toString(16).slice(2)}`,
            username: name,
            profit: (Math.random() * 50000 - 5000).toFixed(2),
            roi: (Math.random() * 300 - 30).toFixed(1),
            volume: (Math.random() * 1000000).toFixed(0),
            trades: Math.floor(Math.random() * 500) + 10,
            winRate: (Math.random() * 70 + 30).toFixed(1),
            streak: Math.floor(Math.random() * 20 - 5),
            followers: Math.floor(Math.random() * 10000)
        }));
    }

    /**
     * Sort leaderboard by category
     */
    sortLeaderboard(category) {
        switch(category) {
            case 'profit':
                this.traders.sort((a, b) => parseFloat(b.profit) - parseFloat(a.profit));
                break;
            case 'roi':
                this.traders.sort((a, b) => parseFloat(b.roi) - parseFloat(a.roi));
                break;
            case 'volume':
                this.traders.sort((a, b) => parseFloat(b.volume) - parseFloat(a.volume));
                break;
            case 'winrate':
                this.traders.sort((a, b) => parseFloat(b.winRate) - parseFloat(a.winRate));
                break;
            case 'followers':
                this.traders.sort((a, b) => b.followers - a.followers);
                break;
        }
        
        // Update ranks
        this.traders.forEach((trader, idx) => {
            trader.rank = idx + 1;
        });
    }

    /**
     * Create leaderboard table
     */
    createLeaderboardTable(container, category = 'profit') {
        const table = document.createElement('div');
        table.className = 'bg-dark-800 rounded-lg overflow-hidden';

        // Table header
        const header = document.createElement('div');
        header.className = 'grid grid-cols-12 gap-4 bg-dark-700 p-4 font-semibold text-sm text-gray-400 border-b border-dark-600';
        header.innerHTML = `
            <div class="col-span-1">#</div>
            <div class="col-span-3">Trader</div>
            <div class="col-span-2">Profit/ROI</div>
            <div class="col-span-2">Win Rate</div>
            <div class="col-span-2">Volume</div>
            <div class="col-span-2">Action</div>
        `;
        table.appendChild(header);

        // Table rows
        const rows = document.createElement('div');
        this.traders.forEach((trader, idx) => {
            const row = document.createElement('div');
            row.className = 'grid grid-cols-12 gap-4 p-4 border-b border-dark-700 hover:bg-dark-700/50 transition items-center';
            
            const profitColor = parseFloat(trader.profit) > 0 ? 'text-green-400' : 'text-red-400';
            const profitIcon = parseFloat(trader.profit) > 0 ? '↗' : '↘';

            row.innerHTML = `
                <div class="col-span-1 font-bold text-lg">
                    ${trader.rank <= 3 ? '🏆' : ''} ${trader.rank}
                </div>
                <div class="col-span-3">
                    <div class="flex items-center gap-2">
                        <div class="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-sm font-bold">
                            ${trader.username.charAt(0)}
                        </div>
                        <div>
                            <p class="font-semibold text-sm">${trader.username}</p>
                            <p class="text-xs text-gray-400">${trader.address.slice(0, 6)}...${trader.address.slice(-4)}</p>
                        </div>
                    </div>
                </div>
                <div class="col-span-2">
                    <p class="font-bold ${profitColor}">
                        ${profitIcon} $${trader.profit}
                    </p>
                    <p class="text-xs text-gray-400">${trader.roi}% ROI</p>
                </div>
                <div class="col-span-2">
                    <div class="flex items-center gap-2">
                        <div class="flex-1 bg-dark-600 rounded-full h-2">
                            <div class="bg-gradient-to-r from-green-400 to-blue-400 h-2 rounded-full" style="width: ${trader.winRate}%"></div>
                        </div>
                        <span class="text-sm font-semibold">${trader.winRate}%</span>
                    </div>
                </div>
                <div class="col-span-2">
                    <p class="font-semibold text-sm">$${(parseInt(trader.volume) / 1000).toFixed(0)}k</p>
                    <p class="text-xs text-gray-400">${trader.trades} trades</p>
                </div>
                <div class="col-span-2 flex gap-2">
                    <button onclick="followTrader('${trader.address}')" class="flex-1 bg-primary/20 text-primary text-xs py-1 rounded hover:bg-primary/40 transition font-semibold">
                        Follow
                    </button>
                    <button onclick="viewTraderProfile('${trader.address}')" class="flex-1 border border-dark-600 text-xs py-1 rounded hover:border-primary transition">
                        Profile
                    </button>
                </div>
            `;
            rows.appendChild(row);
        });
        
        table.appendChild(rows);
        container.appendChild(table);
    }
}

/**
 * Create leaderboard page
 */
function createLeaderboardPage() {
    const container = document.createElement('div');
    container.className = 'space-y-6';

    // Header
    const header = document.createElement('div');
    header.className = 'mb-8';
    header.innerHTML = `
        <h1 class="text-4xl font-bold mb-2 bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
            🏆 Leaderboard
        </h1>
        <p class="text-gray-400">Follow top traders and see who's winning in the prediction markets</p>
    `;
    container.appendChild(header);

    // Filters
    const filters = document.createElement('div');
    filters.className = 'flex flex-col md:flex-row gap-4 mb-6';
    
    const timeframeSelect = document.createElement('select');
    timeframeSelect.className = 'bg-dark-800 border border-dark-600 rounded-lg px-4 py-2 text-white';
    timeframeSelect.innerHTML = `
        <option value="24h">Last 24h</option>
        <option value="7d">Last 7d</option>
        <option value="30d">Last 30d</option>
        <option value="all">All Time</option>
    `;
    
    const categorySelect = document.createElement('select');
    categorySelect.className = 'bg-dark-800 border border-dark-600 rounded-lg px-4 py-2 text-white';
    categorySelect.id = 'categorySelect';
    categorySelect.innerHTML = `
        <option value="profit">Highest Profit</option>
        <option value="roi">Highest ROI</option>
        <option value="volume">Most Volume</option>
        <option value="winrate">Highest Win Rate</option>
        <option value="followers">Most Followers</option>
    `;
    
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Search trader...';
    searchInput.className = 'bg-dark-800 border border-dark-600 rounded-lg px-4 py-2 text-white placeholder-gray-500 flex-1';
    
    filters.appendChild(timeframeSelect);
    filters.appendChild(categorySelect);
    filters.appendChild(searchInput);
    container.appendChild(filters);

    // Leaderboard table
    const manager = new LeaderboardManager();
    manager.loadLeaderboard('24h', 'profit');
    
    manager.createLeaderboardTable(container, 'profit');

    // Category change handler
    categorySelect.addEventListener('change', (e) => {
        const tableContainer = container.querySelector('.bg-dark-800.rounded-lg');
        if (tableContainer) {
            tableContainer.remove();
        }
        manager.loadLeaderboard('24h', e.target.value);
        manager.createLeaderboardTable(container, e.target.value);
    });

    return container;
}

/**
 * Show leaderboard modal
 */
function showLeaderboard() {
    const modal = document.getElementById('leaderboardModal') || createLeaderboardModal();
    const content = modal.querySelector('.modal-content');
    content.innerHTML = '';
    content.appendChild(createLeaderboardPage());
    modal.classList.remove('hidden');
}

/**
 * Create leaderboard modal
 */
function createLeaderboardModal() {
    const modal = document.createElement('div');
    modal.id = 'leaderboardModal';
    modal.className = 'fixed inset-0 modal-backdrop bg-black/60 z-50 hidden overflow-y-auto';
    
    modal.innerHTML = `
        <div class="min-h-screen flex items-start justify-center p-4 pt-20">
            <div class="bg-dark-800 rounded-2xl w-full max-w-5xl p-6 relative">
                <button onclick="this.closest('#leaderboardModal').classList.add('hidden')" class="absolute top-4 right-4 text-gray-400 hover:text-white z-10">
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
 * Follow a trader
 */
function followTrader(traderAddress) {
    console.log('Following trader:', traderAddress);
    showNotification(`You are now following this trader!`, 'success');
}

/**
 * View trader profile
 */
function viewTraderProfile(traderAddress) {
    // TODO: Create trader profile modal
    console.log('Viewing profile for:', traderAddress);
}
