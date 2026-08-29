"""BIAR Protocol - Market service: business logic between API and DB/AMM."""
import datetime
import json
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.amm import AMMError, LMSRMarket
from core.config import settings
from models.database import LimitOrderModel, MarketModel, PositionModel, TradeModel
from schemas.market import LimitOrderRequest, MarketCreate, OrderRequest


class MarketNotFound(Exception):
    pass


class MarketResolvedError(Exception):
    pass


class MarketService:
    """Encapsulates all market operations with AMM state management."""

    def __init__(self, db: Session):
        self.db = db

    # ---------- helpers ----------

    def _get_market(self, market_id: int) -> MarketModel:
        m = self.db.get(MarketModel, market_id)
        if m is None:
            raise MarketNotFound(f"Market {market_id} not found")
        return m

    def _load_amm(self, market: MarketModel) -> LMSRMarket:
        q = json.loads(market.q_vector)
        return LMSRMarket(liquidity_b=market.liquidity_b, q=q)

    def _save_amm(self, market: MarketModel, amm: LMSRMarket) -> None:
        market.q_vector = json.dumps(amm.q)

    # ---------- market CRUD ----------

    def create_market(self, data: MarketCreate) -> MarketModel:
        end_time = None
        if data.end_time:
            try:
                end_time = datetime.datetime.fromisoformat(
                    data.end_time.replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except ValueError:
                raise ValueError("end_time must be ISO 8601 format")
            now = datetime.datetime.utcnow()
            if end_time <= now:
                raise ValueError("end_time must be in the future")
            # Markets must resolve within a short window (hours to ~1 day)
            min_duration = datetime.timedelta(hours=settings.MIN_MARKET_DURATION_HOURS)
            max_duration = datetime.timedelta(hours=settings.MAX_MARKET_DURATION_HOURS)
            if end_time - now < min_duration:
                raise ValueError(
                    f"end_time must be at least {settings.MIN_MARKET_DURATION_HOURS:g} hour(s) in the future"
                )
            if end_time - now > max_duration:
                raise ValueError(
                    f"end_time must be within {settings.MAX_MARKET_DURATION_HOURS:g} hour(s) of creation"
                )

        market = MarketModel(
            title=data.title.strip(),
            description=data.description.strip(),
            category=data.category,
            outcomes=json.dumps(data.outcomes),
            creator=data.creator,
            end_time=end_time,
            liquidity_b=settings.LMSR_LIQUIDITY_B,
            q_vector=json.dumps([0.0] * len(data.outcomes)),
        )
        self.db.add(market)
        self.db.commit()
        self.db.refresh(market)
        return market

    def list_markets(
        self,
        category: str | None = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 20,
    ):
        stmt = select(MarketModel).order_by(MarketModel.created_at.desc())
        if active_only:
            stmt = stmt.where(MarketModel.resolved.is_(False))
        if category:
            stmt = stmt.where(MarketModel.category == category)
        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        items = (
            self.db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
            .scalars()
            .all()
        )
        return items, total, page, page_size

    def get_market(self, market_id: int) -> MarketModel:
        return self._get_market(market_id)

    def get_prices(self, market: MarketModel) -> list[float]:
        return self._load_amm(market).prices()

    # ---------- trading ----------

    def place_order(self, market_id: int, order: OrderRequest) -> TradeModel:
        market = self._get_market(market_id)
        if market.resolved:
            raise MarketResolvedError("Market is already resolved")
        if market.end_time and datetime.datetime.utcnow() > market.end_time:
            raise MarketResolvedError("Market has ended")

        outcomes = json.loads(market.outcomes)
        if order.outcome_index >= len(outcomes):
            raise AMMError("Invalid outcome index")

        amm = self._load_amm(market)

        # Enforce user-specified slippage cap if provided
        if order.max_slippage is not None:
            slip = amm.slippage(order.outcome_index, order.shares)
            if slip > order.max_slippage:
                raise AMMError(
                    f"Slippage {slip:.2%} exceeds your limit {order.max_slippage:.2%}"
                )

        # Protocol-level guard rails
        amm.assert_trade_allowed(order.outcome_index, order.shares)

        if order.side == "buy":
            amount = amm.execute_buy(order.outcome_index, order.shares)
        else:
            amount = amm.execute_sell(order.outcome_index, order.shares)

        price = amount / order.shares
        market.total_volume += amount
        self._save_amm(market, amm)

        trade = TradeModel(
            market_id=market.id,
            trader=order.trader,
            outcome_index=order.outcome_index,
            side=order.side,
            shares=order.shares,
            amount=amount,
            price=price,
        )
        self.db.add(trade)
        self._update_position(market, order, order.shares, amount, price)
        self.db.commit()
        self.db.refresh(trade)
        return trade

    # ---------- positions ----------

    def _update_position(
        self,
        market: MarketModel,
        order: OrderRequest,
        shares: float,
        amount: float,
        price: float,
    ) -> None:
        """Apply a fill to the trader's net position (weighted-average cost)."""
        pos = self.db.execute(
            select(PositionModel).where(
                PositionModel.trader == order.trader,
                PositionModel.market_id == market.id,
                PositionModel.outcome_index == order.outcome_index,
            )
        ).scalar_one_or_none()

        if pos is None:
            pos = PositionModel(
                trader=order.trader,
                market_id=market.id,
                outcome_index=order.outcome_index,
                shares=0.0,
                cost_basis=0.0,
                realized_pnl=0.0,
            )
            self.db.add(pos)

        if order.side == "buy":
            pos.shares += shares
            pos.cost_basis += amount
        else:
            sell_shares = min(shares, pos.shares)
            if pos.shares > 0:
                avg = pos.cost_basis / pos.shares
                cost = avg * sell_shares
                pos.realized_pnl += amount - cost
                pos.cost_basis = max(0.0, pos.cost_basis - cost)
            pos.shares = max(0.0, pos.shares - sell_shares)
            if pos.shares == 0:
                pos.cost_basis = 0.0

    def get_portfolio(self, trader: str) -> dict:
        """Full portfolio with live marks and claimable winnings."""
        positions = (
            self.db.execute(
                select(PositionModel).where(PositionModel.trader == trader)
            )
            .scalars()
            .all()
        )

        out = []
        total_value = total_cost = total_unrealized = total_realized = 0.0
        for pos in positions:
            if pos.shares <= 0 and pos.realized_pnl == 0:
                continue
            market = self.db.get(MarketModel, pos.market_id)
            if market is None:
                continue
            outcomes = json.loads(market.outcomes)
            prices = self._load_amm(market).prices()
            current_price = (
                prices[pos.outcome_index] if pos.outcome_index < len(prices) else 0.0
            )

            winning = market.resolved and market.winning_outcome == pos.outcome_index
            claimable = 0.0
            if winning and not pos.claimed and pos.shares > 0:
                claimable = pos.shares * 1.0  # winning shares redeem at $1.00

            value = pos.shares * current_price
            unrealized = value - pos.cost_basis
            out.append(
                {
                    "market_id": market.id,
                    "market_title": market.title,
                    "outcome_index": pos.outcome_index,
                    "outcome_name": outcomes[pos.outcome_index]
                    if pos.outcome_index < len(outcomes)
                    else "?",
                    "shares": round(pos.shares, 6),
                    "cost_basis": round(pos.cost_basis, 6),
                    "avg_price": round(pos.cost_basis / pos.shares, 6)
                    if pos.shares > 0
                    else 0.0,
                    "current_price": round(current_price, 6),
                    "value": round(value, 6),
                    "unrealized_pnl": round(unrealized, 6),
                    "realized_pnl": round(pos.realized_pnl, 6),
                    "resolved": market.resolved,
                    "winning": winning,
                    "claimable": round(claimable, 6),
                }
            )
            total_value += value
            total_cost += pos.cost_basis
            total_unrealized += unrealized
            total_realized += pos.realized_pnl

        return {
            "trader": trader,
            "positions": out,
            "total_value": round(total_value, 6),
            "total_cost_basis": round(total_cost, 6),
            "total_unrealized_pnl": round(total_unrealized, 6),
            "total_realized_pnl": round(total_realized, 6),
        }

    def claim_winnings(self, trader: str, market_id: int) -> dict:
        """Redeem winning shares at $1.00 after resolution."""
        market = self._get_market(market_id)
        if not market.resolved:
            raise ValueError("Market is not resolved yet")

        positions = (
            self.db.execute(
                select(PositionModel).where(
                    PositionModel.trader == trader,
                    PositionModel.market_id == market_id,
                )
            )
            .scalars()
            .all()
        )

        payout = 0.0
        for pos in positions:
            if pos.claimed:
                continue
            if market.winning_outcome == pos.outcome_index and pos.shares > 0:
                payout += pos.shares * 1.0
                pos.realized_pnl += pos.shares * 1.0 - pos.cost_basis
                pos.cost_basis = 0.0
                pos.shares = 0.0
            pos.claimed = True
        self.db.commit()
        return {"market_id": market_id, "trader": trader, "payout": round(payout, 6)}

    # ---------- limit orders ----------

    def place_limit_order(
        self, market_id: int, trader: str, req: LimitOrderRequest
    ) -> LimitOrderModel:
        market = self._get_market(market_id)
        if market.resolved:
            raise MarketResolvedError("Market is already resolved")
        if market.end_time and datetime.datetime.utcnow() > market.end_time:
            raise MarketResolvedError("Market has ended")

        outcomes = json.loads(market.outcomes)
        if req.outcome_index >= len(outcomes):
            raise AMMError("Invalid outcome index")

        expires_at = None
        if req.expires_at:
            try:
                expires_at = datetime.datetime.fromisoformat(
                    req.expires_at.replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except ValueError:
                raise ValueError("expires_at must be ISO 8601 format")
            if expires_at <= datetime.datetime.utcnow():
                raise ValueError("expires_at must be in the future")

        order = LimitOrderModel(
            order_ref=secrets.token_hex(16),
            market_id=market.id,
            trader=trader,
            outcome_index=req.outcome_index,
            side=req.side,
            quantity=req.quantity,
            limit_price=req.limit_price,
            expires_at=expires_at,
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

        # Try immediate fill against the AMM if price already crossed
        self._try_fill_limit_order(order, market)
        return order

    def _try_fill_limit_order(
        self, order: LimitOrderModel, market: MarketModel
    ) -> None:
        """Fill a resting order (fully or partially) when the AMM price crosses
        the limit. Buys fill when price <= limit; sells fill when price >= limit."""
        if order.status in ("filled", "cancelled", "expired"):
            return
        amm = self._load_amm(market)
        prices = amm.prices()
        current = prices[order.outcome_index]

        remaining = order.quantity - order.filled_quantity
        crossed = (order.side == "buy" and current <= order.limit_price) or (
            order.side == "sell" and current >= order.limit_price
        )
        if not crossed or remaining <= 0:
            if order.filled_quantity > 0:
                order.status = "partial"
            return

        fill_shares = remaining
        try:
            amm.assert_trade_allowed(order.outcome_index, fill_shares)
            if order.side == "buy":
                amount = amm.execute_buy(order.outcome_index, fill_shares)
            else:
                amount = amm.execute_sell(order.outcome_index, fill_shares)
        except AMMError:
            if order.filled_quantity > 0:
                order.status = "partial"
            return

        price = amount / fill_shares
        market.total_volume += amount
        self._save_amm(market, amm)

        trade = TradeModel(
            market_id=market.id,
            trader=order.trader,
            outcome_index=order.outcome_index,
            side=order.side,
            shares=fill_shares,
            amount=amount,
            price=price,
        )
        self.db.add(trade)
        self._update_position(
            market,
            OrderRequest(
                trader=order.trader,
                outcome_index=order.outcome_index,
                side=order.side,
                shares=fill_shares,
            ),
            fill_shares,
            amount,
            price,
        )
        order.filled_quantity += fill_shares
        order.status = "filled"
        self.db.commit()

    def match_limit_orders(self, market_id: int) -> list[dict]:
        """Run the matching loop for all open orders on a market."""
        market = self._get_market(market_id)
        open_orders = (
            self.db.execute(
                select(LimitOrderModel).where(
                    LimitOrderModel.market_id == market_id,
                    LimitOrderModel.status.in_(["open", "partial"]),
                )
            )
            .scalars()
            .all()
        )

        filled = []
        for order in open_orders:
            if order.expires_at and datetime.datetime.utcnow() > order.expires_at:
                order.status = "expired"
                continue
            before = order.filled_quantity
            self._try_fill_limit_order(order, market)
            if order.filled_quantity > before:
                filled.append(
                    {
                        "order_ref": order.order_ref,
                        "filled_quantity": order.filled_quantity,
                        "status": order.status,
                    }
                )
        self.db.commit()
        return filled

    def cancel_limit_order(self, order_ref: str, trader: str) -> bool:
        """Cancel an order. Only the owner may cancel."""
        order = self.db.execute(
            select(LimitOrderModel).where(LimitOrderModel.order_ref == order_ref)
        ).scalar_one_or_none()
        if order is None or order.trader != trader:
            return False
        if order.status in ("filled", "cancelled", "expired"):
            return False
        order.status = "cancelled"
        self.db.commit()
        return True

    def list_limit_orders(self, market_id: int, trader: str | None = None) -> list:
        stmt = (
            select(LimitOrderModel)
            .where(
                LimitOrderModel.market_id == market_id,
                LimitOrderModel.status.in_(["open", "partial"]),
            )
            .order_by(LimitOrderModel.created_at.desc())
        )
        if trader:
            stmt = stmt.where(LimitOrderModel.trader == trader)
        return list(self.db.execute(stmt).scalars().all())

    # ---------- resolution ----------

    def resolve_market(self, market_id: int, winning_outcome: int) -> MarketModel:
        market = self._get_market(market_id)
        if market.resolved:
            raise MarketResolvedError("Market already resolved")
        outcomes = json.loads(market.outcomes)
        if not 0 <= winning_outcome < len(outcomes):
            raise ValueError("winning_outcome index out of range")
        market.resolved = True
        market.winning_outcome = winning_outcome
        self.db.commit()
        self.db.refresh(market)
        return market

    # ---------- stats ----------

    def get_stats(self) -> dict:
        total_markets = self.db.execute(
            select(func.count(MarketModel.id))
        ).scalar_one()
        active_markets = self.db.execute(
            select(func.count(MarketModel.id)).where(MarketModel.resolved.is_(False))
        ).scalar_one()
        total_volume = self.db.execute(
            select(func.coalesce(func.sum(MarketModel.total_volume), 0.0))
        ).scalar_one()
        total_trades = self.db.execute(select(func.count(TradeModel.id))).scalar_one()
        return {
            "active_markets": active_markets,
            "total_markets": total_markets,
            "total_volume": round(total_volume, 2),
            "total_trades": total_trades,
        }

    def get_orderbook(self, market_id: int) -> dict:
        market = self._get_market(market_id)
        outcomes = json.loads(market.outcomes)
        amm = self._load_amm(market)
        prices = amm.prices()

        # Depth ladder: cost to buy increasing share sizes per outcome
        sizes = [10, 50, 100, 500]
        depth = []
        for i, name in enumerate(outcomes):
            ladder = []
            for s in sizes:
                try:
                    cost = amm.buy_cost(i, s)
                    ladder.append(
                        {"shares": s, "cost": round(cost, 4), "avg_price": round(cost / s, 4)}
                    )
                except AMMError:
                    break
            depth.append({"outcome": name, "price": round(prices[i], 4), "ladder": ladder})

        return {
            "market_id": market.id,
            "outcomes": outcomes,
            "prices": [round(p, 4) for p in prices],
            "depth": depth,
        }