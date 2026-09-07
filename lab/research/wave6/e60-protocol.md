# E60: assign leading comments to their declaration

Engine inspection found that structural blocks start at declaration headers
and end at the next header. Consequently, documentation immediately before
function B belongs to function A's block, while Python docstrings naturally
sit inside their function. A query matching B's documentation can therefore
rank A's block. Test this concrete boundary issue without a learned model.

Add a default-off leading-comment attachment mode. Only contiguous comments
on their own line, immediately preceding a declaration (including hoisted
attributes/templates/export wrappers), move the declaration's start. Do not
attach trailing inline comments or comments separated by blank lines. Keep
Python blocks unchanged. Re-key affected structural-block cache entries and
preserve symbol-anchor seating when the block now begins before the symbol.

Use synthetic ownership/cache/anchor tests, then freeze the candidate and run
full Rust/C++ against the shipped binary with payload-identical flag-off
controls. Original exact scoring, 8192 requested tokens, pad 5, length .85,
error-zero fractions, and paired comparisons apply. FILE should be unchanged.
Treat this as an additional discovery candidate, with family-wide correction
across E56/E57/E58/E60 before any adoption claim. Replicate any qualifying
improvement on remaining discovery languages/Lite before Verified.
