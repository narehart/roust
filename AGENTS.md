# Project instructions

This repository is **roust** (the checkout directory may still be named
`bgrep`), a local Rust CLI that returns ranked, token-budgeted code bundles.

## Shared agent context

- Edit shared project instructions in `.rulesync/rules/project.md`; this file
  is generated. Run `npm run agents:sync` after editing shared configuration.
  Read `.agents/README.md` for the layout and workflow.
- If `.agents/memory/MEMORY.md` exists, read its index at the start of a task
  and open the relevant topic files. Treat historical findings as context;
  verify current behavior against the checkout.
- Keep harness-specific permissions, hooks, and runtime state in their native
  configuration locations. Shared prose does not grant tool permissions.

## Repository map

- `roust-rs/`: shipped Rust CLI and Rust integration tests.
- `tests/`: Python tests, including subprocess tests of the release binary.
- `parity/` and `lab/`: evaluation tooling, research artifacts, and experiments.
- `README.md` and `docs/`: user documentation, benchmarks, and research notes.
- `scripts/`: docs build, packaging, and version checks.
- `npm/roust-cli/`: published npm wrapper; root `package.json` is repo tooling.
- `RELEASE.md`: release procedure.

## Working conventions

- Do work on a branch named with a conventional prefix (for example,
  `chore/sync-agent-configuration`), not directly on `main`. Use Conventional
  Commit messages, open a pull request, and merge it after required checks pass.

- Scope searches to relevant source directories. `lab/` contains large cloned
  repositories and generated results; `.claude/worktrees/` contains separate
  checkouts. Exclude these from broad searches unless the task needs them.
- Preserve existing experiment outputs and unrelated untracked files.
- Ground benchmark claims and changes to retrieval defaults in reproducible
  evaluation artifacts. See `docs/RESEARCH.md` and `docs/EVALUATION.md`.
- Preserve exact tree-sitter dependency pins in `roust-rs/Cargo.toml` unless
  intentionally upgrading and validating the grammar/core combination.
- Keep release versions consistent using `scripts/check_versions.py` and
  follow `RELEASE.md` for packaging changes.

## Validation

Run checks appropriate to the change, from the repository root:

- Rust: `cargo test --manifest-path roust-rs/Cargo.toml`.
- Python/CLI: first `cargo build --release --manifest-path roust-rs/Cargo.toml`,
  then `uv run pytest tests/`. Binary-dependent tests skip if the release
  binary is absent; skips are not evidence that CLI behavior passed.
- Docs tooling: `npm run docs:test` and `npm run docs:build`.
- Version changes: `python3 scripts/check_versions.py`.

For instruction-only edits, verify paths and imports; application tests are
unnecessary unless application behavior also changes.
