/**
 * BIAR Protocol - WebSocket Client
 * Real-time market data and price feed management
 */

class WebSocketClient {
    constructor(baseUrl = 'ws://localhost:8000') {
        this.baseUrl = baseUrl;
        this.connections = new Map();
        this.subscriptions = new Map();
        this.reconnectAttempts = 5;
        this.reconnectDelay = 3000;
    }

    /**
     * Connect to market WebSocket
     */
    async connectToMarket(marketId, clientId = null) {
        if (!clientId) {
            clientId = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        }

        const url = `${this.baseUrl}/ws/market/${marketId}/${clientId}`;
        
        return new Promise((resolve, reject) => {
            try {
                const ws = new WebSocket(url);
                const connectionKey = `market_${marketId}`;

                ws.onopen = () => {
                    console.log(`✓ Connected to market ${marketId} WebSocket`);
                    this.connections.set(connectionKey, ws);
                    
                    // Request initial market state
                    ws.send(JSON.stringify({ type: 'get_market_state' }));
                    resolve(ws);
                };

                ws.onerror = (error) => {
                    console.error(`WebSocket error for market ${marketId}:`, error);
                    reject(error);
                };

                ws.onmessage = (event) => {
                    this.handleMessage(JSON.parse(event.data), connectionKey);
                };

                ws.onclose = () => {
                    console.log(`✗ Disconnected from market ${marketId} WebSocket`);
                    this.connections.delete(connectionKey);
                    // Attempt reconnect
                    this.reconnect(connectionKey, () => this.connectToMarket(marketId, clientId));
                };

            } catch (error) {
                reject(error);
            }
        });
    }

    /**
     * Connect to user portfolio WebSocket
     */
    async connectToUserPortfolio(walletAddress) {
        const url = `${this.baseUrl}/ws/user/${walletAddress}`;
        
        return new Promise((resolve, reject) => {
            try {
                const ws = new WebSocket(url);
                const connectionKey = 'user_portfolio';

                ws.onopen = () => {
                    console.log(`✓ Connected to user portfolio WebSocket`);
                    this.connections.set(connectionKey, ws);
                    ws.send(JSON.stringify({ type: 'get_portfolio' }));
                    resolve(ws);
                };

                ws.onerror = (error) => {
                    console.error('Portfolio WebSocket error:', error);
                    reject(error);
                };

                ws.onmessage = (event) => {
                    this.handleMessage(JSON.parse(event.data), connectionKey);
                };

                ws.onclose = () => {
                    console.log('✗ Disconnected from user portfolio WebSocket');
                    this.connections.delete(connectionKey);
                    this.reconnect(connectionKey, () => this.connectToUserPortfolio(walletAddress));
                };

            } catch (error) {
                reject(error);
            }
        });
    }

    /**
     * Connect to global market feed
     */
    async connectToFeed() {
        const url = `${this.baseUrl}/ws/feed`;
        
        return new Promise((resolve, reject) => {
            try {
                const ws = new WebSocket(url);
                const connectionKey = 'global_feed';

                ws.onopen = () => {
                    console.log('✓ Connected to global market feed');
                    this.connections.set(connectionKey, ws);
                    resolve(ws);
                };

                ws.onerror = (error) => {
                    console.error('Global feed WebSocket error:', error);
                    reject(error);
                };

                ws.onmessage = (event) => {
                    this.handleMessage(JSON.parse(event.data), connectionKey);
                };

                ws.onclose = () => {
                    console.log('✗ Disconnected from global market feed');
                    this.connections.delete(connectionKey);
                };

            } catch (error) {
                reject(error);
            }
        });
    }

    /**
     * Handle incoming WebSocket messages
     */
    handleMessage(message, connectionKey) {
        const { type, data, market_id, prices, probabilities, timestamp } = message;

        switch (type) {
            case 'market_state':
                // Emit market state update event
                window.dispatchEvent(new CustomEvent('marketStateUpdate', {
                    detail: { market: data, timestamp }
                }));
                break;

            case 'price_update':
                // Emit price update event
                window.dispatchEvent(new CustomEvent('priceUpdate', {
                    detail: { market_id, prices, timestamp }
                }));
                break;

            case 'probability_update':
                // Emit probability update event
                window.dispatchEvent(new CustomEvent('probabilityUpdate', {
                    detail: { market_id, probabilities, timestamp }
                }));
                break;

            case 'order_executed':
                // Emit order update event
                window.dispatchEvent(new CustomEvent('orderExecuted', {
                    detail: { market_id, order: data.order, timestamp }
                }));
                break;

            case 'portfolio_state':
                // Emit portfolio update event
                window.dispatchEvent(new CustomEvent('portfolioUpdate', {
                    detail: { portfolio: data, timestamp }
                }));
                break;

            case 'notification':
                // Emit notification event
                window.dispatchEvent(new CustomEvent('notification', {
                    detail: { message: data.message, type: data.notification_type, timestamp }
                }));
                break;

            case 'pong':
                console.log('Pong received - connection alive');
                break;

            default:
                console.log('Unknown message type:', type);
        }
    }

    /**
     * Send ping to keep connection alive
     */
    sendPing(connectionKey) {
        const ws = this.connections.get(connectionKey);
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
        }
    }

    /**
     * Subscribe to market updates
     */
    subscribe(marketId, callback) {
        const key = `market_${marketId}`;
        if (!this.subscriptions.has(key)) {
            this.subscriptions.set(key, []);
        }
        this.subscriptions.get(key).push(callback);
        
        // Listen for updates
        window.addEventListener('marketStateUpdate', (event) => {
            if (event.detail.market.id === marketId) {
                callback(event.detail);
            }
        });
    }

    /**
     * Send message to market WebSocket
     */
    sendToMarket(marketId, message) {
        const ws = this.connections.get(`market_${marketId}`);
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(message));
        }
    }

    /**
     * Send message to user portfolio WebSocket
     */
    sendToPortfolio(message) {
        const ws = this.connections.get('user_portfolio');
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(message));
        }
    }

    /**
     * Disconnect from a connection
     */
    disconnect(connectionKey) {
        const ws = this.connections.get(connectionKey);
        if (ws) {
            ws.close();
            this.connections.delete(connectionKey);
        }
    }

    /**
     * Disconnect all connections
     */
    disconnectAll() {
        for (let ws of this.connections.values()) {
            if (ws.readyState === WebSocket.OPEN) {
                ws.close();
            }
        }
        this.connections.clear();
    }

    /**
     * Attempt to reconnect after disconnection
     */
    reconnect(connectionKey, reconnectFn) {
        let attempts = 0;
        const attemptReconnect = () => {
            if (attempts < this.reconnectAttempts) {
                attempts++;
                console.log(`Reconnecting ${connectionKey}... (attempt ${attempts})`);
                setTimeout(() => {
                    try {
                        reconnectFn();
                    } catch (e) {
                        attemptReconnect();
                    }
                }, this.reconnectDelay * attempts);
            }
        };
        attemptReconnect();
    }
}

// Global WebSocket client instance
const wsClient = new WebSocketClient();

// Keep-alive ping every 30 seconds
setInterval(() => {
    wsClient.connections.forEach((ws, key) => {
        wsClient.sendPing(key);
    });
}, 30000);
