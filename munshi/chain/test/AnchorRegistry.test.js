const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("AnchorRegistry", function () {
  const WS = ethers.keccak256(ethers.toUtf8Bytes("ws-pseudonym"));
  const ROOT = ethers.keccak256(ethers.toUtf8Bytes("root-1"));

  async function deploy() {
    const [anchorer, other] = await ethers.getSigners();
    const Registry = await ethers.getContractFactory("AnchorRegistry");
    const registry = await Registry.deploy(anchorer.address);
    await registry.waitForDeployment();
    return { registry, anchorer, other };
  }

  it("anchors a root and stores it", async function () {
    const { registry } = await deploy();
    await registry.anchor(WS, 1, ROOT);
    expect(await registry.rootOf(WS, 1)).to.equal(ROOT);
  });

  it("reverts when caller is not the anchorer", async function () {
    const { registry, other } = await deploy();
    await expect(registry.connect(other).anchor(WS, 1, ROOT)).to.be.revertedWithCustomError(registry, "NotAnchorer");
  });

  it("reverts on double anchor of the same slot", async function () {
    const { registry } = await deploy();
    await registry.anchor(WS, 1, ROOT);
    const other = ethers.keccak256(ethers.toUtf8Bytes("root-2"));
    await expect(registry.anchor(WS, 1, other)).to.be.revertedWithCustomError(registry, "AlreadyAnchored");
  });

  it("emits Anchored with workspace, seq and root", async function () {
    const { registry } = await deploy();
    await expect(registry.anchor(WS, 7, ROOT))
      .to.emit(registry, "Anchored")
      .withArgs(WS, 7, ROOT, (ts) => ts > 0n);
  });

  it("rejects an empty root", async function () {
    const { registry } = await deploy();
    await expect(registry.anchor(WS, 1, ethers.ZeroHash)).to.be.revertedWithCustomError(registry, "EmptyRoot");
  });
});
