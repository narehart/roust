# E23 — tree-sitter JS/TS/TSX structural blocks (`--ts-blocks`): MSWE-580 gate PASS, ADOPTED

*Campaign #4 wave 5. Spec: `lab/research/wave5/multilang-and-sweeps.md` Part (a), transplant #1.
Branch `e23-tsblocks` off main `3f0c77b`; engine + harness commits `a24b0c6` / `60d1455`.
Gate runs 2026-08-25, engine `roust 0.2.0 (60d1455, clean)` throughout.*

## What shipped

**Engine** (`roust-rs/src/core.rs`): `ts_blocks(text, rel)` — tree-sitter CST walk with a
node-type allowlist (`function_declaration`, generator variants, `class_declaration`,
`abstract_class_declaration`, `method_definition` (class bodies AND object literals),
declarator/pair/class-field-bound `arrow_function`/`function_expression`, TS-only
`interface_declaration`/`enum_declaration`/`module`/`internal_module`; export/ambient
wrappers hoisted into span starts, the JS analogue of python_blocks' decorator folding) —
emitting `python_blocks`' EXACT output contract: 1-indexed inclusive spans, leading
preamble span, each header running to the next header at same-or-lower CST depth (depth
plays indentation's role), so top-level spans partition the file and nested members get
their own tighter spans. Line numbers come from mapping tree-sitter byte offsets onto
`py_splitlines`' own line-start offsets (binary search), never tree-sitter rows —
py_splitlines splits on the full Unicode boundary set (` `, `\x0b`, …) while
tree-sitter rows count only `\n`, and the packer slices py_splitlines output by these
numbers. Parse failure degrades to the whole-file span (python_blocks' no-headers shape).
Wired into the single dispatch that previously sent every non-Python file to
`window_blocks(±30)`; flag `--ts-blocks`, **default OFF, byte-identical** (new
`pack_regions` param, `family_enum` pattern). Grammars are crates.io versions **pinned
exactly** (`tree-sitter =0.26.13`, `tree-sitter-javascript =0.25.0`,
`tree-sitter-typescript =0.23.2` via the `tree-sitter-language` ABI shim) — no parser.c
vendoring needed; grammar bumps are gated dependency changes per the documented ABI-churn
history (tree-sitter#3095, zed#24632).

**Harness twin** (`lab/agentless_metric_verified.py` + `lab/agentless_metric_full.py
--ts-functions`, default OFF): tree-sitter function-span extraction for .js/.jsx/.ts/.tsx
on BOTH the gold and predicted sides of the exact FUNCTION metric — function/method
implementations only (no class/interface/enum bodies, no abstract signatures), mirroring
the Python side's def-only convention. Python bindings pinned to the engine's grammar
versions (`tree-sitter==0.26.0`, `tree-sitter-javascript==0.25.0`,
`tree-sitter-typescript==0.23.2`). `parity/region_eval_full.py --ts-blocks` passthrough +
per-record `ts_blocks` provenance.

## The vacuous-FUNCTION fix, formally

The previously published MSWE FUNCTION 99.83 is **retired as vacuous**: gold-function
extraction was Python-AST-only, so every JS/TS instance had `n_gold_functions: 0` and
passed the subset condition vacuously. With the fixed scorer, **517/579** scored
instances have a non-empty gold function set, and the true baseline FUNCTION is
**21.21** (123/580).

## MSWE-580 gate (Multi-SWE JS/TS, both arms engine `60d1455`, fixed scorer)

| metric | baseline (defaults) | `--ts-blocks` | paired (gain/loss, two-sided sign test) |
|---|---|---|---|
| FILE (all-gold superset) | 46.38 (269/580) | **46.38 (269/580)** | +0/−0, p=1 — **invariant, per-instance identical** |
| FUNCTION (exact, first real numbers) | 21.21 (123/580) | **31.03 (180/580)** | +68/−11, p=3.5e-11 |
| LINE (all-or-nothing) | 9.31 (54/580) | **13.28 (77/580)** | +37/−14, p=1.8e-3 |
| LINE mean fraction | .1805 | **.2582** | mean diff +.0776, +168/−87, p=4.4e-7 |

(1 engine error per arm — `iamkun__dayjs-857`, same instance as the historical run,
counted wrong at all levels per the unified convention.)

**Anatomy — the packing half moved, the ranking half didn't** (by design):
- Conditional on the gold file being retrieved (n=269, identical set both arms):
  line-recall mean .270 → **.418**, median .000 → **.250**, zero-capture instances
  59.9% → **40.9%**. (Python Lite reference profile: .560 / .857 / 36.5% — roughly half
  the remaining conditional gap to Python is closed by structure alone.)
- Coverage: **100.0%** of returned non-.py region files (17,513/17,513, identical file
  sets both arms) are in the .js/.jsx/.ts/.tsx family — the `window_blocks` fallback
  fired on **zero** returned files in the ts arm. The whole packing surface of this
  benchmark is structural under the flag.
- FILE is flat because select_files is untouched — the remaining FILE half is a ranking
  problem, and note its ceiling: **135/580 instances have ≥1 gold file outside the
  indexed extension set** (.json 316 gold files, .md 158, .svelte, .mjs, …), bounding
  all-gold-superset FILE at ~76.7 for the current corpus walk regardless of ranking.

## Python no-regression proofs

1. **Lite-300 v12 reproduction, flag OFF**: 300/300 ok, scored by untouched
   `agentless_metric_v4.py`: **92.33 / 54.67 / 43.33 / .52510** — equal to the v12
   reference (`agentless_metric_e20_traceboost.json`) to every reported digit
   (artifact: `e23_lite300_baseline.jsonl` / `agentless_metric_e23_lite300_baseline.json`).
2. **Defaults byte-identity vs main**: 12 Lite instances across 6 repos, TWO runs per
   binary (3f0c77b reference build vs E23 build), md5 over the retrieval payload
   (query/files/regions/bundle): **12/12 identical, 0 determinism flakes**.
3. **Flag-ON wiring proof**: 30 Lite instances, defaults vs `--ts-blocks` on the E23
   binary: **30/30 byte-identical** — the wiring provably never touches Python-only
   bundles.
4. **Scorer no-regression**: modified `agentless_metric_verified.py` (flag OFF) rescored
   `e20_verified_traceboost.jsonl`: `all_instances` and `file_correct_subset` blocks
   **byte-equal** to the published artifact (92.38 / 47.17 / 35.63 / .47810).

## Cost (adoption inputs)

- **Binary size**: 6,281,056 → 9,672,912 bytes (**+3.39 MB, +54%**) for the three
  grammars — within the spec's single-digit-MB estimate.
- **Cold index**: unchanged (~22 ms on axios) — `ts_blocks` runs only at query time
  inside `pack_regions`, indexing never parses.
- **Warm query**: axios (141 files) 0.11 s → **2.23 s** with `--ts-blocks`. This is the
  packer's known structural-candidate cost profile, not a tree-sitter pathology: the
  shipped engine's Python path on flask (77 files) already runs 1.45 s warm — the JS
  window path was cheap only because it produced a handful of window candidates. The
  cost driver is the O(candidates²) pass-2 marginal loop + per-span tokenization, shared
  with the Python path; optimizing it (span-count caps, marginal-cache) is a separate,
  language-agnostic engine experiment.

## Verdict: ADOPTED (user-approved 2026-08-25, language-agnostic directive)

Gate criteria met exactly: MSWE LINE +3.97 (p=1.8e-3) and fraction +.0776 (p=4.4e-7)
positive, FILE per-instance invariant (+0/−0), FUNCTION +9.82 on its first real
measurement (p=3.5e-11), Lite-300 v12 reproduced exactly and Python path byte-identical
under the flag. **Structural blocks are now the engine default** (same PR #55, adoption
conversion), and the flag was renamed for the mechanism's scope as part of adoption —
the same flag will carry the #56 grammar batch (Java/Go/Rust/C/C++): canonical names
are `--structural-blocks` (ON by default, accepted-but-redundant) and
`--no-structural-blocks` (escape hatch reproducing the pre-adoption engine
byte-identically); `--ts-blocks`/`--no-ts-blocks` remain as **hidden accepted
aliases** (clap `alias`, not shown in `--help`) so existing harness scripts and this
document's own provenance notes stay valid.
Adoption identity proofs (14 MSWE JS/TS + 12 Lite Python instances, two runs per
config, md5 over the retrieval payload, run against the final renamed binary):
new-default binary == old binary with explicit `--ts-blocks` (and the structural
path demonstrably fired on all 14 JS/TS instances), new `--no-structural-blocks`
== old defaults; all eight runs per Python instance hashed identically
(structural blocks never fire on .py).
`mswe_jsts_e23_tsblocks` (FILE 46.38 / FUNCTION 31.03 / LINE 13.28 / fraction .2582)
is the MSWE reference going forward; Python v12 references are unchanged (proven
untouched). Accepted price: +3.39 MB binary, ~2.2 s structural-query cost on JS/TS
repos. This is step one of the language-agnostic campaign (issue #56).
Post-adoption follow-ups (now tracked in #56):
(a) the FILE-ranking half (46.38 vs the 76.7 extension ceiling — select_files is still
Python-tuned), (b) pass-2 cost optimization, (c) extending the corpus walk /
CODE_EXTENSIONS beyond the current set (.json/.md gold files are 135 instances of FILE
ceiling), (d) the b-part sibling transplants (#2/#3) now that JS/TS has real block
structure to enumerate families over.

## Process anomalies (recorded)

- First identity-gate attempt spuriously failed: the md5 included `stats.cache`
  ("miss" on each instance's first cold run vs "hit" on warm reruns), flagging every
  cold-vs-warm pair; fixed by hashing only the retrieval payload. Two accidentally
  concurrent gate processes also mutated the same private clones once (self-inflicted;
  killed, clones re-cold-started, rerun clean).
- The `swebench_driver` process guard trips on ITS OWN pgrep when several harnesses
  start simultaneously (`pgrep -f swebench_driver` matches the other guards' pgrep argv);
  staggering launches by 10 s avoids it. Worth a guard-side fix (match `swebench_driver[0-9]*\.py`).
- MSWE arm runtimes ~2.5×  the historical single-run (three concurrent evals sharing
  the machine); per-instance outputs unaffected (FILE sets identical to the 92baeeb run's
  269 file-hit set).

## Artifacts

`lab/results_regions/`: `e23_lite300_baseline.jsonl`(+`.log`),
`mswe_jsts_e23_baseline.jsonl`(+`.log`), `mswe_jsts_e23_tsblocks.jsonl`(+`.log`),
`agentless_metric_e23_lite300_baseline.json`, `agentless_metric_mswe_e23_baseline.json`,
`agentless_metric_mswe_e23_tsblocks.json`. Gate/stat scripts: `lab/e23_identity_gate.py`,
`lab/e23_paired_stats.py`. Unit tests: 5 `ts_blocks`/flag-gating tests in
`roust-rs/src/core.rs` (fixtures: arrow-in-const, object-literal methods, nested classes,
export default, TSX components, headerless fallback, .py-control flag gating).
