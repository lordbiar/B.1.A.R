/**
 * BIAR Protocol - Advanced Analytics Dashboard
 * Real-time charts, historical data, and market insights
 */

class MarketAnalytics {
    constructor(marketId, wsClient) {
        this.marketId = marketId;
        this.wsClient = wsClient;
        this.priceHistory = [];
        this.volumeData = [];
        this.probabilityHistory = {};
        this.trades = [];
        this.chart = null;
        this.volumeChart = null;
    }

    /**
     * Initialize charts for a market
     */
    async initCharts(container) {
        // Get historical data
        await this.loadHistoricalData();
        
        // Create price chart
        this.createPriceChart(container);
        
        // Create volume chart
        this.createVolumeChart(container);
        
        // Listen for real-time updates
        this.setupRealtimeUpdates();
    }

    /**
     * Load historical price data (simulated)
     */
    async loadHistoricalData() {
        // In production, fetch from API
        // For now, generate realistic historical data
        const now = Date.now();
        const dayAgo = now - (24 * 60 * 60 * 1000);
        
        for (let i = 0; i < 96; i++) { // 15-min intervals for 24 hours
            const time = dayAgo + (i * 15 * 60 * 1000);
            const basePrice = 0.45 + Math.random() * 0.1;
            const price = basePrice + (Math.sin(i / 10) * 0.05);
            
            this.priceHistory.push({
                timestamp: new Date(time),
                time: new Date(time).toLocaleTimeString(),
                price: Math.max(0.01, Math.min(0.99, price)),
                volume: Math.random() * 50000 + 10000
            });
        }
    }

    /**
     * Create price movement chart using Chart.js
     */
    createPriceChart(container) {
        const chartContainer = document.createElement('div');
        chartContainer.className = 'bg-dark-800 rounded-lg p-4 mb-4';
        chartContainer.style.position = 'relative';
        chartContainer.style.height = '400px';
        
        const canvas = document.createElement('canvas');
        chartContainer.appendChild(canvas);
        container.appendChild(chartContainer);

        const ctx = canvas.getContext('2d');
        
        const data = {
            labels: this.priceHistory.map(d => d.time),
            datasets: [{
                label: 'Price (USDC)',
                data: this.priceHistory.map(d => d.price),
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointBackgroundColor: '#6366f1',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }];
        };

        this.chart = new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: '#9ca3af',
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.8)',
                        titleColor: '#fff',
                        bodyColor: '#d1d5db',
                        borderColor: '#6366f1',
                        borderWidth: 1,
                        padding: 12,
                        titleFont: { size: 13, weight: 'bold' },
                        bodyFont: { size: 12 }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        grid: {
                            color: 'rgba(75, 85, 99, 0.2)'
                        },
                        ticks: {
                            color: '#9ca3af',
                            maxTicksLimit: 6
                        }
                    },
                    y: {
                        display: true,
                        grid: {
                            color: 'rgba(75, 85, 99, 0.2)'
                        },
                        ticks: {
                            color: '#9ca3af',
                            callback: function(value) {
                                return value.toFixed(3);
                            }
                        },
                        min: 0,
                        max: 1
                    }
                }
            }
        });
    }

    /**
     * Create volume chart
     */
    createVolumeChart(container) {
        const chartContainer = document.createElement('div');
        chartContainer.className = 'bg-dark-800 rounded-lg p-4';
        chartContainer.style.position = 'relative';
        chartContainer.style.height = '200px';
        
        const canvas = document.createElement('canvas');
        chartContainer.appendChild(canvas);
        container.appendChild(chartContainer);

        const ctx = canvas.getContext('2d');
        
        const data = {
            labels: this.priceHistory.map(d => d.time),
            datasets: [{
                label: 'Volume (USDC)',
                data: this.priceHistory.map(d => d.volume),
                backgroundColor: 'rgba(8, 182, 212, 0.3)',
                borderColor: '#06b6d4',
                borderWidth: 1,
                type: 'bar'
            }];
        };

        this.volumeChart = new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.8)',
                        titleColor: '#fff',
                        bodyColor: '#d1d5db',
                        borderColor: '#06b6d4',
                        borderWidth: 1
                    }
                },
                scales: {
                    x: {
                        display: true,
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#9ca3af',
                            maxTicksLimit: 6
                        }
                    },
                    y: {
                        display: true,
                        grid: {
                            color: 'rgba(75, 85, 99, 0.2)'
                        },
                        ticks: {
                            color: '#9ca3af'
                        }
                    }
                }
            }
        });
    }

    /**
     * Setup real-time updates
     */
    setupRealtimeUpdates() {
        window.addEventListener('priceUpdate', (event) => {
            if (event.detail.market_id === this.marketId) {
                this.updateCharts(event.detail.prices);
            }
        });
    }

    /**
     * Update charts with new data
     */
    updateCharts(prices) {
        const now = new Date();
        
        // Add new price point
        const latestPrice = Object.values(prices)[0] || 0;
        const volume = Math.random() * 50000 + 10000;
        
        this.priceHistory.push({
            timestamp: now,
            time: now.toLocaleTimeString(),
            price: latestPrice,
            volume: volume
        });

        // Keep only last 96 data points (24 hours at 15-min intervals)
        if (this.priceHistory.length > 96) {
            this.priceHistory.shift();
        }

        // Update charts
        if (this.chart) {
            this.chart.data.labels = this.priceHistory.map(d => d.time);
            this.chart.data.datasets[0].data = this.priceHistory.map(d => d.price);
            this.chart.update('none');
        }

        if (this.volumeChart) {
            this.volumeChart.data.labels = this.priceHistory.map(d => d.time);
            this.volumeChart.data.datasets[0].data = this.priceHistory.map(d => d.volume);
            this.volumeChart.update('none');
        }
    }

    /**
     * Calculate and return analytics metrics
     */
    getAnalytics() {
        const prices = this.priceHistory.map(d => d.price);
        
        if (prices.length === 0) return null;

        const currentPrice = prices[prices.length - 1];
        const previousPrice = prices[0];
        const change = currentPrice - previousPrice;
        const changePercent = (change / previousPrice) * 100;

        // Calculate volatility (standard deviation)
        const mean = prices.reduce((a, b) => a + b) / prices.length;
        const variance = prices.reduce((sq, n) => sq + Math.pow(n - mean, 2), 0) / prices.length;
        const volatility = Math.sqrt(variance);

        // Calculate moving averages
        const sma7 = this.calculateSMA(prices, 7);
        const sma21 = this.calculateSMA(prices, 21);

        // Calculate RSI
        const rsi = this.calculateRSI(prices, 14);

        // Total volume
        const totalVolume = this.priceHistory.reduce((sum, d) => sum + d.volume, 0);

        return {
            currentPrice: currentPrice.toFixed(4),
            change: change.toFixed(4),
            changePercent: changePercent.toFixed(2),
            high: Math.max(...prices).toFixed(4),
            low: Math.min(...prices).toFixed(4),
            volatility: (volatility * 100).toFixed(2),
            sma7: sma7.toFixed(4),
            sma21: sma21.toFixed(4),
            rsi: rsi.toFixed(0),
            totalVolume: totalVolume.toLocaleString(undefined, { maximumFractionDigits: 0 }),
            dataPoints: prices.length
        };
    }

    /**
     * Calculate Simple Moving Average
     */
    calculateSMA(data, period) {
        if (data.length < period) return data[data.length - 1];
        return data.slice(-period).reduce((a, b) => a + b) / period;
    }

    /**
     * Calculate Relative Strength Index
     */
    calculateRSI(data, period = 14) {
        const changes = [];
        for (let i = 1; i < data.length; i++) {
            changes.push(data[i] - data[i - 1]);
        }

        const gains = changes.filter(x => x > 0).reduce((a, b) => a + b, 0) / period;
        const losses = Math.abs(changes.filter(x => x < 0).reduce((a, b) => a + b, 0) / period);

        const rs = gains / (losses || 1);
        return 100 - (100 / (1 + rs));
    }

    /**
     * Create analytics widget for dashboard
     */
    createAnalyticsWidget() {
        const container = document.createElement('div');
        container.className = 'bg-dark-800 rounded-lg p-6 mb-4';
        
        const analytics = this.getAnalytics();
        if (!analytics) return container;

        const isPositive = parseFloat(analytics.change) > 0;
        const changeColor = isPositive ? 'text-green-400' : 'text-red-400';
        const changeIcon = isPositive ? '↗' : '↘';

        container.innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                    <p class="text-gray-400 text-sm">Price</p>
                    <p class="text-2xl font-bold">${analytics.currentPrice}</p>
                </div>
                <div>
                    <p class="text-gray-400 text-sm">Change 24h</p>
                    <p class="text-2xl font-bold ${changeColor}">
                        ${changeIcon} ${analytics.changePercent}%
                    </p>
                </div>
                <div>
                    <p class="text-gray-400 text-sm">24h High/Low</p>
                    <p class="text-lg font-semibold">${analytics.high} / ${analytics.low}</p>
                </div>
                <div>
                    <p class="text-gray-400 text-sm">Volatility</p>
                    <p class="text-lg font-semibold text-yellow-400">${analytics.volatility}%</p>
                </div>
                <div>
                    <p class="text-gray-400 text-sm">RSI (14)</p>
                    <p class="text-lg font-semibold">${analytics.rsi}</p>
                </div>
                <div>
                    <p class="text-gray-400 text-sm">SMA 7/21</p>
                    <p class="text-sm font-semibold">${analytics.sma7} / ${analytics.sma21}</p>
                </div>
                <div>
                    <p class="text-gray-400 text-sm">24h Volume</p>
                    <p class="text-lg font-semibold">$${analytics.totalVolume}</p>
                </div>
                <div>
                    <p class="text-gray-400 text-sm">Data Points</p>
                    <p class="text-lg font-semibold">${analytics.dataPoints}</p>
                </div>
            </div>
        `;

        return container;
    }
}

/**
 * Create advanced market view with charts and analytics
 */
function createAdvancedMarketView(marketId) {
    const container = document.createElement('div');
    container.className = 'space-y-4';

    const analytics = new MarketAnalytics(marketId, wsClient);

    // Initialize charts
    analytics.initCharts(container);

    // Add analytics widget
    const analyticsWidget = analytics.createAnalyticsWidget();
    container.insertBefore(analyticsWidget, container.firstChild);

    return container;
}

/**
 * Show detailed market view in modal
 */
function showMarketAdvancedView(marketId) {
    const modal = document.getElementById('advancedViewModal') || createAdvancedViewModal();
    
    const content = modal.querySelector('.modal-content');
    content.innerHTML = '';
    
    // Create advanced view
    const advancedView = createAdvancedMarketView(marketId);
    content.appendChild(advancedView);
    
    modal.classList.remove('hidden');
}

/**
 * Create advanced view modal
 */
function createAdvancedViewModal() {
    const modal = document.createElement('div');
    modal.id = 'advancedViewModal';
    modal.className = 'fixed inset-0 modal-backdrop bg-black/60 z-50 hidden overflow-y-auto';
    
    modal.innerHTML = `
        <div class="min-h-screen flex items-start justify-center p-4 pt-20">
            <div class="bg-dark-800 rounded-2xl w-full max-w-4xl p-6 relative">
                <button onclick="this.closest('#advancedViewModal').classList.add('hidden')" class="absolute top-4 right-4 text-gray-400 hover:text-white z-10">
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
