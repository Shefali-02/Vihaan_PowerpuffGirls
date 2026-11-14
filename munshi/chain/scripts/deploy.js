// Deploys AnchorRegistry with the first Hardhat account as anchorer and writes deployments/local.json.
const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function main() {
  const [anchorer] = await hre.ethers.getSigners();
  const Registry = await hre.ethers.getContractFactory("AnchorRegistry");
  const registry = await Registry.deploy(anchorer.address);
  await registry.waitForDeployment();
  const address = await registry.getAddress();
  const { chainId } = await hre.ethers.provider.getNetwork();

  // Copy the ABI next to the deployment so the API needs nothing else from this folder.
  const artifact = await hre.artifacts.readArtifact("AnchorRegistry");
  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, "AnchorRegistry.abi.json"), JSON.stringify(artifact.abi, null, 2));
  const deployment = {
    address,
    abi_path: "deployments/AnchorRegistry.abi.json",
    chain_id: Number(chainId),
    anchorer: anchorer.address,
  };
  fs.writeFileSync(path.join(outDir, "local.json"), JSON.stringify(deployment, null, 2));
  console.log("AnchorRegistry deployed:", deployment);
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
