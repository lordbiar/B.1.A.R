const { ethers } = require("hardhat");

/**
 * Deploy the BIAR Protocol contracts:
 *   1. BIAROracle  (resolution committee + dispute window)
 *   2. BIARMarket  (trading + payouts, resolved by the oracle)
 */
async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  // 1. Oracle
  const BIAROracle = await ethers.getContractFactory("BIAROracle");
  const oracle = await BIAROracle.deploy();
  await oracle.waitForDeployment();
  const oracleAddress = await oracle.getAddress();
  console.log("BIAROracle deployed to:", oracleAddress);

  // 2. Market (wired to oracle)
  const BIARMarket = await ethers.getContractFactory("BIARMarket");
  const market = await BIARMarket.deploy(oracleAddress);
  await market.waitForDeployment();
  const marketAddress = await market.getAddress();
  console.log("BIARMarket deployed to:", marketAddress);

  console.log("\nDeployment complete. Update backend .env:");
  console.log(`CONTRACT_ADDRESS=${marketAddress}`);
  console.log(`ORACLE_ADDRESS=${oracleAddress}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});