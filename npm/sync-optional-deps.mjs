#!/usr/bin/env node
/**
 * Pin every platform package as an exact-version optionalDependency of the
 * main `roust` package, immediately before publishing, so the pinned versions
 * always match the release being published. Deliberately not checked in: a
 * committed pin would be stale the moment the version bumps.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { TARGETS } from "./prepare-platform-package.mjs";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifestPath = path.join(ROOT, "npm", "roust", "package.json");
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));

manifest.optionalDependencies = Object.fromEntries(
  [...new Set(Object.values(TARGETS).map((t) => t.pkg))].sort().map((p) => [p, manifest.version]),
);
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
console.log(`Pinned ${Object.keys(manifest.optionalDependencies).length} platform packages at ${manifest.version}`);
