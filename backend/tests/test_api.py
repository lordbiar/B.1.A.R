"""BIAR Protocol - Backend test suite (AMM math, API, security)."""
import math

import pytest
from fastapi.testclient import TestClient

from core.amm import AMMError, LMSRMarket


# ==================== AMM unit tests ====================


class TestLMSR:
    def test_initial_prices_uniform(self):
        amm = LMSRMarket(liquidity_b=100, q=[0.0, 0.0])
        prices = amm.prices()
        assert prices == pytest.approx([0.5, 0.5])

    def test_prices_sum_to_one(self):
        amm = LMSRMarket(liquidity_b=100, q=[50.0, 20.0, 10.0])
        assert sum(amm.prices()) == pytest.approx(1.0)

    def test_buy_shifts_price_up(self):
        amm = LMSRMarket(liquidity_b=100, q=[0.0, 0.0])
        before = amm.price(0)
        amm.execute_buy(0, 50)
        assert amm.price(0) > before
        assert sum(amm.prices()) == pytest.approx(1.0)

    def test_buy_cost_positive_and_increasing(self):
        amm = LMSRMarket(liquidity_b=100, q=[0.0, 0.0])
        c1 = amm.buy_cost(0, 10)
        c2 = amm.buy_cost(0, 100)
        assert c1 > 0
        assert c2 > c1 * 10  # super-linear cost (price impact)

    def test_sell_reduces_shares(self):
        amm = LMSRMarket(liquidity_b=100, q=[100.0, 50.0])
        proceeds = amm.execute_sell(0, 40)
        assert proceeds > 0
        assert amm.q[0] == pytest.approx(60.0)

    def test_cannot_sell_more_than_outstanding(self):
        amm = LMSRMarket(liquidity_b=100, q=[10.0, 10.0])
        with pytest.raises(AMMError):
            amm.sell_proceeds(0, 20)

    def test_no_overflow_large_shares(self):
        """Log-sum-exp stability: huge share counts must not overflow."""
        amm = LMSRMarket(liquidity_b=200, q=[1e9, 2e9, 5e8])
        prices = amm.prices()  # would overflow naive exp()
        assert sum(prices) == pytest.approx(1.0)
        assert all(math.isfinite(p) for p in prices)

    def test_invalid_index_rejected(self):
        amm = LMSRMarket(liquidity_b=100, q=[0.0, 0.0])
        with pytest.raises(AMMError):
            amm.price(5)

    def test_slippage_grows_with_size(self):
        amm = LMSRMarket(liquidity_b=100, q=[0.0, 0.0])
        small = amm.slippage(0, 10)
        large = amm.slippage(0, 500)
        assert large > small >= 0


# ==================== API integration tests ====================


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import os

    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
    # Reload config + modules that captured DATABASE_URL at import time
    import importlib

    import core.config
    importlib.reload(core.config)
    import models.database as db_mod
    importlib.reload(db_mod)
    db_mod.Base.metadata.create_all(bind=db_mod.engine)

    import api.main as main_mod
    importlib.reload(main_mod)
    with TestClient(main_mod.app) as c:
        yield c


class TestAPI:
    def test_health(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

    def test_create_and_list_market(self, client):
        res = client.post(
            "/api/v1/markets",
            json={
                "title": "Will BTC close above $100k in 2026?",
                "description": "Bitcoin year-end close",
                "outcomes": ["YES", "NO"],
                "category": "crypto",
            },
        )
        assert res.status_code == 200
        market = res.json()
        assert market["outcomes"] == ["YES", "NO"]
        assert market["prices"] == pytest.approx([0.5, 0.5])

        res = client.get("/api/v1/markets")
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_create_market_validation(self, client):
        # Duplicate outcomes rejected
        res = client.post(
            "/api/v1/markets",
            json={"title": "Test market title", "outcomes": ["YES", "yes"]},
        )
        assert res.status_code == 422

        # Bad category rejected
        res = client.post(
            "/api/v1/markets",
            json={"title": "Test market title", "outcomes": ["A", "B"], "category": "nope"},
        )
        assert res.status_code == 422

        # Title too short
        res = client.post("/api/v1/markets", json={"title": "ab", "outcomes": ["A", "B"]})
        assert res.status_code == 422

    def test_place_order_and_price_impact(self, client):
        res = client.post(
            "/api/v1/markets",
            json={"title": "Order test market", "outcomes": ["YES", "NO"]},
        )
        market_id = res.json()["id"]

        res = client.post(
            f"/api/v1/markets/{market_id}/order",
            json={"outcome_index": 0, "side": "buy", "shares": 100},
        )
        assert res.status_code == 200
        trade = res.json()
        assert trade["amount"] > 0
        assert trade["price"] > 0.5  # buying YES moves price above 50%

        # Price should now reflect the buy
        res = client.get(f"/api/v1/markets/{market_id}")
        assert res.json()["prices"][0] > 0.5

    def test_order_invalid_outcome(self, client):
        res = client.post(
            "/api/v1/markets",
            json={"title": "Invalid outcome market", "outcomes": ["A", "B"]},
        )
        market_id = res.json()["id"]
        res = client.post(
            f"/api/v1/markets/{market_id}/order",
            json={"outcome_index": 9, "side": "buy", "shares": 10},
        )
        assert res.status_code == 400

    def test_order_oversized_rejected(self, client):
        res = client.post(
            "/api/v1/markets",
            json={"title": "Oversize test market", "outcomes": ["A", "B"]},
        )
        market_id = res.json()["id"]
        res = client.post(
            f"/api/v1/markets/{market_id}/order",
            json={"outcome_index": 0, "side": "buy", "shares": 10_000_000},
        )
        assert res.status_code == 422  # schema-level max

    def test_404_unknown_market(self, client):
        res = client.get("/api/v1/markets/9999")
        assert res.status_code == 404

    def test_orderbook(self, client):
        res = client.post(
            "/api/v1/markets",
            json={"title": "Orderbook test market", "outcomes": ["A", "B"]},
        )
        market_id = res.json()["id"]
        res = client.get(f"/api/v1/markets/{market_id}/orderbook")
        assert res.status_code == 200
        body = res.json()
        assert len(body["depth"]) == 2
        assert body["depth"][0]["ladder"]

    def test_stats(self, client):
        res = client.get("/api/v1/stats")
        assert res.status_code == 200
        body = res.json()
        assert {"active_markets", "total_markets", "total_volume", "total_trades"} <= set(body)

    def test_resolve_forbidden_in_production(self, client):
        res = client.post(
            "/api/v1/markets",
            json={"title": "Resolve test market", "outcomes": ["A", "B"]},
        )
        market_id = res.json()["id"]
        res = client.post(
            f"/api/v1/markets/{market_id}/resolve",
            json={"resolver": "0x" + "a" * 40, "winning_outcome": 0},
        )
        # DEBUG defaults to false -> oracle-only
        assert res.status_code == 403