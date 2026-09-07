# E57 semantic region packing

Protocol: `lab/research/wave6/e57-protocol.md`. No production defaults change.

`smoke-fixed/` is the completed two-instance wiring/scoring run. One exact
FUNCTION/LINE result improves, while the other task loses .125 fractional
line coverage; this is mixed smoke evidence, not an adoption result.
`smoke-cached/` reuses completed E56 vectors read-only and reproduces every
baseline/control/treatment payload from `smoke-fixed/` exactly. Its vectors
are hashed in the records. Completed output manifests are required before
scoring; `smoke/` and `smoke-debug/` are incomplete crash reproductions and
must not be included in recall totals.

## Native crash diagnosis

The initial prototype used tree-sitter `Point.row` attributes. On Python
3.13.5/tree-sitter 0.26.0 this reproducibly segfaulted. A four-way traversal
probe isolated attribute access: `children`/tuple-index passed,
`named_children`/tuple-index passed, and both attribute-access variants
segfaulted. The [0.26.0 binding source](https://github.com/tree-sitter/py-tree-sitter/blob/v0.26.0/tree_sitter/binding/point.c)
returns a borrowed tuple item from its attribute getters, consistent with
the observed memory corruption. The established scorer already uses tuple
access. E57 now uses it too, with a regression exercising repeated parsing
and line numbers outside Python's small-integer cache. Rust dependency pins
and scorer behavior are unchanged.

## Reproduce

Use E56's Python environment plus `tiktoken==0.14.0`; exact runtime and
source hashes are recorded in each environment JSON. Use the frozen E55 CLI
as both baseline and experiment (the Python controller implements packing):

```sh
python lab/e57_run.py --slice rust --baseline /path/to/baseline \
  --experiment /path/to/baseline --out /tmp/e57-rerun \
  --producer /path/to/e56/rust_hybrid26.jsonl
python lab/e51_score.py /tmp/e57-rerun/rust_manifest.json
python lab/e51_compare.py /tmp/e57-rerun/rust_manifest.json
```

`--producer` waits for each E56 instance's completed prediction before reading
its cached vectors. Missing vectors fail explicitly rather than being silently
recomputed with different settings. Omit the option to populate vectors with
the E56 model implementation. The full E56 embedding costs still apply;
read-only cache timings are not end-to-end cold retrieval latency. For final
selection, apply the four-candidate E56/E57/E58 family correction from E58's
protocol, not only the comparison script's per-run correction.
