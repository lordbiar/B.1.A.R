/**
 * BIAR Protocol - API client with input sanitization and error handling.
 */
const API_BASE = window.location.hostname === 'localhost'
  ? 'http://localhost:8000'
  : window.location.origin;

const ApiClient = {
  async request(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);

    try {
      const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (res.status === 429) {
        throw new Error('Rate limit exceeded. Please slow down.');
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${res.status})`);
      }
      return await res.json();
    } catch (err) {
      if (err.name === 'AbortError') {
        throw new Error('Request timed out');
      }
      throw err;
    } finally {
      clearTimeout(timeout);
    }
  },

  getMarkets(category) {
    const q = category ? `?category=${encodeURIComponent(category)}` : '';
    return this.request(`/api/v1/markets${q}`);
  },

  getMarket(id) {
    return this.request(`/api/v1/markets/${encodeURIComponent(id)}`);
  },

  getOrderbook(id) {
    return this.request(`/api/v1/markets/${encodeURIComponent(id)}/orderbook`);
  },

  getStats() {
    return this.request('/api/v1/stats');
  },

  placeOrder(marketId, order) {
    return this.request(`/api/v1/markets/${encodeURIComponent(marketId)}/order`, {
      method: 'POST',
      body: JSON.stringify(order),
    });
  },

  createMarket(data) {
    return this.request('/api/v1/markets', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
};

// XSS-safe DOM text setter
function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}