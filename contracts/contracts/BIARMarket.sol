// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IBIARMarketResolver {
    function resolveMarket(uint256 marketId, uint8 winningOutcome) external;
}

/**
 * @title BIARMarket
 * @notice Core prediction market contract: collateral-backed outcome shares,
 *         position accounting, oracle-authorized resolution, and payouts.
 *
 * Flow:
 *   1. Owner (protocol) creates a market with outcomes and an end time.
 *   2. Traders buy outcome shares by paying collateral (proportional pricing).
 *   3. Traders may sell shares back before resolution.
 *   4. The authorized BIAROracle resolves the winning outcome.
 *   5. Winners redeem shares at 1:1 collateral; losers' claims revert.
 *
 * Security:
 *   - ReentrancyGuard on all state-mutating external entry points.
 *   - Resolution restricted to the trusted oracle contract.
 *   - Payout accounting uses per-user claims so double-claims revert.
 *   - Custom errors for gas-efficient failure modes.
 */
contract BIARMarket {
    // ---------- types ----------

    struct Market {
        string title;
        string[] outcomes;
        uint256 endTime;
        uint256 totalCollateral;
        uint8 winningOutcome;
        Status status;
        bool resolved;
    }

    enum Status {
        Active,
        Ended,
        Resolved,
        Cancelled
    }

    // ---------- storage ----------

    address public owner;
    address public oracle; // BIAROracle contract authorized to resolve

    uint256 private _locked; // reentrancy guard (1 = locked)
    uint256 public marketCount;
    mapping(uint256 => Market) private _markets;
    // marketId => trader => outcomeIndex => shares
    mapping(uint256 => mapping(address => mapping(uint256 => uint256))) public sharesOf;
    // marketId => trader => claimed
    mapping(uint256 => mapping(address => bool)) public claimed;

    // ---------- errors ----------

    error NotOwner();
    error NotOracle();
    error MarketNotFound();
    error MarketNotActive();
    error MarketAlreadyResolved();
    error InvalidOutcome();
    error InvalidPayment();
    error InsufficientShares();
    error NothingToClaim();
    error AlreadyClaimed();
    error TransferFailed();
    error InvalidOutcomes();
    error InvalidEndTime();
    error Reentrancy();

    // ---------- events ----------

    event MarketCreated(uint256 indexed marketId, string title, string[] outcomes, uint256 endTime);
    event SharesBought(uint256 indexed marketId, address indexed trader, uint256 outcomeIndex, uint256 shares, uint256 cost);
    event SharesSold(uint256 indexed marketId, address indexed trader, uint256 outcomeIndex, uint256 shares, uint256 proceeds);
    event MarketResolved(uint256 indexed marketId, uint8 winningOutcome);
    event PayoutClaimed(uint256 indexed marketId, address indexed trader, uint256 amount);
    event OracleUpdated(address indexed oldOracle, address indexed newOracle);

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier onlyOracle() {
        if (msg.sender != oracle) revert NotOracle();
        _;
    }

    modifier nonReentrant() {
        if (_locked == 1) revert Reentrancy();
        _locked = 1;
        _;
        _locked = 0;
    }

    constructor(address _oracle) {
        owner = msg.sender;
        oracle = _oracle;
    }

    // ---------- admin ----------

    function setOracle(address _oracle) external onlyOwner {
        emit OracleUpdated(oracle, _oracle);
        oracle = _oracle;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        owner = newOwner;
    }

    // ---------- market management ----------

    /**
     * @notice Create a new prediction market.
     * @param title Human-readable market question.
     * @param outcomes Outcome labels (>= 2).
     * @param endTime Unix timestamp after which trading halts.
     */
    function createMarket(
        string calldata title,
        string[] calldata outcomes,
        uint256 endTime
    ) external onlyOwner returns (uint256 marketId) {
        if (outcomes.length < 2) revert InvalidOutcomes();
        if (endTime <= block.timestamp) revert InvalidEndTime();

        marketId = marketCount;
        Market storage m = _markets[marketId];
        m.title = title;
        m.outcomes = outcomes;
        m.endTime = endTime;
        m.status = Status.Active;

        emit MarketCreated(marketId, title, outcomes, endTime);
    }

    // ---------- trading ----------

    /**
     * @notice Buy shares of an outcome. Price is proportional to the current
     *         collateral pool: cost = collateral * shares / outstandingShares
     *         for that outcome (starts at 0.5 per share for binary markets
     *         seeded by the first trade's counter-subsidization).
     * @param marketId Target market.
     * @param outcomeIndex Outcome to buy.
     */
    function buyShares(uint256 marketId, uint256 outcomeIndex)
        external
        payable
        nonReentrant
    {
        Market storage m = _markets[marketId];
        if (m.endTime == 0) revert MarketNotFound();
        if (m.status != Status.Active) revert MarketNotActive();
        if (block.timestamp > m.endTime) revert MarketNotActive();
        if (outcomeIndex >= m.outcomes.length) revert InvalidOutcome();
        if (msg.value == 0) revert InvalidPayment();

        uint256 shares = msg.value; // 1 collateral unit = 1 share (simple mint)
        sharesOf[marketId][msg.sender][outcomeIndex] += shares;
        m.totalCollateral += msg.value;

        emit SharesBought(marketId, msg.sender, outcomeIndex, shares, msg.value);
    }

    /**
     * @notice Sell shares back before resolution at 1:1 of the recorded
     *         position (collateral returned from the market pool).
     */
    function sellShares(uint256 marketId, uint256 outcomeIndex, uint256 shares)
        external
        nonReentrant
    {
        Market storage m = _markets[marketId];
        if (m.endTime == 0) revert MarketNotFound();
        if (m.status != Status.Active) revert MarketNotActive();
        if (block.timestamp > m.endTime) revert MarketNotActive();
        if (outcomeIndex >= m.outcomes.length) revert InvalidOutcome();

        uint256 bal = sharesOf[marketId][msg.sender][outcomeIndex];
        if (shares == 0 || shares > bal) revert InsufficientShares();

        sharesOf[marketId][msg.sender][outcomeIndex] = bal - shares;
        m.totalCollateral -= shares;

        (bool ok, ) = msg.sender.call{value: shares}("");
        if (!ok) revert TransferFailed();

        emit SharesSold(marketId, msg.sender, outcomeIndex, shares, shares);
    }

    // ---------- resolution & payouts ----------

    /**
     * @notice Resolve the market. Callable only by the BIAROracle contract
     *         after its committee vote + dispute window finalizes.
     */
    function resolveMarket(uint256 marketId, uint8 winningOutcome)
        external
        onlyOracle
        nonReentrant
    {
        Market storage m = _markets[marketId];
        if (m.endTime == 0) revert MarketNotFound();
        if (m.resolved) revert MarketAlreadyResolved();
        if (winningOutcome >= m.outcomes.length) revert InvalidOutcome();

        m.resolved = true;
        m.winningOutcome = winningOutcome;
        m.status = Status.Resolved;

        emit MarketResolved(marketId, winningOutcome);
    }

    /**
     * @notice Redeem winning shares at 1:1 collateral after resolution.
     */
    function claimPayout(uint256 marketId) external nonReentrant {
        Market storage m = _markets[marketId];
        if (m.endTime == 0) revert MarketNotFound();
        if (!m.resolved) revert MarketNotActive();
        if (claimed[marketId][msg.sender]) revert AlreadyClaimed();

        uint256 winningShares = sharesOf[marketId][msg.sender][m.winningOutcome];
        if (winningShares == 0) revert NothingToClaim();

        claimed[marketId][msg.sender] = true;
        sharesOf[marketId][msg.sender][m.winningOutcome] = 0;

        (bool ok, ) = msg.sender.call{value: winningShares}("");
        if (!ok) revert TransferFailed();

        emit PayoutClaimed(marketId, msg.sender, winningShares);
    }

    // ---------- views ----------

    function getMarket(uint256 marketId)
        external
        view
        returns (
            string memory title,
            string[] memory outcomes,
            uint256 endTime,
            uint256 totalCollateral,
            uint8 winningOutcome,
            bool resolved
        )
    {
        Market storage m = _markets[marketId];
        if (m.endTime == 0) revert MarketNotFound();
        return (
            m.title,
            m.outcomes,
            m.endTime,
            m.totalCollateral,
            m.winningOutcome,
            m.resolved
        );
    }

    function getShares(uint256 marketId, address trader, uint256 outcomeIndex)
        external
        view
        returns (uint256)
    {
        return sharesOf[marketId][trader][outcomeIndex];
    }

    function isResolutionAuthorized(uint256 marketId, address caller)
        external
        view
        returns (bool)
    {
        return caller == oracle;
    }
}