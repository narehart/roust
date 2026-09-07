# E57: semantic code regions with compact navigation context

E55's oracle FILE experiment leaves exact FUNCTION recall below Python even
after irrelevant files are removed. Test semantic region selection directly,
using the same pinned Qwen model/chunk inputs as E56 and preserving existing
file navigation. Gold never enters the retriever or packer.

Each baseline-returned file receives one nonempty line from its returned
regions. Prefer a line costing at most 64 tokens, otherwise retain its first
nonempty line. This is deliberately brief navigation context, not a claim
that a one-line excerpt provides the full implementation. Count headers and
separators against the final 8192-token budget. Fail explicitly if the seats
alone exceed it; do not silently overrun or drop baseline files.

Rank the E56 token chunks globally by cosine similarity. For the top 1000,
first try expanding to include overlapping AST function definitions, then
the original chunk's full source lines. Add a candidate only when its union
with existing regions adds source lines and the complete rendered bundle
fits. Python uses stdlib AST; the other languages use the existing grammar
packages. No scorer or gold-span helpers are imported by retrieval.

This isolates a new information signal and a new allocation policy together;
it does not claim either component's independent causal effect. Evaluate one
treatment against shipped output on full Rust and C++, initially two wiring
cases. Keep exact FILE/FUNCTION/LINE, strict fractional coverage, token cost,
and latency visible. Substantial one-line navigation makes precision and
FUNCTION/LINE metrics especially important; FILE improvement alone is not
success. Preserve Python Verified for a qualifying final gate.

Corpus membership is unchanged, so E55's FILE ceilings still apply. A later
separate ancillary-file channel is needed for raw all-gold parity; this
experiment is not presented as a complete solution by itself.
