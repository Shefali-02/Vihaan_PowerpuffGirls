require("@nomicfoundation/hardhat-toolbox");
const path = require("path");
const { subtask } = require("hardhat/config");
const { TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD } = require("hardhat/builtin-tasks/task-names");

const SOLC_VERSION = "0.8.24";

// Offline fallback: with SOLC_OFFLINE=1, compile with the solc npm package (solcjs)
// instead of downloading a native compiler from binaries.soliditylang.org.
if (process.env.SOLC_OFFLINE === "1") {
  subtask(TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD, async (args, hre, runSuper) => {
    if (args.solcVersion !== SOLC_VERSION) return runSuper();
    const solc = require("solc");
    return {
      compilerPath: path.join(path.dirname(require.resolve("solc")), "soljson.js"),
      isSolcJs: true,
      version: args.solcVersion,
      longVersion: solc.version(),
    };
  });
}

/** Local-only chain for the demo. No testnet keys are committed. */
module.exports = {
  solidity: { version: SOLC_VERSION, settings: { optimizer: { enabled: true, runs: 200 } } },
  networks: {
    hardhat: { chainId: 31337 },
    localhost: { url: process.env.CHAIN_RPC_URL || "http://127.0.0.1:8545", chainId: 31337 },
  },
};
