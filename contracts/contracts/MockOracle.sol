// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title MockOracle
 * @notice Test helper: lets tests push resolutions into BIARMarket as if
 *         coming from the authorized oracle contract.
 */
contract MockOracle {
    function resolveAsOracle(
        address market,
        uint256 marketId,
        uint8 winningOutcome
    ) external {
        (bool ok, ) = market.call(
            abi.encodeWithSignature("resolveMarket(uint256,uint8)", marketId, winningOutcome)
        );
        require(ok, "resolve failed");
    }
}