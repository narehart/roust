#!/usr/bin/env python3
"""Archive/restore the exact five evaluation fields, excluding unused columns.

Restored parquet bytes may differ; canonical evaluation rows must match.
Existing files are verified, never overwritten. Python Verified is excluded.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd
from e51_run import ROOT, SLICES, sha256

COLUMNS = ["instance_id", "repo", "base_commit", "patch", "problem_statement"]


def canonical(path):
    rows = pd.read_parquet(path)[COLUMNS].to_dict("records")
    assert len({r["instance_id"] for r in rows}) == len(rows)
    rows.sort(key=lambda r: (r["repo"], r["instance_id"]))
    return ("\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows) + "\n").encode()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["snapshot", "restore"])
    ap.add_argument("--lab-dir", type=Path, default=ROOT / "lab")
    args = ap.parse_args()
    archive = ROOT / "lab/results_regions/e51/inputs"
    index_path = archive / "manifest.json"
    if args.mode == "snapshot":
        archive.mkdir(parents=True, exist_ok=True)
        index = {"columns": COLUMNS, "datasets": {}}
        for name, (pq, _, n) in SLICES.items():
            if name == "ver":
                continue
            source = args.lab_dir / pq
            raw = canonical(source)
            assert len(raw.splitlines()) == n
            dest = archive / (name + ".jsonl.gz")
            dest.write_bytes(gzip.compress(raw, mtime=0))
            index["datasets"][name] = {"original_path": pq, "original_sha256": sha256(source),
                                      "snapshot": dest.name, "snapshot_sha256": sha256(dest),
                                      "rows_sha256": hashlib.sha256(raw).hexdigest(), "n": n}
        index_path.write_text(json.dumps(index, indent=2) + "\n")
    else:
        index = json.loads(index_path.read_text())
        args.lab_dir.mkdir(parents=True, exist_ok=True)
        for name, item in index["datasets"].items():
            snapshot = archive / item["snapshot"]
            assert sha256(snapshot) == item["snapshot_sha256"]
            raw = gzip.decompress(snapshot.read_bytes())
            assert hashlib.sha256(raw).hexdigest() == item["rows_sha256"]
            dest = args.lab_dir / item["original_path"]
            if dest.exists():
                if canonical(dest) != raw:
                    raise SystemExit(f"Refusing to overwrite different evaluation data: {dest}")
            else:
                rows = [json.loads(line) for line in raw.splitlines()]
                pd.DataFrame(rows).to_parquet(dest, index=False)
                assert canonical(dest) == raw
            print(f"Verified {name}: {item['n']} exact evaluation rows")


if __name__ == "__main__":
    main()
