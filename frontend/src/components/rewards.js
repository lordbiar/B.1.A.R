/**
 * BIAR Protocol - Rewards & Incentives UI
 * Display and manage rewards, liquidity mining, and referrals
 */

class RewardsUI {
    constructor(userAddress) {
        this.userAddress = userAddress;
        this.rewards = [];
        this.referralCode = null;
    }

    /**
     * Load user rewards data
     */
    async loadRewards() {
        // In production, fetch from API
        this.rewards = this.generateSampleRewards();
        this.referralCode = `ref_${this.userAddress.slice(0, 8)}`;
    }

    /**
     * Generate sample rewards for demo
     */
    generateSampleRewards() {
        return [
            {
                id: 1,
                type: 'trading_rebate',
                amount: 250.50,
                timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000),
                claimed: false,
                description: 'Trading rebate on market orders'
            },
            {
                id: 2,
                type: 'liquidity_mining',
                amount: 500.00,
                timestamp: new Date(Date.now() - 24 * 60 * 60 * 1000),
                claimed: false,
                description: 'Liquidity mining rewards (7d)'
            },
            {
                id: 3,
                type: 'referral',
                amount: 100.00,
                timestamp: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000),
                claimed: false,
                description: 'Referral bonus from sign-up'
            },
            {
                id: 4,
                type: 'early_adopter',
                amount: 50.00,
                timestamp: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
                claimed: true,
                description: 'Early adopter bonus (Tier 1)'
            }
        ];
    }

    /**
     * Create rewards dashboard widget
     */
    createRewardsDashboard() {
        const container = document.createElement('div');
        container.className = 'space-y-6';

        // Summary cards
        const summary = this.createSummaryCards();
        container.appendChild(summary);

        // Rewards list
        const rewardsList = this.createRewardsList();
        container.appendChild(rewardsList);

        // Claim rewards button
        const unclaimedAmount = this.getUnclaimedTotal();
        if (unclaimedAmount > 0) {
            const claimBtn = document.createElement('button');
            claimBtn.className = 'w-full gradient-bg py-3 rounded-lg font-semibold text-lg hover:opacity-90 transition';
            claimBtn.innerHTML = `💰 Claim ${unclaimedAmount.toFixed(2)} USDC`;
            claimBtn.onclick = () => this.claimRewards();
            container.appendChild(claimBtn);
        }

        return container;
    }

    /**
     * Create summary cards
     */
    createSummaryCards() {
        const container = document.createElement('div');
        container.className = 'grid grid-cols-1 md:grid-cols-4 gap-4';

        const totalEarned = this.getTotalEarned();
        const totalClaimed = this.getTotalClaimed();
        const unclaimed = this.getUnclaimedTotal();
        const referralCode = this.referralCode;

        const cards = [
            {
                label: 'Total Earned',
                value: `$${totalEarned.toFixed(2)}`,
                icon: '💵',
                color: 'text-green-400'
            },
            {
                label: 'Claimed',
                value: `$${totalClaimed.toFixed(2)}`,
                icon: '✅',
                color: 'text-blue-400'
            },
            {
                label: 'Pending',
                value: `$${unclaimed.toFixed(2)}`,
                icon: '⏳',
                color: 'text-yellow-400'
            },
            {
                label: 'Referral Code',
                value: referralCode || 'N/A',
                icon: '🎯',
                color: 'text-purple-400',
                copyable: true
            }
        ];

        cards.forEach(card => {
            const div = document.createElement('div');
            div.className = 'bg-dark-800 rounded-lg p-4 border border-dark-700 hover:border-primary transition';
            
            let html = `
                <div class="flex items-center justify-between mb-2">
                    <span class="text-2xl">${card.icon}</span>
                    <span class="text-gray-400 text-sm">${card.label}</span>
                </div>
                <p class="text-2xl font-bold ${card.color}">${card.value}</p>
            `;

            if (card.copyable) {
                html += `
                    <button onclick="copyToClipboard('${card.value}')" class="mt-2 text-xs text-gray-400 hover:text-white transition">
                        Copy code
                    </button>
                `;
            }

            div.innerHTML = html;
            container.appendChild(div);
        });

        return container;
    }

    /**
     * Create rewards list
     */
    createRewardsList() {
        const container = document.createElement('div');
        container.className = 'bg-dark-800 rounded-lg overflow-hidden';

        // Header
        const header = document.createElement('div');
        header.className = 'bg-dark-700 p-4 grid grid-cols-4 gap-4 font-semibold text-sm text-gray-400 border-b border-dark-600';
        header.innerHTML = `
            <div>Type</div>
            <div>Amount</div>
            <div>Date</div>
            <div>Status</div>
        `;
        container.appendChild(header);

        // Rewards rows
        this.rewards.forEach(reward => {
            const row = document.createElement('div');
            row.className = 'p-4 grid grid-cols-4 gap-4 border-b border-dark-700 hover:bg-dark-700/30 transition items-center';

            const typeLabel = this.getRewardTypeLabel(reward.type);
            const typeEmoji = this.getRewardTypeEmoji(reward.type);
            const statusBadge = reward.claimed ? 
                '<span class="bg-green-500/20 text-green-400 text-xs px-2 py-1 rounded-full">Claimed</span>' :
                '<span class="bg-yellow-500/20 text-yellow-400 text-xs px-2 py-1 rounded-full">Pending</span>';

            row.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="text-lg">${typeEmoji}</span>
                    <div>
                        <p class="font-semibold text-sm">${typeLabel}</p>
                        <p class="text-xs text-gray-400">${reward.description}</p>
                    </div>
                </div>
                <div class="font-bold text-lg text-green-400">+$${reward.amount.toFixed(2)}</div>
                <div class="text-sm text-gray-400">${reward.timestamp.toLocaleDateString()}</div>
                <div>${statusBadge}</div>
            `;

            container.appendChild(row);
        });

        return container;
    }

    /**
     * Create referral widget
     */
    createReferralWidget() {
        const container = document.createElement('div');
        container.className = 'bg-gradient-to-r from-primary/20 to-accent/20 rounded-lg p-6 border border-primary/30';

        container.innerHTML = `
            <div class="flex items-start justify-between">
                <div>
                    <h3 class="text-2xl font-bold mb-2">🎯 Referral Program</h3>
                    <p class="text-gray-400 mb-4">
                        Share your referral code and earn 5% commission on every trade your friends make.
                        Your friends also get 2% bonus on their first trade!
                    </p>
                    <div class="space-y-2">
                        <p class="text-sm text-gray-400">Your Referral Code:</p>
                        <div class="flex gap-2">
                            <input type="text" value="${this.referralCode}" readonly class="flex-1 bg-dark-900 border border-dark-600 rounded px-3 py-2 font-mono text-sm">
                            <button onclick="copyToClipboard('${this.referralCode}')" class="bg-primary hover:bg-primary/80 px-4 py-2 rounded font-semibold transition">
                                Copy
                            </button>
                        </div>
                    </div>
                </div>
                <div class="text-4xl">💰</div>
            </div>
            
            <div class="mt-6 grid grid-cols-2 gap-4">
                <div class="bg-dark-800 rounded p-4">
                    <p class="text-gray-400 text-sm">Friends Referred</p>
                    <p class="text-3xl font-bold">12</p>
                </div>
                <div class="bg-dark-800 rounded p-4">
                    <p class="text-gray-400 text-sm">Referral Earnings</p>
                    <p class="text-3xl font-bold text-green-400">$2,450</p>
                </div>
            </div>
        `;

        return container;
    }

    /**
     * Create liquidity mining widget
     */
    createLiquidityMiningWidget() {
        const container = document.createElement('div');
        container.className = 'bg-gradient-to-r from-secondary/20 to-primary/20 rounded-lg p-6 border border-secondary/30';

        container.innerHTML = `
            <div class="flex items-start justify-between">
                <div>
                    <h3 class="text-2xl font-bold mb-2">💧 Liquidity Mining</h3>
                    <p class="text-gray-400 mb-4">
                        Earn up to 50% APY by providing liquidity to prediction markets.
                        No lock-up period - withdraw anytime!
                    </p>
                </div>
                <div class="text-4xl">🌊</div>
            </div>
            
            <div class="mt-6 grid grid-cols-3 gap-4">
                <div class="bg-dark-800 rounded p-4">
                    <p class="text-gray-400 text-sm">Your Liquidity</p>
                    <p class="text-2xl font-bold">$5,000</p>
                </div>
                <div class="bg-dark-800 rounded p-4">
                    <p class="text-gray-400 text-sm">APY Rate</p>
                    <p class="text-2xl font-bold text-green-400">42%</p>
                </div>
                <div class="bg-dark-800 rounded p-4">
                    <p class="text-gray-400 text-sm">Pending Rewards</p>
                    <p class="text-2xl font-bold">$487.50</p>
                </div>
            </div>
            
            <button class="w-full mt-4 bg-secondary/20 border border-secondary hover:bg-secondary/40 transition py-2 rounded font-semibold">
                Manage Liquidity
            </button>
        `;

        return container;
    }

    // ==================== Helper Methods ====================

    getTotalEarned() {
        return this.rewards.reduce((sum, r) => sum + r.amount, 0);
    }

    getTotalClaimed() {
        return this.rewards.filter(r => r.claimed).reduce((sum, r) => sum + r.amount, 0);
    }

    getUnclaimedTotal() {
        return this.rewards.filter(r => !r.claimed).reduce((sum, r) => sum + r.amount, 0);
    }

    getRewardTypeLabel(type) {
        const labels = {
            'trading_rebate': 'Trading Rebate',
            'liquidity_mining': 'Liquidity Mining',
            'referral': 'Referral Bonus',
            'market_creation': 'Market Creation',
            'early_adopter': 'Early Adopter'
        };
        return labels[type] || type;
    }

    getRewardTypeEmoji(type) {
        const emojis = {
            'trading_rebate': '💱',
            'liquidity_mining': '💧',
            'referral': '🎯',
            'market_creation': '📊',
            'early_adopter': '🎖️'
        };
        return emojis[type] || '💰';
    }

    claimRewards() {
        const amount = this.getUnclaimedTotal();
        showNotification(`Successfully claimed $${amount.toFixed(2)}!`, 'success');
        
        // Mark all as claimed
        this.rewards.forEach(r => r.claimed = true);
        
        // Refresh dashboard
        const dashboard = document.getElementById('rewardsDashboard');
        if (dashboard) {
            dashboard.innerHTML = '';
            dashboard.appendChild(this.createRewardsDashboard());
        }
    }
}

/**
 * Create rewards page
 */
async function createRewardsPage(userAddress) {
    const container = document.createElement('div');
    container.className = 'space-y-6';

    const ui = new RewardsUI(userAddress);
    await ui.loadRewards();

    // Header
    const header = document.createElement('div');
    header.className = 'mb-8';
    header.innerHTML = `
        <h1 class="text-4xl font-bold mb-2 bg-gradient-to-r from-green-400 to-blue-400 bg-clip-text text-transparent">
            💰 Rewards & Incentives
        </h1>
        <p class="text-gray-400">Earn USDC through trading, liquidity mining, and referrals</p>
    `;
    container.appendChild(header);

    // Rewards dashboard
    const dashboard = document.createElement('div');
    dashboard.id = 'rewardsDashboard';
    dashboard.appendChild(ui.createRewardsDashboard());
    container.appendChild(dashboard);

    // Referral widget
    container.appendChild(ui.createReferralWidget());

    // Liquidity mining widget
    container.appendChild(ui.createLiquidityMiningWidget());

    return container;
}

/**
 * Show rewards modal
 */
function showRewards(userAddress) {
    const modal = document.getElementById('rewardsModal') || createRewardsModal();
    const content = modal.querySelector('.modal-content');
    content.innerHTML = '';
    
    createRewardsPage(userAddress).then(page => {
        content.appendChild(page);
    });
    
    modal.classList.remove('hidden');
}

/**
 * Create rewards modal
 */
function createRewardsModal() {
    const modal = document.createElement('div');
    modal.id = 'rewardsModal';
    modal.className = 'fixed inset-0 modal-backdrop bg-black/60 z-50 hidden overflow-y-auto';
    
    modal.innerHTML = `
        <div class="min-h-screen flex items-start justify-center p-4 pt-20">
            <div class="bg-dark-800 rounded-2xl w-full max-w-4xl p-6 relative">
                <button onclick="this.closest('#rewardsModal').classList.add('hidden')" class="absolute top-4 right-4 text-gray-400 hover:text-white z-10">
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
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text);
    showNotification('Copied to clipboard!', 'success');
}
