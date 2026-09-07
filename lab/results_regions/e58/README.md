# E58 stable-unit workload and retrieval experiments

Protocol: `lab/research/wave6/e58-protocol.md`. `reuse/` is a source-only
workload comparison on the first 20 deterministic Rust and C++ instances,
with no model inference. Each method starts with an independently empty
simulated content cache. The reports do not establish recall or latency gains.

| Slice | Window new chunks | AST new chunks | Window padded tokens | AST padded tokens | AST/window |
|---|---:|---:|---:|---:|---:|
| Rust, 20 | 11,359 | 15,703 | 4,309,222 | 2,609,180 | .6055 |
| C++, 20 | 16,380 | 28,618 | 6,217,242 | 4,490,066 | .7222 |

AST units generate more individual chunks but reduce the padded tokens that
would need embedding by 39.45% and 27.78%. Estimated attention-cell counts
fall to .4351 and .5392 of the window method. These are workload proxies;
batch overhead and hardware behavior require actual timing measurements.

Reproduce the workload comparison using the E56 Python environment and frozen
E55 CLI (both binary paths may point to that same clean CLI):

```sh
python lab/e58_mine.py --slice rust --baseline /path/to/baseline \
  --experiment /path/to/baseline --out /tmp/e58-reuse --limit 20
python lab/e58_analyze.py /tmp/e58-reuse/rust_manifest.json
```

Repeat for C++. The frozen miner/source-unit implementation is commit
`d3cb391`. Tokenizer model/revision is the E56 pinned Qwen checkpoint.

The retrieval stage uses `lab/e58_run.py` with `mlx==0.32.2`,
`mlx-lm==0.31.3`, and the recorded Python/scoring environment. It uses the
original weights in float16; no quantized checkpoint is substituted.
Keep its cache separate from E56's:

```sh
python lab/e58_run.py --slice rust --baseline /path/to/baseline \
  --experiment /path/to/baseline --out /tmp/e58-retrieval \
  --embedding-cache /tmp/e58-embeddings.sqlite
```

Use `e51_score.py` and `e51_compare.py` as for E57. A successful completed
manifest, full membership checks, and family-wide correction are required
before drawing a discovery conclusion. Smoke, workload, and full retrieval
artifacts have different purposes and must not be pooled.

## Two-instance smoke

`smoke/` is complete and retains the manifest, original scorer results,
paired comparison, and native environment. Both flag-off payloads match.
AST semantic regions obtain FILE 50%, FUNCTION 50%, LINE 0%, and mean line
fraction .516667, compared with baseline 50%, 0%, 0%, and .504167.
This mixed two-instance result establishes execution, not an adoption gain.
The complete six-candidate discovery correction is performed by
`lab/e61_family.py` only once both full slices of every candidate finish.
