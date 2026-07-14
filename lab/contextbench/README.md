# ContextBench evaluation (issue #3)

Evaluates roust on [ContextBench](https://github.com/EuniAI/ContextBench)
(arXiv:2602.05892) — the benchmark whose gold labels are human-annotated
"necessary context" line regions, scored with interval-overlap
Coverage(=Recall)/Precision at file / symbol("block") / line granularity.
This is exactly the shape roust outputs, so scoring uses ContextBench's own
evaluator unmodified.

## Protocol

- **Dataset**: `data/contextbench_verified.parquet` from the ContextBench repo
  (their curated 500-instance benchmark drawn from SWE-Bench
  Verified/Multi/Poly/Pro), filtered to `language == "python"` → **266 tasks,
  19 repos**. Data license is unstated upstream, so no task data or repo
  content is committed here — only the adapter and aggregate results.
- **System under test**: the frozen release binary
  `roust-rs/target/release/roust` (version recorded per prediction row and in
  `manifest.json`), invoked once per task:
  `roust --json --budget 8192 "<problem_statement>" <repo@base_commit>`.
  No model, no API key, no per-benchmark tuning.
- **Prediction format**: roust's `regions: {file: [[start, end], ...]}` maps
  to a ContextBench trajectory with a **single step** (`pred_steps` has one
  entry equal to the final context; `pred_files`/`pred_spans` are the packed
  bundle's files/line spans).
- **Scoring**: `python -m contextbench.evaluate --gold <parquet> --pred <chunk>
  --cache <dir> --out <results>` — their code end to end, including repo
  checkout, path validation, tree-sitter symbol extraction, and micro-average
  aggregation (`aggregate_results`).
- **Efficiency metrics are N/A**: ContextBench's AUC-Coverage / Redundancy
  measure *trajectory* efficiency across an agent's retrieval steps. roust is
  a one-shot tool — its trajectory has exactly one step, so AUC degenerates to
  final coverage and Redundancy to 0 by construction. We report final
  Coverage/Precision only. `editloc` is likewise not reported: roust emits no
  patch, and the evaluator's gold-patch fallback would score the gold patch
  against gold context (an oracle, not a prediction).

## Running

```bash
# one-time: clone github.com/EuniAI/ContextBench, create a venv with its
# requirements (python 3.11 for tree-sitter-languages wheels)
<evaluator>/.venv/bin/python lab/contextbench/run_contextbench.py \
  --evaluator <evaluator-clone> \
  --cache lab/contextbench_repos/cache \
  --tmp-root lab/contextbench_repos/tmp \
  --out-dir lab/contextbench_repos/run_python \
  --language python --evaluate
```

The runner is resumable (skips instance_ids already in `predictions.jsonl` /
`skips.jsonl`), clones lazily per repo via ContextBench's own blob-filtered
`checkout()`, evaluates per repo group, and prunes per-commit worktrees after
each group so peak disk stays bounded. Tasks that fail (checkout error, roust
error/timeout, empty regions) are skipped and counted in `skips.jsonl`.

## Results

266/266 tasks evaluated (0 skipped), `roust 0.2.0 (c07a09d, clean)`,
budget 8192, micro-averaged by ContextBench's `aggregate_results`:

| Granularity | Coverage (recall) | Precision |
|---|---|---|
| file | 0.679 | 0.060 |
| symbol ("block") | 0.346 | 0.040 |
| line | 0.274 | 0.053 |

Reference (different protocol — multi-turn LLM agents, full 500-task
8-language set): Claude Sonnet 4.5 file 0.720/0.665, block 0.449/0.420,
line 0.374/0.344 (recall/precision).

Full aggregate: `results_python.json`. Per-instance results and prediction
files stay local (`lab/contextbench_repos/run_python/`, gitignored) because
the dataset's license is unstated.
