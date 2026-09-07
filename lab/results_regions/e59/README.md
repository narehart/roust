# E59 exact duplicate-function workload

These gold-informed reports diagnose an opportunity; they do not measure
retrieval gains. All 239 Rust and 129 C++ tasks were parsed successfully.
The miner and scorer hashes and gold-input hashes are embedded in each JSON.

| Slice | Tasks with exact cross-file copies | Tasks with copies >=64 body tokens | Potential saved body tokens, >=64 |
|---|---:|---:|---:|
| Rust | 4 | 0 | 0 |
| C++ | 49 | 41 | 175,205 |

Location headers, retrieval mistakes, and the engine's candidate boundaries
are excluded. Thus these counts are neither achievable savings nor a recall
ceiling. E61 tests whether an actual retriever can exploit this opportunity.
Indentation-normalized copies are reported separately and are not used by E61.

Reproduce in the E56 scoring environment, using the restored discovery inputs
and base repositories listed by `e51_run.SLICES`:

```sh
python lab/e59_mine.py --slice rust --out /tmp/rust_duplicates.json
python lab/e59_mine.py --slice cpp --out /tmp/cpp_duplicates.json
```

Implementation: `e7c50cc`. No Verified instances were used.
