"""
BIAR Protocol - Liquidity Mining & Rewards System
Incentivize market participation through rewards
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class RewardType(Enum):
    """Types of rewards"""
    TRADING_REBATE = "trading_rebate"  # % of trading fees
    LIQUIDITY_MINING = "liquidity_mining"  # For providing liquidity
    REFERRAL = "referral"  # For referrals
    MARKET_CREATION = "market_creation"  # For creating markets
    EARLY_ADOPTER = "early_adopter"  # For early users


@dataclass
class Reward:
    """Represents a single reward"""
    reward_id: str
    user_address: str
    reward_type: RewardType
    amount: float
    market_id: Optional[int] = None
    timestamp: datetime = None
    metadata: Dict = None
    claimed: bool = False
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


class LiquidityMiningPool:
    """Manages liquidity mining rewards for a market"""
    
    def __init__(self, market_id: int, annual_rate: float = 0.50):
        """
        Initialize mining pool
        
        Args:
            market_id: Market ID
            annual_rate: Annual reward rate (50% = 0.50)
        """
        self.market_id = market_id
        self.annual_rate = annual_rate
        self.total_liquidity = 0.0
        self.provider_shares: Dict[str, float] = {}  # user -> share amount
        self.last_reward_time = datetime.utcnow()
        self.cumulative_rewards: Dict[str, float] = {}
    
    def add_liquidity(self, user_address: str, amount: float) -> Tuple[bool, str]:
        """
        Add liquidity to the pool
        
        Args:
            user_address: User wallet address
            amount: Amount of liquidity to add
        
        Returns:
            (success, message)
        """
        if amount <= 0:
            return False, "Amount must be positive"
        
        self.provider_shares[user_address] = self.provider_shares.get(user_address, 0) + amount
        self.total_liquidity += amount
        
        return True, f"Added ${amount} liquidity to market {self.market_id}"
    
    def remove_liquidity(self, user_address: str, amount: float) -> Tuple[bool, str]:
        """
        Withdraw liquidity from the pool
        """
        if user_address not in self.provider_shares:
            return False, "User has no liquidity in this pool"
        
        if self.provider_shares[user_address] < amount:
            return False, "Insufficient liquidity to withdraw"
        
        self.provider_shares[user_address] -= amount
        self.total_liquidity -= amount
        
        if self.provider_shares[user_address] == 0:
            del self.provider_shares[user_address]
        
        return True, f"Withdrawn ${amount} from market {self.market_id}"
    
    def calculate_pending_rewards(self) -> Dict[str, float]:
        """
        Calculate pending rewards for all liquidity providers
        """
        if self.total_liquidity == 0:
            return {}
        
        # Time since last reward calculation
        time_elapsed = (datetime.utcnow() - self.last_reward_time).total_seconds() / (365 * 24 * 3600)
        
        # Total rewards to distribute
        total_rewards = self.total_liquidity * self.annual_rate * time_elapsed
        
        # Distribute proportionally
        pending = {}
        for user, share in self.provider_shares.items():
            user_reward = total_rewards * (share / self.total_liquidity)
            pending[user] = user_reward
        
        return pending
    
    def claim_rewards(self, user_address: str) -> Tuple[bool, float]:
        """
        Claim pending rewards
        
        Returns:
            (success, reward_amount)
        """
        if user_address not in self.provider_shares:
            return False, 0.0
        
        pending = self.calculate_pending_rewards()
        reward_amount = pending.get(user_address, 0.0)
        
        if reward_amount <= 0:
            return False, 0.0
        
        # Record cumulative rewards
        self.cumulative_rewards[user_address] = self.cumulative_rewards.get(user_address, 0) + reward_amount
        
        # Reset reward calculation time
        self.last_reward_time = datetime.utcnow()
        
        return True, reward_amount


class RewardsManager:
    """
    Central rewards management system
    Handles all reward types and distributions
    """
    
    def __init__(self):
        self.rewards: List[Reward] = []
        self.mining_pools: Dict[int, LiquidityMiningPool] = {}  # market_id -> pool
        self.user_referrals: Dict[str, List[str]] = {}  # referrer -> list of referred users
        self.trading_volume: Dict[str, float] = {}  # user -> total volume
        self.trading_fee_rate = 0.003  # 0.3%
        self.rebate_rate = 0.25  # 25% of fees back to traders
    
    # ==================== Liquidity Mining ====================
    
    def create_mining_pool(self, market_id: int, annual_rate: float = 0.50) -> LiquidityMiningPool:
        """Create a liquidity mining pool for a market"""
        pool = LiquidityMiningPool(market_id, annual_rate)
        self.mining_pools[market_id] = pool
        return pool
    
    def get_mining_pool(self, market_id: int) -> Optional[LiquidityMiningPool]:
        """Get mining pool for a market"""
        return self.mining_pools.get(market_id)
    
    # ==================== Trading Rebates ====================
    
    def record_trade(self, user_address: str, market_id: int, trade_amount: float) -> float:
        """
        Record a trade and calculate rebate
        
        Returns:
            Rebate amount in USDC
        """
        # Track volume
        self.trading_volume[user_address] = self.trading_volume.get(user_address, 0) + trade_amount
        
        # Calculate rebate
        trading_fee = trade_amount * self.trading_fee_rate
        rebate_amount = trading_fee * self.rebate_rate
        
        # Create reward
        reward = Reward(
            reward_id=f"rebate_{user_address}_{datetime.utcnow().timestamp()}",
            user_address=user_address,
            reward_type=RewardType.TRADING_REBATE,
            amount=rebate_amount,
            market_id=market_id,
            metadata={"trade_amount": trade_amount, "fee_rate": self.trading_fee_rate}
        )
        
        self.rewards.append(reward)
        return rebate_amount
    
    # ==================== Referral Rewards ====================
    
    def create_referral_link(self, referrer_address: str) -> str:
        """
        Create a referral link for a user
        Returns the referral code
        """
        if referrer_address not in self.user_referrals:
            self.user_referrals[referrer_address] = []
        
        # Simple referral code (in production, use UUIDs)
        referral_code = f"ref_{referrer_address[:8]}"
        return referral_code
    
    def process_referral(self, referrer_address: str, referred_user: str, referred_amount: float) -> Dict:
        """
        Process a referral reward
        
        Returns:
            Referral reward details
        """
        if referrer_address not in self.user_referrals:
            self.user_referrals[referrer_address] = []
        
        # Track referral
        self.user_referrals[referrer_address].append(referred_user)
        
        # Referral rewards
        referrer_reward = referred_amount * 0.05  # 5% of referred user's trading volume
        referred_reward = referred_amount * 0.02  # 2% sign-up bonus
        
        # Create referrer reward
        reward1 = Reward(
            reward_id=f"referral_{referrer_address}_{referred_user}",
            user_address=referrer_address,
            reward_type=RewardType.REFERRAL,
            amount=referrer_reward,
            metadata={"referred_user": referred_user, "referred_amount": referred_amount}
        )
        
        # Create referred user reward
        reward2 = Reward(
            reward_id=f"signup_bonus_{referred_user}",
            user_address=referred_user,
            reward_type=RewardType.REFERRAL,
            amount=referred_reward,
            metadata={"referrer": referrer_address}
        )
        
        self.rewards.append(reward1)
        self.rewards.append(reward2)
        
        return {
            "referrer_reward": referrer_reward,
            "referred_reward": referred_reward,
            "total_distributed": referrer_reward + referred_reward
        }
    
    # ==================== Market Creation Rewards ====================
    
    def reward_market_creator(self, creator_address: str, market_id: int) -> Reward:
        """
        Reward a user for creating a market
        """
        reward = Reward(
            reward_id=f"market_creation_{market_id}",
            user_address=creator_address,
            reward_type=RewardType.MARKET_CREATION,
            amount=100.0,  # $100 reward for creating a market
            market_id=market_id,
            metadata={"market_id": market_id}
        )
        
        self.rewards.append(reward)
        return reward
    
    # ==================== Early Adopter Rewards ====================
    
    def reward_early_adopter(self, user_address: str, reward_tier: int = 1) -> Reward:
        """
        Reward early adopters
        
        Tier 1: First 1000 users - $50
        Tier 2: Next 5000 users - $25
        Tier 3: Next 10000 users - $10
        """
        reward_amounts = {1: 50.0, 2: 25.0, 3: 10.0}
        amount = reward_amounts.get(reward_tier, 10.0)
        
        reward = Reward(
            reward_id=f"early_adopter_{user_address}",
            user_address=user_address,
            reward_type=RewardType.EARLY_ADOPTER,
            amount=amount,
            metadata={"tier": reward_tier}
        )
        
        self.rewards.append(reward)
        return reward
    
    # ==================== Reward Queries ====================
    
    def get_unclaimed_rewards(self, user_address: str) -> List[Reward]:
        """Get all unclaimed rewards for a user"""
        return [r for r in self.rewards 
                if r.user_address == user_address and not r.claimed]
    
    def get_total_unclaimed(self, user_address: str) -> float:
        """Get total unclaimed reward amount"""
        return sum(r.amount for r in self.get_unclaimed_rewards(user_address))
    
    def claim_all_rewards(self, user_address: str) -> Tuple[bool, float]:
        """
        Claim all pending rewards for a user
        
        Returns:
            (success, total_claimed_amount)
        """
        unclaimed = self.get_unclaimed_rewards(user_address)
        
        if not unclaimed:
            return False, 0.0
        
        total_amount = 0.0
        for reward in unclaimed:
            reward.claimed = True
            total_amount += reward.amount
        
        return True, total_amount
    
    def get_reward_summary(self, user_address: str) -> Dict:
        """Get summary of rewards for a user"""
        user_rewards = [r for r in self.rewards if r.user_address == user_address]
        
        summary = {
            "total_earned": sum(r.amount for r in user_rewards),
            "total_claimed": sum(r.amount for r in user_rewards if r.claimed),
            "total_pending": sum(r.amount for r in user_rewards if not r.claimed),
            "reward_breakdown": {}
        }
        
        # Break down by reward type
        for reward_type in RewardType:
            type_rewards = [r for r in user_rewards if r.reward_type == reward_type]
            summary["reward_breakdown"][reward_type.value] = {
                "count": len(type_rewards),
                "total": sum(r.amount for r in type_rewards)
            }
        
        return summary
    
    def get_leaderboard_by_rewards(self, limit: int = 100) -> List[Dict]:
        """
        Get leaderboard of top earners
        """
        user_totals = {}
        for reward in self.rewards:
            if reward.user_address not in user_totals:
                user_totals[reward.user_address] = {
                    "total_earned": 0.0,
                    "total_claimed": 0.0,
                    "reward_count": 0
                }
            
            user_totals[reward.user_address]["total_earned"] += reward.amount
            if reward.claimed:
                user_totals[reward.user_address]["total_claimed"] += reward.amount
            user_totals[reward.user_address]["reward_count"] += 1
        
        # Sort by total earned
        leaderboard = sorted(
            [{"address": addr, **data} for addr, data in user_totals.items()],
            key=lambda x: x["total_earned"],
            reverse=True
        )[:limit]
        
        # Add ranks
        for idx, entry in enumerate(leaderboard):
            entry["rank"] = idx + 1
        
        return leaderboard


# Global rewards manager instance
rewards_manager = RewardsManager()
