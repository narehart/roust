# E56 semantic retrieval experiment

Protocol: `lab/research/wave6/e56-protocol.md`. Model code and runner:
`lab/e56_dense.py`, `lab/e56_run.py`. This is a local research backend, not
a production CLI dependency or adopted default.

`smoke/` is a two-instance wiring/performance run. Dense selection recovers
one exact FUNCTION/LINE result; lexical fusion leaves both results unchanged.
Neither result is evidence of a general improvement. Both control payloads
match baseline. Cold embedding of the two repository versions took minutes;
the second version reused unchanged content. Timings include concurrent
research processes and are not a quiet performance benchmark.

Create a Python environment with the packages in `rust_environment.json`
and pandas, pyarrow, scipy, and the grammar packages listed in the scorer
provenance. The model revision is pinned and downloads to the normal Hugging
Face cache. Model artifacts and embeddings are not committed. Embeddings are
cached in `/private/tmp/roust-e56-cache/embeddings.sqlite` by model/configuration
and exact input text. Use an empty cache for cold cost measurements.

Use the E55 frozen CLI/example binaries (the example basename must be
`research_pack`):

```sh
python lab/e56_run.py --slice rust --baseline /path/to/baseline \
  --experiment /path/to/research_pack --out /tmp/e56-rerun
python lab/e51_score.py /tmp/e56-rerun/rust_manifest.json
python lab/e51_compare.py /tmp/e56-rerun/rust_manifest.json
```

Repeat for C++. Run all arms in the declared order: baseline establishes
the exact base-commit corpus cache before semantic retrieval reads it.
Dense and hybrid share the same per-instance embedding/ranking computation.
Their repeated `e56_diagnostic.documents` and `.query` fields describe that
shared computation and must not be summed as independent costs. The separate
`e56_elapsed_seconds` field measures actual time spent in each arm, including
checkout and model initialization when incurred. Full discovery results must
be distinguished from this smoke and from E55's gold-informed diagnostic.
