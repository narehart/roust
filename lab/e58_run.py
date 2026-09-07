#!/usr/bin/env python3
"""AST-unit/native-inference treatment with E57's unchanged packing policy."""
import argparse
import importlib.metadata
import json
from pathlib import Path

import e57_run as run
from e58_native import NativeRetriever


if __name__ == "__main__":
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--slice", required=True)
    ap.add_argument("--embedding-cache", type=Path, required=True)
    args, _ = ap.parse_known_args()
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{args.slice}_native_environment.json"
    assert not path.exists()
    path.write_text(json.dumps({
        "packages": {p: importlib.metadata.version(p) for p in ["mlx", "mlx-lm", "transformers", "tokenizers"]},
        "source_sha256": {f: run.rig.sha256(Path(__file__).with_name(f)) for f in
                          ["e58_run.py", "e58_native.py", "e58_units.py"]}}, indent=2) + "\n")
    run.RegionRetriever = NativeRetriever
    run.rig.ARMS = {"baseline": [], "flag-off": [], "ast-semantic": ["--semantic-regions"]}
    run.main()
