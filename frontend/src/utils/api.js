/**
 * BIAR Protocol - API Client
 * Handles communication with the backend API
 */

const API_BASE_URL = 'http://localhost:8000/api/v1';

class BIAPI {
    constructor(baseUrl = API_BASE_URL) {
        this.baseUrl = baseUrl;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'API request failed');
            }
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // Market endpoints
    async getMarkets(filters = {}) {
        const params = new URLSearchParams();
        if (filters.status) params.append('status', filters.status);
        if (filters.category) params.append('category', filters.category);
        if (filters.limit) params.append('limit', filters.limit);
        
        return this.request(`/markets?${params.toString()}`);
    }

    async getMarket(marketId) {
        return this.request(`/markets/${marketId}`);
    }

    async createMarket(marketData) {
        return this.request('/markets', {
            method: 'POST',
            body: JSON.stringify(marketData)
        });
    }

    async resolveMarket(marketId, winningOutcome, oracleData = null) {
        return this.request(`/markets/${marketId}/resolve?winning_outcome=${encodeURIComponent(winningOutcome)}`, {
            method: 'POST',
            body: JSON.stringify({ oracle_data: oracleData })
        });
    }

    // Order endpoints
    async placeOrder(marketId, orderData) {
        return this.request(`/markets/${marketId}/order`, {
            method: 'POST',
            body: JSON.stringify(orderData)
        });
    }

    async getOrderbook(marketId) {
        return this.request(`/markets/${marketId}/orderbook`);
    }

    // Position endpoints
    async getUserPositions(userAddress, marketId = null) {
        const endpoint = marketId 
            ? `/users/${userAddress}/positions?market_id=${marketId}`
            : `/users/${userAddress}/positions`;
        return this.request(endpoint);
    }

    // Simulation endpoints
    async simulateSlippage(marketId, outcome, amount, modelType = 'lmsr') {
        return this.request('/simulation/slippage', {
            method: 'POST',
            body: JSON.stringify({
                market_id: marketId,
                outcome,
                amount,
                model_type: modelType
            })
        });
    }

    async simulateLiquidityDepth(marketId, outcome, tradeSizes = [10, 50, 100, 500, 1000]) {
        return this.request('/simulation/liquidity-depth', {
            method: 'POST',
            body: JSON.stringify({
                market_id: marketId,
                outcome,
                trade_sizes: tradeSizes
            })
        });
    }

    // Stats endpoint
    async getStats() {
        return this.request('/stats');
    }

    // Oracle endpoints
    async getOracleFeeds(activeOnly = true) {
        return this.request(`/oracles?active_only=${activeOnly}`);
    }
}

// Export singleton instance
const api = new BIAPI();
