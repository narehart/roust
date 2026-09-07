# E59: cross-file duplicate function workload

E52 addressed overlapping spans within a file. Inspect a separate possible
waste: identical function bodies repeated across files, especially modular
and amalgamated C++ headers. [SourcererCC](https://arxiv.org/abs/1512.06448)
motivates indexed clone detection; the first diagnostic here uses exact
content hashes rather than its broader near-clone algorithm.

Before implementing a production change, mine the full Rust and C++ discovery
gold-function sets with the existing parser/scorer helpers. Collapse nested
or overlapping gold spans within each file so a parent and child are not
double-counted. Group resulting bodies across different files by exact text,
and separately by common-indentation removal. Report groups, possible body
token savings, and a conservative minimum-64-token subgroup.

This is gold-informed workload diagnosis, never retrieval. Location and
format overhead are omitted, so savings are not a strict budget lower bound
or an achievable recall gain. Indentation-normalized groups would need an
explicit source-reconstruction representation; they are not interchangeable
with exact-text groups. No source is changed and no Verified input is used.
