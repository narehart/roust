# Release runbook

`roust` ships three artifacts from a single tag push:

| Artifact | What it is | Where it goes |
|---|---|---|
| **Platform npm packages** (`roust-darwin-arm64`, `roust-linux-x64`, …) | The compiled binary plus a minimal `package.json` carrying `os`/`cpu`/`libc` constraints. npm installs exactly one of them through the main package's `optionalDependencies` (the esbuild/Biome model — no postinstall script, no runtime download). | npm |
| **Main npm package** (`roust-cli`) | A launcher (`bin/roust.mjs`) that resolves the platform package and execs the binary, forwarding argv/stdio/exit code. `npm i -g roust-cli`, `npx roust-cli` — the installed command is `roust`. The bare `roust` name is rejected by npm's typosquat guard ("too similar to existing packages"), which is why this is `-cli` suffixed, same as sibling projects. | npm |
| **Crate** (`roust` on crates.io) | The `roust-rs/` Rust source, for `cargo install roust` and library use. This is the build-from-source path for platforms without a prebuilt binary. | crates.io |
| **GitHub Release** | The raw per-platform binaries with `.sha256` checksums, plus auto-generated notes. | GitHub Releases |

Prebuilt targets: `x86_64-apple-darwin`, `aarch64-apple-darwin`,
`x86_64-unknown-linux-gnu`, `aarch64-unknown-linux-gnu`,
`x86_64-pc-windows-msvc`.

All of it is built and published by `.github/workflows/release.yml`, triggered
by pushing a tag matching the strict `v[0-9]+.[0-9]+.[0-9]+` pattern (`vX.Y.Z`
only -- a typo'd or pre-release-suffixed tag does not trigger a publish).

---

## v0.3.0 / v0.3.1 — shipped 2026-08-26

Published and verified:

| Artifact | Version | Check |
|---|---|---|
| npm `roust-cli` | 0.3.0 | `npm install roust-cli` pulls exactly one platform package and the `roust` command runs |
| npm `roust-{darwin-arm64,darwin-x64,linux-arm64,linux-x64,win32-x64}` | 0.3.0 | published from their own build jobs |
| crates.io `roust` | 0.3.0 | `cargo install roust` |
| GitHub Release `v0.3.0` | — | 10 assets (5 binaries + 5 `.sha256`) |
| Docs site | — | https://narehart.github.io/roust/ |

0.3.1 followed immediately, for a reason worth recording: a registry renders
the README **from the published version**, so 0.3.0's crates.io page carried a
README that still said "not yet released", and the npm package shipped no
README at all. Registry pages are documentation; they need the same accuracy
bar as the repo. The npm package now ships the root README (staged at publish
time, one source of truth) and the release checklist below includes reading
the rendered registry pages after publishing.

One provenance wrinkle to know about, specific to the 0.3.0 release: the npm
binaries were built by the tag run (embedded SHA `c075631`) and the GitHub
Release assets by the follow-up dispatch (`a726d9d`), so `roust --version`
reports different SHAs for the same 0.3.0 depending on where you got it. The
`roust-rs/` diff between those commits is empty — the two builds produce
byte-identical output on the same input, verified — and future releases avoid
the split because the publish steps are now re-runnable from the tag itself.

Two things the first attempt taught, both now fixed in the workflow:

1. **npm rejects the bare name `roust`** — "too similar to existing packages
   must,rbush", its typosquat guard. The published package is `roust-cli`
   (the installed command is still `roust`), matching the convention sibling
   projects already use. The platform packages were not affected.
2. **Every publish step is now idempotent.** npm and crates.io versions are
   immutable, so a partially-successful release used to be unrecoverable
   without a version bump; each step now checks the registry and skips what
   is already there. A re-run resumes rather than failing.

## One-time setup — DONE

Both registry credentials are configured as repository secrets (verify with
`gh secret list --repo narehart/roust`):

| Secret | Registry | Token | Expires |
|---|---|---|---|
| `CARGO_REGISTRY_TOKEN` | crates.io | `roust-release-ci`, scopes `publish-new` + `publish-update` | 2027-08-26 |
| `NPM_TOKEN` | npm | `roust-ci`, granular, read+write all packages, 2FA-bypass | 2026-11-24 |

Both names are unclaimed until the first publish: `roust` is free on npm and
on crates.io, and the platform package names (`roust-darwin-arm64` etc.) are
free too. The first real tag push claims all of them.

Rotation: regenerate at the registry, then `gh secret set <NAME> --repo
narehart/roust`. The npm token is capped at 90 days by npm policy, so it will
need rotating before the next release cycle if that is more than three months
out.

## Per-release steps

1. **Bump the version in both places** (they must match — CI checks this,
   see below):
   - `pyproject.toml`: `version = "X.Y.Z"`
   - `roust-rs/Cargo.toml`: `version = "X.Y.Z"`

2. **Update `CHANGELOG.md`**: move the `[Unreleased]` entries under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading (or add one if there's nothing under
   `Unreleased` yet).

3. **Commit** the version bump + changelog update.

4. **Dry-run the release workflow first** (recommended for anything other
   than a routine patch): Actions > Release > "Run workflow", pick the
   branch/commit you just pushed, leave `dry_run` checked (the default). This
   compiles all five platform binaries, checksums them, and stages each npm
   platform package — everything a real release builds — while skipping npm,
   crates.io, and the GitHub Release. Confirm all jobs are green before
   tagging.

5. **Tag and push**:
   ```
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
   The tag push triggers `release.yml` for real (`dry_run` is only a
   `workflow_dispatch` input; a tag push always runs the full publish path).

6. **Watch the run**: `gh run watch` or the Actions tab. Expect, in order:
   `plan` -> `build-binaries` (5 targets in parallel; each publishes its own
   `roust-<platform>` npm package at the end) -> `publish-npm` +
   `publish-crates-io` + `github-release` (parallel, after the builds).

   Ordering matters for npm: the platform packages must exist on the registry
   before the main `roust` package that pins them as `optionalDependencies`,
   which is why `publish-npm` `needs: build-binaries`.

7. **Read the rendered registry pages** once the run is green:
   https://www.npmjs.com/package/roust-cli and
   https://crates.io/crates/roust. Both render the README from the version
   just published — a stale sentence there is public in a way a stale line in
   the repo is not, and it cannot be edited without another version.

8. **Partial failures are contained by design.** Each publish target is its
   own job, so a crates.io token problem cannot block the npm publish or the
   GitHub Release (and vice versa). Fix the cause, then "Re-run failed jobs"
   from the Actions UI, or dispatch `release.yml` against the `vX.Y.Z` tag ref
   with `dry_run` unchecked.

   One npm-specific caveat: npm publishes are immutable and a version can only
   be published once. If `publish-npm` fails *after* some platform packages
   published, re-running is safe for the ones that failed but will error
   ("cannot publish over previously published version") for the ones that
   succeeded — bump to the next patch version rather than fighting it.

---

## Binary matrix

| Target | Runner | Notes |
|---|---|---|
| `x86_64-apple-darwin` | `macos-latest` | Built natively; cross-arch on Apple Silicon runners via `--target`. |
| `aarch64-apple-darwin` | `macos-latest` | Apple Silicon, native. |
| `x86_64-unknown-linux-gnu` | `ubuntu-latest` | Native. glibc; `libc: ["glibc"]` in the npm platform manifest. |
| `aarch64-unknown-linux-gnu` | `ubuntu-latest` | Cross-compiled with `gcc-aarch64-linux-gnu` (`CARGO_TARGET_..._LINKER`). |
| `x86_64-pc-windows-msvc` | `windows-latest` | Native. |

Not built: musl Linux (add `x86_64-unknown-linux-musl` with the matching
`libc: ["musl"]` manifest if Alpine users appear) and Windows arm64 (no
GitHub-hosted runner). Both fall back to `cargo install roust`.

---

## Version consistency check

`scripts/check_versions.py` compares the `version` in `pyproject.toml`
against `roust-rs/Cargo.toml` and fails if they differ. It runs as the
`version-check` job in `.github/workflows/ci.yml` on every push/PR to `main`,
so a drift is caught long before a tag is ever pushed — the release workflow
itself doesn't re-check, it just builds whatever `pyproject.toml`/`Cargo.toml`
say at the tagged commit.

Run it locally any time with `python3 scripts/check_versions.py`.

---

## Testing the workflow without publishing

Use `workflow_dispatch` with `dry_run` checked (the default). The build jobs
run in full — every platform binary is compiled, checksummed, uploaded as a
CI artifact, and staged into its npm platform package (the manifest is printed
to the log) — while all three publish jobs are skipped outright
(`if: needs.plan.outputs.dry_run != 'true'`). A dry run therefore exercises
everything except the four `npm publish` / `cargo publish` / release-upload
calls, and cannot publish by accident.
