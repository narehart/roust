# E63: rerank a fixed semantic candidate pool

Registered after the backend-only preparation/probe, before benchmark runs.
Use the pinned Qwen reranker and native implementation described in
`e63-reranker-preparation.md`. This is the seventh discovery candidate;
family correction becomes 7 candidates × 2 slices × 3 binary endpoints = 42.

For each full Rust/C++ task, wait for its completed E58 source record. Read
only the corresponding frozen E58 embedding cache, with matching source-unit
implementation and namespace. Recreate E58's original semantic bundle and
require exact regions/bundle payload identity before reranking. Producer
failures or mismatched records are errors, never missing cases discarded
from the denominator. Base commit and repository must match.

Take the first 128 distinct (path, start, end) regions from E58's cosine
ranking. Score issue text and each source region jointly, with explicit path
and range metadata. Use the already-validated 768-query/1024-document token
limits, final yes-minus-no logits, and deterministic path/range tie breaks.
Place these reranked candidates first and retain the remaining distinct
regions in their original order. Apply E57/E58's unchanged navigation seats,
function expansion, top-1000 loop, and exact 8192-token rendering.

There are baseline, flag-off, and cross-rerank arms. Keep every existing
baseline navigation file and validate flag-off payload identity. Score full
FILE/FUNCTION/LINE/fraction using the original helpers and compare both with
the baseline and E58's recorded outcome. Reranker scores, producer record
hashes, cache namespace, source hashes, and timing are recorded. Timing under
concurrent jobs is not a controlled latency benchmark.

A two-instance wiring smoke checks cache reproduction and complete execution;
it cannot select pool size or establish a recall gain. Full discovery, the
expanded family correction, remaining-language/Lite replication, and a
qualifying Verified gate remain required for adoption. No new ancillary
documents or gold-derived retrieval features enter this candidate.
