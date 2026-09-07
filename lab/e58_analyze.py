#!/usr/bin/env python3
"""Summarize cache-workload mining, without making latency/recall claims."""
import argparse
import json
from pathlib import Path
from e51_run import sha256


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", type=Path)
    args = ap.parse_args()
    m = json.loads(args.manifest.read_text())
    path = args.manifest.parent / f"{m['slice']}_baseline.jsonl"
    assert sha256(path) == m["outputs_sha256"]["baseline"]
    rows = [json.loads(s) for s in path.read_text().splitlines()]
    assert [r["instance_id"] for r in rows] == m["ids"]
    assert all(not r["error"] for r in rows)
    keys = ["n_chunks", "new_unique", "new_payload_tokens", "padded_tokens_batch8", "attention_cells_batch8"]
    totals = {method: {k: sum(r["e58_reuse"][method][k] for r in rows) for k in keys}
              for method in ["windows", "ast"]}
    result = {"kind": "source workload diagnostic; no model inference", "slice": m["slice"],
              "n": len(rows), "totals": totals,
              "ast_over_windows": {k: totals["ast"][k] / totals["windows"][k] for k in keys}}
    args.manifest.with_name(m["slice"] + "_reuse_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
