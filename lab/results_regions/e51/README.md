# E51/E52 reproduction

Reports and frozen decision criteria:

- `lab/research/wave6/e51-protocol.md`
- `lab/research/wave6/e51-complementary-packing.md`
- `lab/research/wave6/e52-protocol.md`
- `lab/research/wave6/e52-overlap-budget.md`

`mining.json` audits the archived E47 scoreboard; `gold_cost.json` measures
oracle context sizes, not an achievable ceiling. Both exclude Python Verified.
`discovery/` contains E51 raw records, exact scores, paired tests, run manifests,
and scorer versions. E52 records live in `../e52/discovery/`.

## Inputs

`inputs/` archives the exact five fields used by evaluation, compressed as
JSONL. Unused dataset columns are omitted. The manifest records original
parquet SHA256, snapshot SHA256, and canonical evaluation-row SHA256. Restore
missing parquet inputs (existing files are verified and never overwritten):

```sh
uv run --no-project --with pandas --with pyarrow python lab/e51_inputs.py restore
```

The rows are identical; regenerated parquet bytes need not be. This is why both
file hashes and canonical-row hashes are recorded. These are the same
Multi-SWE-bench/SWE-bench inputs already used by the project's adapters and
archived evaluation, not a new sample or relabeled test set.

## Engine builds and evaluation

Build clean binaries from separate checkouts at the commits below and copy
them to stable paths. Do not rebuild or replace them while an arm is running:

- Baseline: `ad13f2f`.
- E51 complementary candidates: `d295b7b`.
- E52 overlap budget: `11cef25`.

Use `cargo build --release --manifest-path roust-rs/Cargo.toml` in each checkout.
The run manifests preserve the actual binary hashes and clean engine versions.

The runners require existing benchmark Git object stores at the paths in
`lab/e51_run.py:SLICES`. Each run creates its own shared-object clones in a
unique temporary directory; it does not mutate the source clones. Keep these
private clones until scoring finishes. To rescore archived predictions later,
use `lab/agentless_metric_full.py --repos-dir` pointing at any equivalent clones
containing the recorded base commits. The recorded temporary paths are local
to the original run and need not exist on another machine.

```sh
uv run --no-project --with pandas --with pyarrow python lab/e51_run.py \
  --slice rust --baseline /path/to/baseline --experiment /path/to/e51 \
  --out /tmp/e51-rerun

uv run --no-project --with pandas --with pyarrow python lab/e52_run.py \
  --slice cpp --baseline /path/to/baseline --experiment /path/to/e52 \
  --out /tmp/e52-rerun
```

Repeat for the other discovery slice. The default arm lists are frozen in the
runner modules. Do not use `--limit` for an adoption gate. Existing outputs
are rejected to prevent accidental appends or mixed runs.

## Exact scoring and comparisons

Use the versions in each `*_scoring.json` when reproducing the original grammar
walks. The following command installs the required packages; pin versions from
that artifact for a strict re-run:

```sh
uv run --no-project --with pandas --with pyarrow --with scipy \
  --with tree_sitter --with tree_sitter_javascript --with tree_sitter_typescript \
  --with tree_sitter_java --with tree_sitter_go --with tree_sitter_rust \
  --with tree_sitter_c --with tree_sitter_cpp \
  python lab/e51_score.py /tmp/e51-rerun/rust_manifest.json

uv run --no-project --with numpy --with scipy \
  python lab/e51_compare.py /tmp/e51-rerun/rust_manifest.json
```

The same commands score E52 manifests. `--reuse-baseline /path/to/old_baseline.jsonl`
optionally reuses control metrics only after matching the full control records,
gold hash, engine provenance, and payloads. Reuse is explicitly marked in the
metric source metadata. Otherwise controls are scored normally.

Comparisons require identical complete ID sets, verify flag-off payload identity,
keep errors wrong, and report exact FUNCTION/LINE, non-vacuous function counts,
paired McNemar tests, multiple-arm corrections, and deterministic paired bootstrap
intervals. Fractional means in the new comparisons count errors as zero; the
legacy exact scorer excludes errors only from its fractional mean. The discovery
arms had zero errors, so those two conventions coincide here.
