# E63 controlled query/code reranking

The [protocol](../../research/wave6/e63-protocol.md) fixes the 128-region
pool, model revision, truncation, tie breaks, and unchanged semantic packer.
The registered implementation is `c15308b`. The family report now accounts
for seven candidates and 42 binary endpoint comparisons.

`backend-probe.json` is a synthetic native/PyTorch reference check, not recall
evidence. Maximum logit-difference error was .01953125 on two synthetic
documents; their ranking matched, cache replay was exact, and the independent
query/document limits preserved code after an oversized issue.

`smoke/` contains two complete Rust instances. Both default-off payloads match
the baseline, and both read-only semantic replays reproduce the E58 producer
payload exactly before reranking. No error occurred. The reranked output has
FILE 50%, FUNCTION 50%, LINE 0%, and fraction .516667: the same aggregate
metrics as E58's smoke. Baseline metrics are 50%, 0%, 0%, and .504167. The
two-case mean fraction masks one gain and one loss against the baseline;
this is execution evidence, not an adoption result.

Use the E58 MLX environment and the separate E63 score cache. A matching E58
producer environment must exist; its per-instance record may still be in
progress, in which case the consumer waits for completion.

```sh
python lab/e63_run.py --slice cpp --baseline /path/to/baseline \
  --experiment /path/to/baseline --out /tmp/e63 \
  --source-producer /path/to/e58/cpp_ast-semantic.jsonl \
  --embedding-cache /path/to/e58-embeddings.sqlite \
  --rerank-cache /tmp/e63-scores.sqlite
python lab/e51_score.py /tmp/e63/cpp_manifest.json
python lab/e51_compare.py /tmp/e63/cpp_manifest.json
```

Repeat for Rust. Full discovery records, complete family correction, remaining
language/Lite replication, and a qualifying Verified gate are required before
adoption. Producer failure or replay mismatch prevents a valid complete result.
Do not pool smoke results with the full discovery results.
