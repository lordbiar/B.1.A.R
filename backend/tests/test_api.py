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
    os.environ["JWT_SECRET"] = "test-secret-key-for-pytest-only"
    os.environ["RATE_LIMIT_REQUESTS"] = "100000"
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
        body = res.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1

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

    def test_markets_pagination(self, client):
        for i in range(5):
            client.post(
                "/api/v1/markets",
                json={"title": f"Pagination market {i}", "outcomes": ["A", "B"]},
            )
        res = client.get("/api/v1/markets?page=1&page_size=2")
        body = res.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["pages"] == 3
        res2 = client.get("/api/v1/markets?page=2&page_size=2")
        assert res2.json()["items"][0]["id"] != body["items"][0]["id"]


# ==================== auth tests ====================


class TestAuth:
    def test_nonce_and_verify_flow(self, client):
        from eth_account import Account

        acct = Account.from_key("0x" + "11" * 32)
        address = acct.address

        res = client.post("/api/v1/auth/nonce", json={"address": address})
        assert res.status_code == 200
        nonce = res.json()["nonce"]
        message = res.json()["message"]

        from eth_account.messages import encode_defunct

        signed = acct.sign_message(encode_defunct(text=message))
        res = client.post(
            "/api/v1/auth/verify",
            json={
                "address": address,
                "signature": signed.signature.hex()
                if isinstance(signed.signature.hex(), str)
                else signed.signature.hex(),
                "nonce": nonce,
            },
        )
        # eth_account returns signature with 0x prefix via .hex()
        sig = signed.signature.hex()
        if not sig.startswith("0x"):
            sig = "0x" + sig
        # retry with normalized signature (first attempt may have failed)
        if res.status_code != 200:
            res = client.post("/api/v1/auth/nonce", json={"address": address})
            nonce = res.json()["nonce"]
            message = res.json()["message"]
            signed = acct.sign_message(encode_defunct(text=message))
            sig = signed.signature.hex()
            if not sig.startswith("0x"):
                sig = "0x" + sig
            res = client.post(
                "/api/v1/auth/verify",
                json={"address": address, "signature": sig, "nonce": nonce},
            )
        assert res.status_code == 200
        token = res.json()["token"]

        res = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        assert res.json()["address"] == address.lower()

    def test_verify_bad_signature_rejected(self, client):
        res = client.post("/api/v1/auth/nonce", json={"address": "0x" + "a" * 40})
        nonce = res.json()["nonce"]
        res = client.post(
            "/api/v1/auth/verify",
            json={
                "address": "0x" + "a" * 40,
                "signature": "0x" + "f" * 130,
                "nonce": nonce,
            },
        )
        assert res.status_code == 401

    def test_verify_bad_nonce_rejected(self, client):
        res = client.post(
            "/api/v1/auth/verify",
            json={
                "address": "0x" + "a" * 40,
                "signature": "0x" + "f" * 130,
                "nonce": "bogus",
            },
        )
        assert res.status_code == 400

    def test_portfolio_requires_auth(self, client):
        res = client.get("/api/v1/portfolio")
        assert res.status_code == 401


# ==================== portfolio + limit order tests ====================


class TestTrading:
    def _auth_headers(self, client, key_byte: str = "22"):
        from eth_account import Account
        from eth_account.messages import encode_defunct

        acct = Account.from_key("0x" + key_byte * 32)
        address = acct.address
        res = client.post("/api/v1/auth/nonce", json={"address": address})
        nonce = res.json()["nonce"]
        message = res.json()["message"]
        sig = acct.sign_message(encode_defunct(text=message)).signature.hex()
        if not sig.startswith("0x"):
            sig = "0x" + sig
        res = client.post(
            "/api/v1/auth/verify",
            json={"address": address, "signature": sig, "nonce": nonce},
        )
        token = res.json()["token"]
        return {"Authorization": f"Bearer {token}"}, address

    def test_order_updates_portfolio(self, client):
        headers, address = self._auth_headers(client)
        res = client.post(
            "/api/v1/markets",
            json={"title": "Portfolio test market", "outcomes": ["YES", "NO"]},
        )
        market_id = res.json()["id"]

        res = client.post(
            f"/api/v1/markets/{market_id}/order",
            json={"outcome_index": 0, "side": "buy", "shares": 50},
            headers=headers,
        )
        assert res.status_code == 200

        res = client.get("/api/v1/portfolio", headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert body["trader"] == address.lower()
        assert len(body["positions"]) == 1
        pos = body["positions"][0]
        assert pos["shares"] == pytest.approx(50)
        assert pos["cost_basis"] > 0
        assert pos["outcome_name"] == "YES"

    def test_limit_order_rests_and_cancels(self, client):
        headers, address = self._auth_headers(client)
        res = client.post(
            "/api/v1/markets",
            json={"title": "Limit order test market", "outcomes": ["YES", "NO"]},
        )
        market_id = res.json()["id"]

        # Buy limit far below market -> rests
        res = client.post(
            f"/api/v1/markets/{market_id}/limit-order",
            json={"outcome_index": 0, "side": "buy", "quantity": 25, "limit_price": 0.10},
            headers=headers,
        )
        assert res.status_code == 200
        order = res.json()
        assert order["status"] == "open"
        assert order["filled_quantity"] == 0

        # Cancel it
        res = client.delete(f"/api/v1/limit-orders/{order['order_ref']}", headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "cancelled"

    def test_limit_order_fills_when_price_crosses(self, client):
        headers, address = self._auth_headers(client)
        res = client.post(
            "/api/v1/markets",
            json={"title": "Limit fill test market", "outcomes": ["YES", "NO"]},
        )
        market_id = res.json()["id"]

        # Buy limit above current price (0.5) -> fills immediately
        res = client.post(
            f"/api/v1/markets/{market_id}/limit-order",
            json={"outcome_index": 0, "side": "buy", "quantity": 25, "limit_price": 0.60},
            headers=headers,
        )
        assert res.status_code == 200
        order = res.json()
        assert order["status"] == "filled"
        assert order["filled_quantity"] == pytest.approx(25)

        # Portfolio should reflect the fill
        res = client.get("/api/v1/portfolio", headers=headers)
        pos = res.json()["positions"][0]
        assert pos["shares"] == pytest.approx(25)

    def test_cannot_cancel_others_order(self, client):
        headers1, _ = self._auth_headers(client, key_byte="33")
        headers2, _ = self._auth_headers(client, key_byte="44")
        res = client.post(
            "/api/v1/markets",
            json={"title": "Cancel auth test market", "outcomes": ["YES", "NO"]},
        )
        market_id = res.json()["id"]
        res = client.post(
            f"/api/v1/markets/{market_id}/limit-order",
            json={"outcome_index": 0, "side": "buy", "quantity": 10, "limit_price": 0.10},
            headers=headers1,
        )
        order_ref = res.json()["order_ref"]
        res = client.delete(f"/api/v1/limit-orders/{order_ref}", headers=headers2)
        assert res.status_code == 404

    def test_claim_winnings_flow(self, client):
        headers, address = self._auth_headers(client)
        res = client.post(
            "/api/v1/markets",
            json={"title": "Claim test market", "outcomes": ["YES", "NO"]},
        )
        market_id = res.json()["id"]
        client.post(
            f"/api/v1/markets/{market_id}/order",
            json={"outcome_index": 0, "side": "buy", "shares": 40},
            headers=headers,
        )

        # Resolve via API (DEBUG-gated): flip the settings object directly
        import core.config as config_mod

        config_mod.settings.DEBUG = True
        try:
            res = client.post(
                f"/api/v1/markets/{market_id}/resolve",
                json={"resolver": "0x" + "a" * 40, "winning_outcome": 0},
            )
            assert res.status_code == 200
        finally:
            config_mod.settings.DEBUG = False

        res = client.post(f"/api/v1/markets/{market_id}/claim", headers=headers)
        assert res.status_code == 200
        payout = res.json()["payout"]
        assert payout == pytest.approx(40)

        # Double claim pays nothing
        res = client.post(f"/api/v1/markets/{market_id}/claim", headers=headers)
        assert res.json()["payout"] == 0
