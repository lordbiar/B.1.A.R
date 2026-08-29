// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title BIAROracle
 * @notice Oracle for BIAR prediction market resolution with dispute window.
 * @dev Security features:
 *      - Multi-sig style committee reporting (threshold of reporters required)
 *      - Dispute period before finalization
 *      - Owner-gated reporter management with timelock-style two-step transfer
 *      - No trust in a single reporter
 */
interface IBIARMarketResolver {
    function resolveMarket(uint256 marketId, uint8 winningOutcome) external;
}

contract BIAROracle {
    // ==================== Errors ====================

    error NotOwner();
    error NotReporter();
    error AlreadyReported();
    error NotEnoughReports();
    error DisputePeriodActive();
    error NothingToFinalize();
    error InvalidOutcome();
    error ZeroAddress();

    // ==================== Events ====================

    event OutcomeReported(uint256 indexed marketId, uint8 outcome, address indexed reporter);
    event DisputeRaised(uint256 indexed marketId, address indexed disputer, string reason);
    event Finalized(uint256 indexed marketId, uint8 winningOutcome);
    event ResolutionPushed(uint256 indexed marketId, uint8 winningOutcome);

    // ==================== State ====================

    address public owner;
    address public pendingOwner;

    // Committee of authorized reporters
    mapping(address => bool) public reporters;
    uint256 public reporterCount;
    uint256 public reportThreshold; // reports needed before finalize

    // Dispute window
    uint256 public constant DISPUTE_PERIOD = 2 hours;

    struct Resolution {
        mapping(uint8 => uint256) votes; // outcome => report count
        uint8 leadingOutcome;
        uint256 leadingVotes;
        uint256 reportTime;   // when threshold was reached
        bool disputed;
        bool finalized;
        bool hasReports;
    }

    mapping(uint256 => Resolution) public resolutions;
    mapping(uint256 => mapping(address => bool)) public hasReported;

    IBIARMarketResolver public immutable market;

    constructor(address _market, uint256 _threshold) {
        if (_market == address(0)) revert ZeroAddress();
        owner = msg.sender;
        market = IBIARMarketResolver(_market);
        reportThreshold = _threshold;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier onlyReporter() {
        if (!reporters[msg.sender]) revert NotReporter();
        _;
    }

    // ==================== Admin (two-step ownership transfer) ====================

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        pendingOwner = newOwner;
    }

    function acceptOwnership() external {
        if (msg.sender != pendingOwner || pendingOwner == address(0)) revert NotOwner();
        owner = pendingOwner;
        pendingOwner = address(0);
    }

    function addReporter(address r) external onlyOwner {
        if (r == address(0)) revert ZeroAddress();
        if (!reporters[r]) {
            reporters[r] = true;
            reporterCount++;
        }
    }

    function removeReporter(address r) external onlyOwner {
        if (reporters[r]) {
            reporters[r] = false;
            reporterCount--;
        }
    }

    function setThreshold(uint256 t) external onlyOwner {
        require(t > 0 && t <= reporterCount, "bad threshold");
        reportThreshold = t;
    }

    // ==================== Reporting ====================

    function reportOutcome(uint256 marketId, uint8 outcome) external onlyReporter {
        Resolution storage r = resolutions[marketId];
        if (hasReported[marketId][msg.sender]) revert AlreadyReported();
        hasReported[marketId][msg.sender] = true;
        r.hasReports = true;

        r.votes[outcome]++;
        emit OutcomeReported(marketId, outcome, msg.sender);

        if (r.votes[outcome] > r.leadingVotes) {
            r.leadingOutcome = outcome;
            r.leadingVotes = r.votes[outcome];
        }

        if (r.leadingVotes >= reportThreshold && r.reportTime == 0) {
            r.reportTime = block.timestamp; // start dispute clock
        }
    }

    function dispute(uint256 marketId, string calldata reason) external {
        Resolution storage r = resolutions[marketId];
        if (!r.hasReports) revert NothingToFinalize();
        if (r.finalized) revert NothingToFinalize();
        r.disputed = true;
        emit DisputeRaised(marketId, msg.sender, reason);
    }

    /// @notice Finalize after dispute window passes with no dispute, then push to market.
    function finalize(uint256 marketId) external {
        Resolution storage r = resolutions[marketId];
        if (!r.hasReports || r.finalized) revert NothingToFinalize();
        if (r.disputed) revert NothingToFinalize(); // owner must re-run committee vote
        if (r.reportTime == 0) revert NotEnoughReports();
        if (block.timestamp < r.reportTime + DISPUTE_PERIOD) revert DisputePeriodActive();

        r.finalized = true;
        emit Finalized(marketId, r.leadingOutcome);

        market.resolveMarket(marketId, r.leadingOutcome);
        emit ResolutionPushed(marketId, r.leadingOutcome);
    }

    // ==================== Views ====================

    function isResolutionAuthorized(address caller) external view returns (bool) {
        return caller == address(this); // only the oracle contract itself pushes resolution
    }

    function getResolutionStatus(uint256 marketId)
        external
        view
        returns (uint8 leadingOutcome, uint256 votes, uint256 reportTime, bool disputed, bool finalized)
    {
        Resolution storage r = resolutions[marketId];
        return (r.leadingOutcome, r.leadingVotes, r.reportTime, r.disputed, r.finalized);
    }
}