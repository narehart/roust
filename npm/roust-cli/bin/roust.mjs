#!/usr/bin/env node
/**
 * Thin launcher: resolve the platform binary npm installed through
 * optionalDependencies and exec it, forwarding argv, stdio, and exit code.
 *
 * There is no runtime download and no postinstall step. If the platform
 * package is missing (an unsupported platform, or --no-optional), we say so
 * and point at the other install paths rather than silently fetching a binary
 * over the network.
 */
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

const PLATFORM_PACKAGES = {
  "darwin-x64": "roust-darwin-x64",
  "darwin-arm64": "roust-darwin-arm64",
  "linux-x64": "roust-linux-x64",
  "linux-arm64": "roust-linux-arm64",
  "win32-x64": "roust-win32-x64",
};

const key = `${process.platform}-${process.arch}`;
const pkg = PLATFORM_PACKAGES[key];
const binaryName = process.platform === "win32" ? "roust.exe" : "roust";

if (!pkg) {
  console.error(
    `roust: no prebuilt binary for ${key}.\n` +
      `Install from source instead:\n` +
      `  cargo install roust\n` +
      `or download a binary from https://github.com/narehart/roust/releases`,
  );
  process.exit(1);
}

let binary;
try {
  binary = require.resolve(`${pkg}/bin/${binaryName}`);
} catch {
  console.error(
    `roust: the platform package ${pkg} is not installed.\n` +
      `This usually means npm was run with --no-optional or the install was\n` +
      `interrupted. Try: npm install roust --force\n` +
      `Alternatives: cargo install roust, or a binary from\n` +
      `https://github.com/narehart/roust/releases`,
  );
  process.exit(1);
}

const result = spawnSync(binary, process.argv.slice(2), { stdio: "inherit" });
if (result.error) {
  console.error(`roust: failed to run ${binary}: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 0);
