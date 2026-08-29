"""BIAR Protocol - LMSR (Logarithmic Market Scoring Rule) AMM engine.

Numerically stable implementation using the log-sum-exp trick to avoid
overflow/underflow with large share quantities. All prices are in [0, 1]
and sum to 1 across outcomes.
"""
import math
from dataclasses import dataclass, field

from core.config import settings


class AMMError(Exception):
    """Raised for invalid AMM operations."""


@dataclass
class LMSRMarket:
    """State of a single LMSR market."""

    liquidity_b: float = field(default_factory=lambda: settings.LMSR_LIQUIDITY_B)
    # q[i] = number of outstanding shares of outcome i
    q: list[float] = field(default_factory=list)

    def __post_init__(self):
        if self.liquidity_b <= 0:
            raise AMMError("Liquidity parameter b must be positive")
        if not self.q:
            self.q = [0.0, 0.0]  # default binary market

    # ---------- core math ----------

    def _cost(self, q: list[float]) -> float:
        """LMSR cost function C(q) = b * ln(sum(exp(q_i / b))), stable via log-sum-exp."""
        # Scale shares by b BEFORE the log-sum-exp trick, otherwise the
        # stabilization is applied to the wrong quantity and costs explode.
        scaled = [x / self.liquidity_b for x in q]
        m = max(scaled)
        # log-sum-exp: m + ln(sum(exp(x_i - m))) avoids overflow
        return self.liquidity_b * (m + math.log(sum(math.exp(x - m) for x in scaled)))

    def _validate_index(self, outcome_index: int) -> None:
        if not 0 <= outcome_index < len(self.q):
            raise AMMError(f"Invalid outcome index {outcome_index}")

    # ---------- public API ----------

    def prices(self) -> list[float]:
        """Instantaneous prices p_i = exp(q_i / b) / sum(exp(q_j / b)), stable."""
        scaled = [x / self.liquidity_b for x in self.q]
        m = max(scaled)
        exps = [math.exp(x - m) for x in scaled]
        total = sum(exps)
        return [e / total for e in exps]

    def price(self, outcome_index: int) -> float:
        self._validate_index(outcome_index)
        return self.prices()[outcome_index]

    def buy_cost(self, outcome_index: int, shares: float) -> float:
        """Cost to buy `shares` of an outcome (price impact included)."""
        self._validate_index(outcome_index)
        if shares <= 0:
            raise AMMError("Shares must be positive")
        new_q = list(self.q)
        new_q[outcome_index] += shares
        return self._cost(new_q) - self._cost(self.q)

    def sell_proceeds(self, outcome_index: int, shares: float) -> float:
        """Proceeds from selling `shares` back to the AMM."""
        self._validate_index(outcome_index)
        if shares <= 0:
            raise AMMError("Shares must be positive")
        if shares > self.q[outcome_index]:
            raise AMMError("Cannot sell more shares than outstanding for this outcome")
        new_q = list(self.q)
        new_q[outcome_index] -= shares
        return max(0.0, self._cost(self.q) - self._cost(new_q))

    def execute_buy(self, outcome_index: int, shares: float) -> float:
        """Apply a buy; returns the cost charged."""
        cost = self.buy_cost(outcome_index, shares)
        self.q[outcome_index] += shares
        return cost

    def execute_sell(self, outcome_index: int, shares: float) -> float:
        """Apply a sell; returns the proceeds paid out."""
        proceeds = self.sell_proceeds(outcome_index, shares)
        self.q[outcome_index] -= shares
        return proceeds

    def price_for_shares(self, outcome_index: int, shares: float) -> float:
        """Average (effective) price per share for buying `shares`."""
        cost = self.buy_cost(outcome_index, shares)
        return cost / shares

    def slippage(self, outcome_index: int, shares: float) -> float:
        """Slippage vs. current spot price, as a fraction (0 = none)."""
        spot = self.price(outcome_index)
        effective = self.price_for_shares(outcome_index, shares)
        if spot <= 0:
            return 0.0
        return max(0.0, (effective - spot) / spot)

    def assert_trade_allowed(self, outcome_index: int, shares: float) -> None:
        """Guard rails: cap slippage and trade size to protect users."""
        if shares > settings.MAX_TRADE_AMOUNT:
            raise AMMError(f"Trade exceeds max size {settings.MAX_TRADE_AMOUNT}")
        slip = self.slippage(outcome_index, shares)
        if slip > settings.MAX_SLIPPAGE:
            raise AMMError(
                f"Slippage {slip:.2%} exceeds maximum allowed "
                f"{settings.MAX_SLIPPAGE:.2%}. Reduce trade size."
            )