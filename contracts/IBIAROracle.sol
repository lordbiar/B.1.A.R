// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title IBIAROracle
 * @notice Oracle interface for secure, decentralized price resolution and settlement
 * @dev Supports multiple oracle types: API feeds, Chainlink, and custom oracles
 */
interface IBIAROracle {
    
    // ==================== Events ====================
    
    /// @notice Emitted when a data feed is registered
    event FeedRegistered(
        bytes32 indexed feedId,
        string name,
        address indexed registrant,
        uint256 timestamp
    );
    
    /// @notice Emitted when market resolution data is submitted
    event ResolutionSubmitted(
        uint256 indexed marketId,
        bytes32 indexed feedId,
        bytes data,
        address indexed submitter,
        uint256 timestamp
    );
    
    /// @notice Emitted when a market is resolved via oracle
    event MarketResolved(
        uint256 indexed marketId,
        string winningOutcome,
        bytes oracleData,
        uint256 timestamp
    );
    
    /// @notice Emitted when oracle status changes
    event OracleStatusChanged(
        address indexed oracle,
        bool isActive,
        uint256 timestamp
    );
    
    /// @notice Emitted when dispute is raised
    event DisputeRaised(
        uint256 indexed marketId,
        address indexed disputer,
        string reason,
        uint256 timestamp
    );
    
    // ==================== Structs ====================
    
    /// @notice Oracle feed configuration
    struct OracleFeed {
        bytes32 id;
        string name;
        string feedType; // "api", "chainlink", "custom"
        address contractAddress;
        uint256 chainId;
        bytes config;
        bool isActive;
        uint256 lastUpdated;
    }
    
    /// @notice Resolution data for a market
    struct ResolutionData {
        uint256 marketId;
        bytes32 feedId;
        bytes data;
        address submitter;
        uint256 timestamp;
        bool confirmed;
        uint256 confirmations;
    }
    
    /// @notice Oracle operator information
    struct OracleOperator {
        address addr;
        bool isActive;
        uint256 reputation;
        uint256 submissionsCount;
    }
    
    // ==================== Feed Management ====================
    
    /// @notice Register a new oracle feed
    /// @param _name Feed name
    /// @param _feedType Type of feed ("api", "chainlink", "custom")
    /// @param _contractAddress Contract address for on-chain feeds
    /// @param _chainId Chain ID
    /// @param _config Additional configuration data
    /// @return feedId Unique identifier for the feed
    function registerFeed(
        string calldata _name,
        string calldata _feedType,
        address _contractAddress,
        uint256 _chainId,
        bytes calldata _config
    ) external returns (bytes32 feedId);
    
    /// @notice Get feed details
    /// @param _feedId Feed ID
    /// @return OracleFeed struct with feed configuration
    function getFeed(bytes32 _feedId) external view returns (OracleFeed memory);
    
    /// @notice Update feed status
    /// @param _feedId Feed ID
    /// @param _isActive New active status
    function updateFeedStatus(bytes32 _feedId, bool _isActive) external;
    
    /// @notice Get all active feeds
    /// @return Array of active feed IDs
    function getActiveFeeds() external view returns (bytes32[] memory);
    
    // ==================== Data Submission ====================
    
    /// @notice Submit resolution data for a market
    /// @param _marketId Market ID to resolve
    /// @param _feedId Feed ID used for resolution
    /// @param _data Resolution data (encoded outcome and metadata)
    function submitResolution(
        uint256 _marketId,
        bytes32 _feedId,
        bytes calldata _data
    ) external;
    
    /// @notice Confirm resolution data (for multi-sig or consensus)
    /// @param _marketId Market ID
    /// @param _confirm Whether to confirm or reject
    function confirmResolution(
        uint256 _marketId,
        bool _confirm
    ) external;
    
    /// @notice Fetch data from an API-based oracle feed
    /// @param _feedId Feed ID
    /// @param _url API endpoint URL
    /// @return Fetched data
    /// @dev This would typically be called by a keeper/off-chain service
    function fetchAPIData(
        bytes32 _feedId,
        string calldata _url
    ) external returns (bytes memory);
    
    /// @notice Get latest data from a Chainlink feed
    /// @param _feedId Feed ID
    /// @param _aggregator Chainlink aggregator address
    /// @return answer Latest round data
    /// @return updatedAt Timestamp of last update
    function getChainlinkData(
        bytes32 _feedId,
        address _aggregator
    ) external view returns (int256 answer, uint256 updatedAt);
    
    // ==================== Resolution Functions ====================
    
    /// @notice Resolve a market using oracle data
    /// @param _marketId Market ID
    /// @param _winningOutcome Winning outcome string
    /// @param _oracleData Raw oracle data
    /// @dev Only callable by authorized oracles after confirmation period
    function resolveMarket(
        uint256 _marketId,
        string calldata _winningOutcome,
        bytes calldata _oracleData
    ) external;
    
    /// @notice Get resolution data for a market
    /// @param _marketId Market ID
    /// @return ResolutionData struct
    function getResolutionData(uint256 _marketId) external view returns (ResolutionData memory);
    
    /// @notice Check if market resolution is confirmed
    /// @param _marketId Market ID
    /// @return true if resolution is confirmed and ready to execute
    function isResolutionConfirmed(uint256 _marketId) external view returns (bool);
    
    /// @notice Get required confirmation count
    /// @return Number of confirmations needed
    function requiredConfirmations() external view returns (uint256);
    
    // ==================== Oracle Management ====================
    
    /// @notice Register an oracle operator
    /// @param _oracle Oracle address
    function registerOracle(address _oracle) external;
    
    /// @notice Remove an oracle operator
    /// @param _oracle Oracle address
    function removeOracle(address _oracle) external;
    
    /// @notice Check if address is an authorized oracle
    /// @param _oracle Address to check
    /// @return true if authorized
    function isAuthorizedOracle(address _oracle) external view returns (bool);
    
    /// @notice Get oracle operator info
    /// @param _oracle Oracle address
    /// @return OracleOperator struct
    function getOracleInfo(address _oracle) external view returns (OracleOperator memory);
    
    /// @notice Update oracle reputation
    /// @param _oracle Oracle address
    /// @param _reputationChange Change in reputation (positive or negative)
    function updateReputation(address _oracle, int256 _reputationChange) external;
    
    // ==================== Dispute Resolution ====================
    
    /// @notice Raise a dispute for a market resolution
    /// @param _marketId Market ID
    /// @param _reason Reason for dispute
    /// @param _evidence Evidence data
    function raiseDispute(
        uint256 _marketId,
        string calldata _reason,
        bytes calldata _evidence
    ) external;
    
    /// @notice Resolve a dispute
    /// @param _marketId Market ID
    /// @param _upholdOriginal Whether to uphold original resolution
    /// @dev Only callable by governance or dispute resolution contract
    function resolveDispute(
        uint256 _marketId,
        bool _upholdOriginal
    ) external;
    
    /// @notice Get dispute status for a market
    /// @param _marketId Market ID
    /// @return hasDispute Whether there's an active dispute
    /// @return reason Dispute reason if exists
    function getDisputeStatus(
        uint256 _marketId
    ) external view returns (bool hasDispute, string memory reason);
    
    // ==================== View Functions ====================
    
    /// @notice Get total number of registered feeds
    /// @return Total feed count
    function feedCount() external view returns (uint256);
    
    /// @notice Get total number of oracle operators
    /// @return Total oracle count
    function oracleCount() external view returns (uint256);
    
    /// @notice Get resolution deadline for a market
    /// @param _marketId Market ID
    /// @return deadline Resolution deadline timestamp
    function getResolutionDeadline(uint256 _marketId) external view returns (uint256 deadline);
    
    /// @notice Calculate oracle fees for resolution
    /// @param _marketId Market ID
    /// @return fee Fee amount in collateral tokens
    function calculateOracleFee(uint256 _marketId) external view returns (uint256 fee);
}

/**
 * @title IChainlinkAggregator
 * @notice Minimal interface for Chainlink price feeds
 */
interface IChainlinkAggregator {
    function latestRoundData() external view returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    );
}
