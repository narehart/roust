#!/usr/bin/env node
/**
 * Build a platform-specific npm package (e.g. roust-darwin-arm64) around a
 * compiled binary, ready for `npm publish`. Run once per build-matrix target
 * in CI:
 *
 *   node npm/prepare-platform-package.mjs --target aarch64-apple-darwin
 *
 * Prints the package directory on stdout (CI captures it). The package holds
 * only the binary plus a minimal package.json carrying os/cpu constraints, so
 * npm installs exactly one of these via the main package's
 * optionalDependencies -- the esbuild/Biome model. No postinstall script and
 * no runtime download on the happy path.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

export const TARGETS = {
  "x86_64-apple-darwin": { pkg: "roust-darwin-x64", os: "darwin", cpu: "x64" },
  "aarch64-apple-darwin": { pkg: "roust-darwin-arm64", os: "darwin", cpu: "arm64" },
  // libc is load-bearing: without it npm's arborist cannot tell a glibc
  // package from a musl one and either may "win" on a Linux install.
  "x86_64-unknown-linux-gnu": { pkg: "roust-linux-x64", os: "linux", cpu: "x64", libc: ["glibc"] },
  "aarch64-unknown-linux-gnu": { pkg: "roust-linux-arm64", os: "linux", cpu: "arm64", libc: ["glibc"] },
  "x86_64-pc-windows-msvc": { pkg: "roust-win32-x64", os: "win32", cpu: "x64" },
};

export function preparePlatformPackage(target, rootDir = ROOT) {
  const info = TARGETS[target];
  if (!info) {
    throw new Error(`Unknown target: ${target}. Known: ${Object.keys(TARGETS).join(", ")}`);
  }
  const main = JSON.parse(fs.readFileSync(path.join(rootDir, "npm", "roust-cli", "package.json"), "utf8"));
  const binaryName = info.os === "win32" ? "roust.exe" : "roust";
  const built = path.join(rootDir, "roust-rs", "target", target, "release", binaryName);
  if (!fs.existsSync(built)) throw new Error(`Built binary not found: ${built}`);

  const pkgDir = path.join(rootDir, "npm", info.pkg);
  const binDir = path.join(pkgDir, "bin");
  fs.mkdirSync(binDir, { recursive: true });
  fs.copyFileSync(built, path.join(binDir, binaryName));
  if (info.os !== "win32") fs.chmodSync(path.join(binDir, binaryName), 0o755);

  fs.writeFileSync(
    path.join(pkgDir, "package.json"),
    JSON.stringify(
      {
        name: info.pkg,
        version: main.version,
        description: `roust binary for ${info.os}-${info.cpu}`,
        license: main.license,
        repository: main.repository,
        os: [info.os],
        cpu: [info.cpu],
        ...(info.libc ? { libc: info.libc } : {}),
        files: ["bin"],
      },
      null,
      2,
    ) + "\n",
  );
  return pkgDir;
}

// CLI entry point only when invoked directly -- sync-optional-deps.mjs
// imports TARGETS from this module and must not trigger the CLI.
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const i = process.argv.indexOf("--target");
  const target = i >= 0 ? process.argv[i + 1] : undefined;
  if (!target) {
    console.error("Usage: node npm/prepare-platform-package.mjs --target <rust-target-triple>");
    process.exit(1);
  }
  console.log(preparePlatformPackage(target));
}
