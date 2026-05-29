#!/usr/bin/env node
const { execFileSync } = require("child_process");
const path = require("path");
const os = require("os");

const platform = os.platform();
const arch = os.arch();

let binaryName;
if (platform === "darwin" && arch === "arm64") {
  binaryName = "agentassert-proxy-macos-arm64";
} else if (platform === "darwin") {
  binaryName = "agentassert-proxy-macos-x86_64";
} else if (platform === "linux") {
  binaryName = "agentassert-proxy-linux-x86_64";
} else {
  console.error(`Unsupported platform: ${platform}/${arch}. Use pip install agentassert-typec-proxy.`);
  process.exit(1);
}

const binaryPath = path.join(__dirname, "bin", binaryName);
try {
  execFileSync(binaryPath, process.argv.slice(2), { stdio: "inherit" });
} catch (e) {
  process.exit(e.status || 1);
}
