#!/usr/bin/env python3
"""Frozen E51 arms through the existing evaluator, using private local clones.

Gold is consumed only by region_eval_verified's scorer; the engine receives
only problem_statement and the base-commit checkout, as in the existing rig.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "parity"))
import region_eval_verified as evaluator

SLICES = {
    "rust": ("ws3a_rust.parquet", "ws3a_repos/rust_base", 239),
    "cpp": ("mswe_cpp.parquet", "ws3a_repos/cpp_base", 129),
    "java": ("ws3b_java.parquet", "ws3b_repos/java_base", 128),
    "go": ("mswe_go.parquet", "ws3b_repos/go_base", 428),
    "jsts": ("mswe_jsts.parquet", "mswe_repos_e23", 580),
    "c": ("mswe_c.parquet", "ws3b_repos/c_base", 128),
    "lite": ("swebench_lite.parquet", "swebench_repos_e20b", 300),
    "ver": ("swebench_verified_heldout.parquet", "ws3a_repos/repos_ver_v2", 407),
}
ARMS = {
    "baseline": [],
    "flag-off": [],
    "shape-union": ["--shape-union-blocks"],
    "hit-windows": ["--hit-window-blocks"],
    "wide-hit-windows": ["--hit-window-blocks", "--symbol-graph", "--max-additions", "32"],
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slice", choices=SLICES, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--experiment", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    ap.add_argument("--limit", type=int, default=0, help="smoke only; not a full gate")
    ap.add_argument("--timeout", type=float, default=180)
    args = ap.parse_args()
    if len(set(args.arms)) != len(args.arms):
        ap.error("duplicate arms")
    args.out.mkdir(parents=True, exist_ok=True)
    paths = {arm: args.out / f"{args.slice}_{arm}.jsonl" for arm in args.arms}
    if any(p.exists() for p in paths.values()):
        ap.error("output already exists; use a new output directory")
    pq, repo_dir, expected = SLICES[args.slice]
    gold = ROOT / "lab" / pq
    rows = evaluator.load_verified_rows(gold, args.limit)
    if not args.limit:
        assert len(rows) == expected
    assert len({r["instance_id"] for r in rows}) == len(rows)
    binaries = {"baseline": args.baseline.resolve(), "experiment": args.experiment.resolve()}
    versions = {}
    for tag, binary in binaries.items():
        version = subprocess.check_output([str(binary), "--version"], text=True).strip()
        assert "clean" in version and "dirty" not in version, version
        versions[tag] = {"path": str(binary), "sha256": sha256(binary), "version": version}
    private = Path(tempfile.mkdtemp(prefix=f"bgrep-e51-{args.slice}-", dir="/private/tmp"))
    manifest = {"slice": args.slice, "n": len(rows), "full_gate": not args.limit,
                "gold": str(gold.relative_to(ROOT)), "gold_sha256": sha256(gold),
                "ids": [r["instance_id"] for r in rows], "binaries": versions,
                "arms": {arm: ARMS[arm] for arm in args.arms}, "repos": str(private),
                "budget": 8192, "pad_lines": 5, "len_exp": 0.85, "timeout": args.timeout}
    manifest_path = args.out / f"{args.slice}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    evaluator.SWEBENCH_REPOS = private
    evaluator.BUDGET = 8192
    original_run = evaluator.run_roust
    last_payload = {}

    def capture_run(*a, **kw):
        obj, error = original_run(*a, **kw)
        last_payload.clear()
        if obj:
            payload = {k: obj[k] for k in ("regions", "bundle") if k in obj}
            # Also catches formatting/truncation changes beyond span equality.
            assert "bundle" in payload, "engine JSON no longer exposes bundle"
            last_payload["payload_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return obj, error

    evaluator.run_roust = capture_run
    checked_out = {}

    def private_checkout(path, commit):
        assert path.parent == private
        if checked_out.get(path) != commit:
            subprocess.run(["git", "checkout", "-f", "-q", commit], cwd=path, check=True, capture_output=True)
            subprocess.run(["git", "clean", "-fdq", "-e", ".roust/"], cwd=path, check=True, capture_output=True)
            checked_out[path] = commit

    evaluator.checkout = private_checkout
    started = time.monotonic()
    for index, row in enumerate(rows, 1):
        rel = row["repo"].replace("/", "__")
        destination = private / rel
        if not destination.exists():
            source = ROOT / "lab" / repo_dir / rel
            subprocess.run(["git", "clone", "--shared", "--no-checkout", "--quiet", str(source), str(destination)], check=True)
        for arm in args.arms:
            evaluator.ROUST_BIN = binaries["baseline" if arm == "baseline" else "experiment"]
            evaluator.EXTRA_ENGINE_FLAGS = ARMS[arm]
            last_payload.clear()
            rec = evaluator.eval_verified_instance(row, args.timeout, 5, 0.85)
            rec.update(last_payload)
            rec["e51_arm"] = arm
            rec["e51_flags"] = ARMS[arm]
            with paths[arm].open("a") as out:
                out.write(json.dumps(rec, separators=(",", ":")) + "\n")
        if index % 5 == 0 or index == len(rows):
            print(f"{args.slice}: {index}/{len(rows)}, {time.monotonic() - started:.1f}s", flush=True)
    for tag, binary in binaries.items():
        assert sha256(binary) == versions[tag]["sha256"], "binary changed during run"
    manifest["elapsed_seconds"] = time.monotonic() - started
    manifest["outputs_sha256"] = {arm: sha256(p) for arm, p in paths.items()}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
