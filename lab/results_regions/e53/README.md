# E53/E54 engine audit and reproduction

Protocols are frozen in `lab/research/wave6/e53-protocol.md` and
`e54-protocol.md`. Final reports are `e53-engine-audit.md` and
`e54-local-feedback.md` in that directory. E53 raw predictions, exact metrics,
paired results, manifests, and scoring provenance are in `discovery/`.
E54 C records are in `../e54/discovery/`; JS/TS records are combined in
`../e54/aggregate/` from `../e54/shards/{0,1,2,3}/`.

## Inputs and binaries

Restore the exact evaluation fields with `lab/e51_inputs.py restore`; see
`../e51/README.md` for inputs, immutable benchmark Git objects, and grammar
package requirements. Python Verified was not used in this round.

Build release binaries in separate clean checkouts and keep them at stable
paths while evaluating. The run manifests record actual binary SHA256 and
clean engine versions:

- `ff0c995`: original main baseline.
- `3f2f3a9`: cache fixes, lazy shape parsing, and linear header ends.
- `f8f27f3`: frozen emitted-coverage experiment and traces.
- `9563064`: streaming line splitting.
- `fddb0a0`: frozen query-local feedback experiment, including all engine fixes.

After the squash merge, fetch `git fetch origin pull/92/head` to obtain
the intermediate engine commits for clean detached builds.

The ambiguous legacy block-cache format is intentionally invalidated; the
corpus index is unaffected. Runners isolate block caches by arm inside private
clones. All benchmark source working trees remain untouched.

## Evaluation and scoring

```sh
uv run --no-project --with pandas --with pyarrow python lab/e53_run.py \
  --slice rust --baseline /path/to/baseline --experiment /path/to/e53 \
  --out /tmp/e53-rerun

uv run --no-project --with pandas --with pyarrow python lab/e54_run.py \
  --slice c --baseline /path/to/baseline --experiment /path/to/e54 \
  --out /tmp/e54-rerun
```

Repeat E53 for C++. E54 JS/TS can run serially or in four independent shards:

```sh
uv run --no-project --with pandas --with pyarrow python lab/e54_run.py \
  --slice jsts --shards 4 --shard 0 --baseline /path/to/baseline \
  --experiment /path/to/e54 --out /tmp/e54-shards/0
```

Run shard indices 0–3 with corresponding output directories. Merge only
completed, compatible shards (duplicate/missing IDs and changed hashes fail):

```sh
uv run --no-project --with pandas --with pyarrow python lab/e54_merge.py \
  /tmp/e54-shards/0/jsts_manifest.json /tmp/e54-shards/1/jsts_manifest.json \
  /tmp/e54-shards/2/jsts_manifest.json /tmp/e54-shards/3/jsts_manifest.json \
  --out /tmp/e54-aggregate
```

Use `lab/e51_score.py <manifest>` with the exact-scoring packages from
`../e51/README.md`, then `lab/e51_compare.py <manifest>` with numpy/scipy.
The scorer driver memoizes immutable source parses by path, content SHA256,
and grammar gates, with a 4,096-entry bound. `scorer_identity.json` records
byte-identical scores against the original four-arm smoke reference.
Scoring provenance includes the driver hash and grammar versions.

FUNCTION/LINE and FILE errors stay wrong. New paired fractional means also
count errors as zero; the legacy scorer's fraction excludes errors, so use
the paired report for the C/JS-TS rows. These have error cases. E53 has none.
E54 changes FILE and uses a six-endpoint correction; E53 uses eight discovery
depth comparisons across two candidate arms.

## Diagnostics and performance

- `lab/e53_mine.py`: absent-source basename and companion-file probes.
- `lab/e53_indexability.py`: audited index guards and repository concentration;
  `eligible_shape` does not prove actual corpus membership or retrieval.
- `lab/e53_trace.py --binary /path/to/e53`: post-run largest fractional win/loss
  autopsies, with exact trace-on versus archived payload identity assertions.
- `lab/e53_perf.py --baseline /path/to/baseline --fixed /path/to/e54 --out /tmp/perf.json`:
  first two non-Verified tasks per slice; warm corpus, three block-cold/warm
  repeats per binary, alternating order, complete payload identity. Run without
  competing evaluation/build jobs for timing claims. Retain all observations.

The first timing run (`performance.json`) overlapped compilation/evaluation
and is exploratory. `performance_paused_with_test_overlap.json` paused the
evaluation workers but overlapped a targeted cache test; it is also exploratory.
The final report identifies the separately recorded
quiet repeat used for performance claims. These small timing samples are not a
recall gate or evidence of a universal speedup.
