# E58: stable source units for incremental semantic indexing

E56's whole-file token windows shift when text is inserted before them.
Early measured clap instances recomputed 72–95% of chunks. This is a cache
reuse problem, not evidence that semantic recall has reached a capability
limit. Function-level retrieval in the SweRank papers also motivates making
the embedding unit correspond more closely to code structure.

First compare the first 20 deterministic Rust and C++ discovery inputs with
no model inference. For each exact engine corpus, construct either E56's
whole-file windows or outermost AST function units plus intervening text.
Split each unit using the same 384-token length and 320-token stride, and
retain the same path prefix. Empty whitespace gaps need no embedding.

Simulate an initially empty content cache independently for each method,
in the existing dataset order. Report unique new chunks, input token counts,
batch-8 padded tokens, and batch-8 attention-cell counts. These are workload
measurements, not latency or recall results. Preserve all nonempty source
lines in the source-unit partition; moving a function must preserve its
content key when the function and path are unchanged.

A later actual retrieval experiment must freeze its model backend and
packing policy separately. Do not mix vectors from different inference
backends or interpret reduced embedding work as proven retrieval quality.

## Retrieval stage, frozen after workload mining

Test the AST-unit representation with the same E57 navigation/region-packing
policy (no added padding or new gold-informed selection). Use the original
Qwen checkpoint in float16 through `mlx-lm`'s Qwen3 transformer layers, causal
attention with left-padding masked, last-token pooling in float32, and batches
of 32. Use a separate embedding cache/namespace. Package and driver versions
are recorded. A 64-document fixture from the original smoke corpus compares
native vectors to the saved PyTorch vectors; this is a numerical check, not
proof of identical downstream rankings.

Run a two-instance smoke, then full Rust and C++. This treatment changes both
source-unit construction and inference backend, and does not isolate their
individual effects on recall. Original exact scoring and token/error rules
remain in force. E56's two treatments, E57's treatment, and this treatment are
one four-candidate discovery family for final selection; do not report the
per-run comparison script's smaller correction as family-wide support.
