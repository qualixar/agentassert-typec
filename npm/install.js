#!/usr/bin/env node
const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const version = require("./package.json").version;
const platform = process.platform;
const arch = process.arch;

const binMap = {
  "darwin-arm64": "agentassert-proxy-macos-arm64",
  "darwin-x64": "agentassert-proxy-macos-x86_64",
  "linux-x64": "agentassert-proxy-linux-x86_64",
};

const key = `${platform}-${arch}`;
const binaryName = binMap[key];

if (!binaryName) {
  console.log(`No prebuilt binary for ${platform}/${arch}. Using pip fallback.`);
  process.exit(0);
}

const binDir = path.join(__dirname, "bin");
const binPath = path.join(binDir, binaryName);
if (fs.existsSync(binPath)) {
  fs.chmodSync(binPath, 0o755);
  process.exit(0);
}

const url = `https://github.com/qualixar/agentassert-typec/releases/download/v${version}/${binaryName}`;

try {
  execSync(`curl -fsSL ${url} -o ${binPath}`, { stdio: "inherit" });
  fs.chmodSync(binPath, 0o755);
  console.log(`Installed AgentAssert Type-C binary: ${binaryName}`);
} catch (e) {
  console.error("Failed to download binary. Use pip install agentassert-typec-proxy.");
  process.exit(1);
}
