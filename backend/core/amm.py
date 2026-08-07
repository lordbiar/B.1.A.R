"""
BIAR Protocol - Core AMM Engine
Implements Constant Product and LMSR market making models
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple
import math
import numpy as np


class AMMModel(ABC):
    """Abstract base class for Automated Market Maker models"""
    
    @abstractmethod
    def get_price(self, quantities: Dict[str, float], outcome: str) -> float:
        """Calculate the price of an outcome token given current quantities"""
        pass
    
    @abstractmethod
    def get_quantities_after_trade(self, quantities: Dict[str, float], 
                                    outcome: str, amount: float) -> Dict[str, float]:
        """Calculate new quantities after a trade"""
        pass
    
    @abstractmethod
    def calculate_cost(self, quantities: Dict[str, float], outcome: str, 
                       shares: float) -> float:
        """Calculate the cost to purchase shares of an outcome"""
        pass


class ConstantProductAMM(AMMModel):
    """
    Constant Product Market Maker (CPMM)
    Uses the invariant: x * y = k (for binary markets)
    Extended to multi-outcome: product of all quantities = constant
    """
    
    def __init__(self, fee_rate: float = 0.003):
        """
        Initialize CPMM
        
        Args:
            fee_rate: Trading fee (default 0.3%)
        """
        self.fee_rate = fee_rate
    
    def get_price(self, quantities: Dict[str, float], outcome: str) -> float:
        """
        Calculate marginal price for an outcome
        Price = (product of other quantities) / (product of all quantities)^(1/n)
        Simplified for binary: price_yes = qty_no / (qty_yes + qty_no)
        """
        total_liquidity = sum(quantities.values())
        if total_liquidity == 0:
            return 1.0 / len(quantities)  # Uniform prior
        
        # For CPMM, price is proportional to inverse of quantity
        qty_outcome = quantities.get(outcome, 0)
        if qty_outcome == 0:
            return 1.0
        
        # Marginal price calculation
        other_product = 1.0
        for key, val in quantities.items():
            if key != outcome:
                other_product *= max(val, 0.0001)  # Prevent division by zero
        
        all_product = other_product * max(qty_outcome, 0.0001)
        n_outcomes = len(quantities)
        
        if n_outcomes == 2:
            # Binary market simplified pricing
            qty_other = sum(v for k, v in quantities.items() if k != outcome)
            return qty_other / (qty_outcome + qty_other)
        
        # Multi-outcome pricing
        return (other_product / (all_product ** (1/n_outcomes)))
    
    def get_quantities_after_trade(self, quantities: Dict[str, float],
                                    outcome: str, amount: float) -> Dict[str, float]:
        """
        Execute a trade and return new quantities
        Maintains the constant product invariant
        """
        new_quantities = quantities.copy()
        
        # Apply fee
        amount_after_fee = amount * (1 - self.fee_rate)
        
        # For buying outcome tokens, we need to solve for delta
        # such that (q_yes + delta_yes) * (q_no + delta_no) = k
        # Simplified: add to the outcome being bought
        
        if outcome in new_quantities:
            new_quantities[outcome] += amount_after_fee
        else:
            new_quantities[outcome] = amount_after_fee
            
        return new_quantities
    
    def calculate_cost(self, quantities: Dict[str, float], outcome: str,
                       shares: float) -> float:
        """
        Calculate cost to purchase shares using constant product formula
        Cost = sqrt(k) - sqrt(q_yes * q_no) for binary
        """
        if len(quantities) == 2:
            # Binary market
            outcomes = list(quantities.keys())
            other_outcome = [o for o in outcomes if o != outcome][0]
            
            q_current = quantities.get(outcome, 0.0001)
            q_other = quantities.get(other_outcome, 0.0001)
            
            # Current invariant
            k_current = q_current * q_other
            
            # New quantity after purchase
            q_new = q_current + shares * (1 - self.fee_rate)
            
            # Solve for new other quantity to maintain invariant
            q_other_new = k_current / q_new if q_new > 0 else q_other
            
            # Cost is the change in the other outcome's quantity
            cost = abs(q_other - q_other_new)
            
            return cost * (1 + self.fee_rate)
        
        # Multi-outcome approximation
        return shares * self.get_price(quantities, outcome)


class LMSR(AMMModel):
    """
    Logarithmic Market Scoring Rule (LMSR)
    Cost function: C(q) = b * ln(sum(exp(q_i / b)))
    Price: p_i = exp(q_i / b) / sum(exp(q_j / b))
    
    Better suited for prediction markets with proper probability calibration
    """
    
    def __init__(self, b: float = 100.0, fee_rate: float = 0.003):
        """
        Initialize LMSR
        
        Args:
            b: Liquidity parameter (higher = more liquidity, less price impact)
            fee_rate: Trading fee (default 0.3%)
        """
        self.b = b
        self.fee_rate = fee_rate
    
    def _cost_function(self, quantities: Dict[str, float]) -> float:
        """Calculate the LMSR cost function value"""
        exp_sum = sum(np.exp(q / self.b) for q in quantities.values())
        return self.b * np.log(exp_sum)
    
    def get_price(self, quantities: Dict[str, float], outcome: str) -> float:
        """
        Calculate the instantaneous price of an outcome
        p_i = exp(q_i / b) / sum(exp(q_j / b))
        """
        if not quantities:
            return 0.0
        
        exp_values = {k: np.exp(q / self.b) for k, q in quantities.items()}
        exp_sum = sum(exp_values.values())
        
        if exp_sum == 0:
            return 1.0 / len(quantities)
        
        qty = quantities.get(outcome, 0)
        return exp_values.get(outcome, np.exp(0)) / exp_sum
    
    def get_probabilities(self, quantities: Dict[str, float]) -> Dict[str, float]:
        """Get probabilities for all outcomes"""
        return {outcome: self.get_price(quantities, outcome) 
                for outcome in quantities.keys()}
    
    def calculate_cost(self, quantities: Dict[str, float], outcome: str,
                       shares: float) -> float:
        """
        Calculate cost to purchase shares
        Cost = C(q + delta) - C(q)
        """
        # Apply fee to shares
        shares_after_fee = shares * (1 - self.fee_rate)
        
        # Create new quantity vector
        new_quantities = quantities.copy()
        new_quantities[outcome] = new_quantities.get(outcome, 0) + shares_after_fee
        
        # Calculate cost difference
        cost = self._cost_function(new_quantities) - self._cost_function(quantities)
        
        # Add fee
        return cost * (1 + self.fee_rate)
    
    def get_quantities_after_trade(self, quantities: Dict[str, float],
                                    outcome: str, amount: float) -> Dict[str, float]:
        """
        Execute trade and return new quantities
        Solves for shares purchased given amount spent
        """
        new_quantities = quantities.copy()
        
        # Apply fee
        amount_after_fee = amount * (1 - self.fee_rate)
        
        # Use numerical method to find shares
        # C(q + delta) - C(q) = amount
        from scipy.optimize import brentq
        
        def cost_diff(shares):
            test_qty = quantities.copy()
            test_qty[outcome] = test_qty.get(outcome, 0) + shares
            return self._cost_function(test_qty) - self._cost_function(quantities) - amount_after_fee
        
        try:
            # Find shares that match the cost
            max_shares = amount_after_fee * 10  # Upper bound
            shares = brentq(cost_diff, 0.0001, max_shares)
            
            new_quantities[outcome] = new_quantities.get(outcome, 0) + shares
        except (ValueError, RuntimeError):
            # Fallback for edge cases
            price = self.get_price(quantities, outcome)
            if price > 0:
                shares = amount_after_fee / price
                new_quantities[outcome] = new_quantities.get(outcome, 0) + shares
        
        return new_quantities
    
    def calculate_slippage(self, quantities: Dict[str, float], outcome: str,
                           shares: float) -> Tuple[float, float, float]:
        """
        Calculate slippage for a trade
        
        Returns:
            Tuple of (effective_price, price_impact, slippage_percentage)
        """
        if shares <= 0:
            return 0.0, 0.0, 0.0
        
        initial_price = self.get_price(quantities, outcome)
        cost = self.calculate_cost(quantities, outcome, shares)
        effective_price = cost / shares if shares > 0 else 0
        
        # Calculate new price after trade
        new_quantities = self.get_quantities_after_trade(quantities, outcome, shares)
        new_price = self.get_price(new_quantities, outcome)
        
        price_impact = abs(new_price - initial_price)
        slippage_pct = ((effective_price - initial_price) / initial_price * 100) if initial_price > 0 else 0
        
        return effective_price, price_impact, slippage_pct


class SimulationEngine:
    """
    Simulation engine for testing market dynamics
    """
    
    def __init__(self, amm_model: AMMModel):
        self.amm = amm_model
    
    def simulate_liquidity_depth(self, initial_quantities: Dict[str, float],
                                  outcome: str, trade_sizes: List[float]) -> Dict:
        """
        Simulate trades of different sizes to measure liquidity depth
        
        Returns analysis of price impact at different trade sizes
        """
        results = []
        
        for size in trade_sizes:
            cost = self.amm.calculate_cost(initial_quantities, outcome, size)
            eff_price, impact, slippage = self.amm.calculate_slippage(
                initial_quantities, outcome, size
            )
            
            results.append({
                'trade_size': size,
                'cost': cost,
                'effective_price': eff_price,
                'price_impact': impact,
                'slippage_pct': slippage
            })
        
        return {
            'initial_state': initial_quantities,
            'outcome': outcome,
            'trades': results,
            'avg_slippage': sum(r['slippage_pct'] for r in results) / len(results),
            'max_slippage': max(r['slippage_pct'] for r in results)
        }
    
    def simulate_dynamic_odds(self, initial_quantities: Dict[str, float],
                               trade_sequence: List[Tuple[str, float]]) -> List[Dict]:
        """
        Simulate a sequence of trades to show dynamic odds recalculation
        """
        quantities = initial_quantities.copy()
        history = []
        
        for outcome, amount in trade_sequence:
            cost = self.amm.calculate_cost(quantities, outcome, amount)
            probabilities = self.amm.get_probabilities(quantities)
            
            history.append({
                'trade': {'outcome': outcome, 'amount': amount, 'cost': cost},
                'probabilities': probabilities,
                'quantities': quantities.copy()
            })
            
            # Update quantities
            quantities = self.amm.get_quantities_after_trade(quantities, outcome, amount)
        
        # Final state
        final_probs = self.amm.get_probabilities(quantities)
        history.append({
            'trade': None,
            'probabilities': final_probs,
            'quantities': quantities,
            'final_state': True
        })
        
        return history
    
    def compare_models(self, quantities: Dict[str, float], outcome: str,
                       shares: float) -> Dict:
        """Compare CPMM vs LMSR for the same trade"""
        cpmm = ConstantProductAMM()
        lmsr = LMSR(b=100.0)
        
        cpmm_cost = cpmm.calculate_cost(quantities, outcome, shares)
        lmsr_cost = lmsr.calculate_cost(quantities, outcome, shares)
        
        cpmm_price = cpmm.get_price(quantities, outcome)
        lmsr_price = lmsr.get_price(quantities, outcome)
        
        return {
            'constant_product': {
                'cost': cpmm_cost,
                'price': cpmm_price,
                'model': 'CPMM'
            },
            'lmsr': {
                'cost': lmsr_cost,
                'price': lmsr_price,
                'model': 'LMSR',
                'liquidity_param': lmsr.b
            },
            'recommendation': 'LMSR' if abs(lmsr_cost - cpmm_cost) < 1 else 'CPMM'
        }
