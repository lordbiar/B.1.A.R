const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("BIARMarket", function () {
  let market;
  let oracle;
  let owner;
  let trader1;
  let trader2;

  beforeEach(async function () {
    [owner, trader1, trader2] = await ethers.getSigners();
    // Deploy a minimal mock oracle: the real BIAROracle requires committee
    // setup; for market tests we only need an address that can call resolve.
    const MockOracle = await ethers.getContractFactory("MockOracle");
    oracle = await MockOracle.deploy();
    await oracle.waitForDeployment();

    const BIARMarket = await ethers.getContractFactory("BIARMarket");
    market = await BIARMarket.deploy(await oracle.getAddress());
    await market.waitForDeployment();
  });

  it("creates a market", async function () {
    const endTime = (await ethers.provider.getBlock("latest")).timestamp + 86400;
    await market.createMarket("Will X happen?", ["YES", "NO"], endTime);
    const m = await market.getMarket(0);
    expect(m.title).to.equal("Will X happen?");
    expect(m.resolved).to.equal(false);
  });

  it("rejects market with < 2 outcomes", async function () {
    const endTime = (await ethers.provider.getBlock("latest")).timestamp + 86400;
    await expect(
      market.createMarket("Bad market", ["YES"], endTime)
    ).to.be.revertedWithCustomError(market, "InvalidOutcomes");
  });

  it("rejects market with past end time", async function () {
    const endTime = (await ethers.provider.getBlock("latest")).timestamp - 10;
    await expect(
      market.createMarket("Past market", ["YES", "NO"], endTime)
    ).to.be.revertedWithCustomError(market, "InvalidEndTime");
  });

  it("buys and sells shares", async function () {
    const endTime = (await ethers.provider.getBlock("latest")).timestamp + 86400;
    await market.createMarket("Trade market", ["YES", "NO"], endTime);

    await market
      .connect(trader1)
      .buyShares(0, 0, { value: ethers.parseEther("1") });
    expect(await market.getShares(0, trader1.address, 0)).to.equal(
      ethers.parseEther("1")
    );

    await market.connect(trader1).sellShares(0, 0, ethers.parseEther("0.4"));
    expect(await market.getShares(0, trader1.address, 0)).to.equal(
      ethers.parseEther("0.6")
    );
  });

  it("rejects oversell", async function () {
    const endTime = (await ethers.provider.getBlock("latest")).timestamp + 86400;
    await market.createMarket("Oversell market", ["YES", "NO"], endTime);
    await market
      .connect(trader1)
      .buyShares(0, 0, { value: ethers.parseEther("1") });
    await expect(
      market.connect(trader1).sellShares(0, 0, ethers.parseEther("2"))
    ).to.be.revertedWithCustomError(market, "InsufficientShares");
  });

  it("resolves via oracle and pays winners only", async function () {
    const endTime = (await ethers.provider.getBlock("latest")).timestamp + 86400;
    await market.createMarket("Resolve market", ["YES", "NO"], endTime);

    await market
      .connect(trader1)
      .buyShares(0, 0, { value: ethers.parseEther("1") }); // YES
    await market
      .connect(trader2)
      .buyShares(0, 1, { value: ethers.parseEther("1") }); // NO

    // Non-oracle cannot resolve
    await expect(
      market.connect(trader1).resolveMarket(0, 0)
    ).to.be.revertedWithCustomError(market, "NotOracle");

    // Oracle resolves YES
    await oracle.resolveAsOracle(await market.getAddress(), 0, 0);

    // Winner claims 1:1
    const before = await ethers.provider.getBalance(trader1.address);
    await market.connect(trader1).claimPayout(0);
    const after = await ethers.provider.getBalance(trader1.address);
    expect(after).to.be.greaterThan(before);

    // Loser cannot claim
    await expect(
      market.connect(trader2).claimPayout(0)
    ).to.be.revertedWithCustomError(market, "NothingToClaim");

    // Double claim reverts
    await expect(
      market.connect(trader1).claimPayout(0)
    ).to.be.revertedWithCustomError(market, "AlreadyClaimed");
  });
});