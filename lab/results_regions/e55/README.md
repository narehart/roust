# E55 oracle-file diagnostic artifacts

Protocol: `lab/research/wave6/e55-protocol.md`. Report:
`lab/research/wave6/e55-oracle-diagnosis.md`.

`discovery/` contains all raw records, complete input/output/binary manifests,
original scorer outputs/provenance, and strict diagnosis summaries. `smoke/`
contains the initial two-instance wiring check; it is not counted again in
the full results. Gold is deliberately supplied only to the oracle arm.

Restore inputs using `lab/e51_inputs.py restore`. Build a clean checkout of
`645170a` with:

```sh
cargo build --release --manifest-path roust-rs/Cargo.toml --bin roust --example research_pack
```

Copy the CLI to a frozen path named `baseline` and the example to a frozen
path named `research_pack` (the wrapper identifies the example by basename).
The manifests record the original SHA256 hashes and clean versions. Run in an
environment containing pandas, pyarrow, scipy, tree_sitter, and the seven
`tree_sitter_{javascript,typescript,java,go,rust,c,cpp}` grammar packages
(JavaScript and TypeScript are separate packages).
Exact versions are in each `*_scoring.json`.

```sh
python lab/e55_run.py --slice rust --baseline /path/to/baseline \
  --experiment /path/to/research_pack --out /tmp/e55-rerun
python lab/e51_score.py /tmp/e55-rerun/rust_manifest.json
python lab/e55_analyze.py /tmp/e55-rerun/rust_manifest.json
```

Repeat for `cpp`. The runner uses disposable shared-object clones, preserving
the benchmark working trees, and isolates the structural block cache by arm.
`full_gate` in the inherited run manifest means the complete slice ran; it
does not turn an oracle intervention into a real retrieval or adoption gate.
