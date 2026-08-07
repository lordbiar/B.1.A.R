// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title IBIARMarket
 * @notice Core interface for BIAR Protocol prediction markets
 * @dev Handles market initialization, liquidity staking, position minting, and payout claims
 */
interface IBIARMarket {
    
    // ==================== Events ====================
    
    /// @notice Emitted when a new market is created
    event MarketCreated(
        uint256 indexed marketId,
        string title,
        address creator,
        uint256 startTime,
        uint256 endTime
    );
    
    /// @notice Emitted when liquidity is provided to a market
    event LiquidityProvided(
        uint256 indexed marketId,
        address indexed provider,
        uint256 amount,
        uint256 shares
    );
    
    /// @notice Emitted when outcome tokens are purchased
    event TokensPurchased(
        uint256 indexed marketId,
        address indexed buyer,
        string outcome,
        uint256 amountSpent,
        uint256 sharesReceived,
        uint256 price
    );
    
    /// @notice Emitted when a market is resolved
    event MarketResolved(
        uint256 indexed marketId,
        string winningOutcome,
        uint256 resolvedAt
    );
    
    /// @notice Emitted when payouts are claimed
    event PayoutClaimed(
        uint256 indexed marketId,
        address indexed claimant,
        string outcome,
        uint256 shares,
        uint256 payout
    );
    
    /// @notice Emitted when liquidity is withdrawn
    event LiquidityWithdrawn(
        uint256 indexed marketId,
        address indexed provider,
        uint256 shares,
        uint256 amount
    );
    
    // ==================== Structs ====================
    
    /// @notice Market configuration and state
    struct Market {
        uint256 id;
        string title;
        string description;
        string[] outcomes;
        uint256 startTime;
        uint256 endTime;
        bool initialized;
        bool resolved;
        string winningOutcome;
        uint256 totalLiquidity;
        uint256 totalVolume;
    }
    
    /// @notice User position in a market
    struct Position {
        uint256 shares;
        uint256 averageCost;
        bool claimed;
    }
    
    /// @notice Liquidity provider information
    struct LiquidityProvider {
        uint256 shares;
        uint256 contributed;
    }
    
    // ==================== Market Management ====================
    
    /// @notice Create a new prediction market
    /// @param _title Market title
    /// @param _description Market description
    /// @param _outcomes Array of possible outcomes (e.g., ["YES", "NO"])
    /// @param _startTime Market start timestamp
    /// @param _endTime Market end/resolution timestamp
    /// @return marketId The ID of the created market
    function createMarket(
        string calldata _title,
        string calldata _description,
        string[] calldata _outcomes,
        uint256 _startTime,
        uint256 _endTime
    ) external returns (uint256 marketId);
    
    /// @notice Initialize a market with initial liquidity
    /// @param _marketId Market ID to initialize
    /// @param _initialAmount Initial liquidity amount
    function initializeMarket(
        uint256 _marketId,
        uint256 _initialAmount
    ) external payable;
    
    /// @notice Get market details
    /// @param _marketId Market ID
    /// @return Market struct with all market data
    function getMarket(uint256 _marketId) external view returns (Market memory);
    
    /// @notice Check if market is active
    /// @param _marketId Market ID
    /// @return true if market is active and trading
    function isMarketActive(uint256 _marketId) external view returns (bool);
    
    // ==================== Trading Functions ====================
    
    /// @notice Purchase outcome tokens
    /// @param _marketId Market ID
    /// @param _outcome Outcome to purchase (e.g., "YES" or "NO")
    /// @param _amount Amount of collateral to spend
    /// @return shares Number of outcome tokens received
    function purchaseTokens(
        uint256 _marketId,
        string calldata _outcome,
        uint256 _amount
    ) external returns (uint256 shares);
    
    /// @notice Sell outcome tokens back to the market
    /// @param _marketId Market ID
    /// @param _outcome Outcome to sell
    /// @param _shares Number of shares to sell
    /// @return amount Collateral received
    function sellTokens(
        uint256 _marketId,
        string calldata _outcome,
        uint256 _shares
    ) external returns (uint256 amount);
    
    /// @notice Get current price for an outcome
    /// @param _marketId Market ID
    /// @param _outcome Outcome to price
    /// @return price Current price (0-1 with 18 decimals precision)
    function getPrice(
        uint256 _marketId,
        string calldata _outcome
    ) external view returns (uint256 price);
    
    /// @notice Calculate cost to purchase shares
    /// @param _marketId Market ID
    /// @param _outcome Outcome to purchase
    /// @param _shares Number of shares to buy
    /// @return cost Cost in collateral tokens
    function calculateCost(
        uint256 _marketId,
        string calldata _outcome,
        uint256 _shares
    ) external view returns (uint256 cost);
    
    // ==================== Liquidity Functions ====================
    
    /// @notice Provide liquidity to a market
    /// @param _marketId Market ID
    /// @param _amount Amount of collateral to provide
    /// @return shares LP shares received
    function provideLiquidity(
        uint256 _marketId,
        uint256 _amount
    ) external payable returns (uint256 shares);
    
    /// @notice Withdraw liquidity from a market
    /// @param _marketId Market ID
    /// @param _shares LP shares to burn
    /// @return amount Collateral received
    function withdrawLiquidity(
        uint256 _marketId,
        uint256 _shares
    ) external returns (uint256 amount);
    
    /// @notice Get liquidity provider info
    /// @param _marketId Market ID
    /// @param _provider Provider address
    /// @return shares LP shares held
    /// @return contributed Total collateral contributed
    function getLiquidityProviderInfo(
        uint256 _marketId,
        address _provider
    ) external view returns (uint256 shares, uint256 contributed);
    
    // ==================== Resolution & Claims ====================
    
    /// @notice Resolve a market with the winning outcome
    /// @param _marketId Market ID
    /// @param _winningOutcome The winning outcome
    /// @dev Only callable by authorized oracle
    function resolveMarket(
        uint256 _marketId,
        string calldata _winningOutcome
    ) external;
    
    /// @notice Claim payout for winning positions
    /// @param _marketId Market ID
    /// @param _outcome Outcome held by claimant
    /// @return payout Amount of collateral received
    function claimPayout(
        uint256 _marketId,
        string calldata _outcome
    ) external returns (uint256 payout);
    
    /// @notice Check if user has unclaimed payout
    /// @param _marketId Market ID
    /// @param _user User address
    /// @param _outcome Outcome held
    /// @return eligible Whether user is eligible for payout
    /// @return amount Payout amount available
    function checkPayout(
        uint256 _marketId,
        address _user,
        string calldata _outcome
    ) external view returns (bool eligible, uint256 amount);
    
    // ==================== View Functions ====================
    
    /// @notice Get user's position in a market
    /// @param _marketId Market ID
    /// @param _user User address
    /// @param _outcome Outcome
    /// @return Position struct
    function getPosition(
        uint256 _marketId,
        address _user,
        string calldata _outcome
    ) external view returns (Position memory);
    
    /// @notice Get total supply of outcome tokens
    /// @param _marketId Market ID
    /// @param _outcome Outcome
    /// @return Total supply of outcome tokens
    function getTotalSupply(
        uint256 _marketId,
        string calldata _outcome
    ) external view returns (uint256);
    
    /// @notice Get market count
    /// @return Total number of markets created
    function marketCount() external view returns (uint256);
}
