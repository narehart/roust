#!/usr/bin/env python3
"""E51: decompose the existing scoreboard without changing its gold definition.

Reads archived E47 predictions and the same gold-hunk parser as the evaluator.
No checkout, engine invocation, or Python Verified inspection is performed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "parity"))
from region_eval import parse_gold_hunks

SLICES = {
    "lite": ("swebench_lite.parquet", "lite_ts40"),
    "jsts": ("mswe_jsts.parquet", "jsts_ts40ship"),
    "java": ("ws3b_java.parquet", "java_ts40ship"),
    "go": ("mswe_go.parquet", "go_ts40ship"),
    "rust": ("ws3a_rust.parquet", "rust_ts40ship"),
    "c": ("mswe_c.parquet", "c_ts40ship"),
    "cpp": ("mswe_cpp.parquet", "cpp_ts40ship"),
}
# A fixed diagnostic definition, not an engine indexing change or a replacement
# for the published metric. Includes source forms the engine does not index.
SOURCE_EXT = set(".py .pyi .js .jsx .ts .tsx .mjs .cjs .svelte .vue .java .kt .go .rs .c .h .cc .cpp .cxx .hh .hpp .hxx .rb .pony .cs .swift .scala .sh".split())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(rows):
    n = len(rows)
    source_rows = [r for r in rows if r["source_files"]]
    return {
        "n": n,
        "errors": sum(r["error"] for r in rows),
        "file_pct": 100 * sum(r["file_ok"] for r in rows) / n,
        "source_eligible_n": len(source_rows),
        "source_file_pct": 100 * sum(r["source_file_ok"] for r in source_rows) / len(source_rows) if source_rows else None,
        "line_fraction": sum(r["fraction"] for r in rows) / n,
        "mean_tokens": sum(r["tokens"] for r in rows if not r["error"]) / max(1, sum(not r["error"] for r in rows)),
        "gold_lines": sum(r["gold_lines"] for r in rows),
        "covered_lines": sum(r["covered_lines"] for r in rows),
        "missing_lines_absent_file": sum(r["missing_lines_absent_file"] for r in rows),
        "missing_lines_present_file": sum(r["missing_lines_present_file"] for r in rows),
        "source_gold_lines": sum(r["source_gold_lines"] for r in rows),
        "source_missing_lines_absent_file": sum(r["source_missing_lines_absent_file"] for r in rows),
        "source_missing_lines_present_file": sum(r["source_missing_lines_present_file"] for r in rows),
    }


def main():
    import pandas as pd
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = {"source_extensions": sorted(SOURCE_EXT), "slices": {}}
    for name, (pq, arm) in SLICES.items():
        gold_path = ROOT / "lab" / pq
        pred_path = ROOT / "lab/results_regions/e47/arms" / (arm + ".jsonl")
        metric_path = ROOT / "lab/results_regions/e44/metrics" / (arm + ".json")
        gold = {r["instance_id"]: r for r in pd.read_parquet(gold_path).to_dict("records")}
        preds = [json.loads(line) for line in pred_path.read_text().splitlines() if line.strip()]
        assert len({p["instance_id"] for p in preds}) == len(preds), "duplicate predictions"
        assert set(gold) == {p["instance_id"] for p in preds}, f"{name}: gold/prediction IDs differ"
        rows, extensions = [], Counter()
        for pred in preds:
            g = gold[pred["instance_id"]]
            assert g["base_commit"] == pred["base_commit"]
            hunks = parse_gold_hunks(g["patch"])
            assert len(hunks) == pred["n_gold_files"]
            regions = {} if pred.get("error") else pred["regions"]
            sources = {f for f in hunks if Path(f).suffix.lower() in SOURCE_EXT}
            r = dict(instance_id=pred["instance_id"], repo=g["repo"], gold_files=len(hunks),
                     source_files=len(sources), error=bool(pred.get("error")),
                     file_ok=bool(hunks) and set(hunks).issubset(regions),
                     source_file_ok=bool(sources) and sources.issubset(regions),
                     tokens=pred.get("tokens") or 0)
            for k in ("gold_lines", "covered_lines", "missing_lines_absent_file", "missing_lines_present_file",
                      "source_gold_lines", "source_missing_lines_absent_file", "source_missing_lines_present_file"):
                r[k] = 0
            for f, spans in hunks.items():
                lines = {ln for a, b in spans for ln in range(a, b + 1)}
                covered = sum(any(a <= ln <= b for a, b in regions.get(f, [])) for ln in lines)
                missing = len(lines) - covered
                category = "missing_lines_present_file" if f in regions else "missing_lines_absent_file"
                r["gold_lines"] += len(lines)
                r["covered_lines"] += covered
                r[category] += missing
                if f in sources:
                    r["source_gold_lines"] += len(lines)
                    r["source_" + category] += missing
                if f not in regions:
                    extensions[Path(f).suffix.lower() or "<no extension>"] += 1
            r["fraction"] = r["covered_lines"] / r["gold_lines"] if r["gold_lines"] else 0
            assert r["file_ok"] == bool(pred.get("all_gold_files_retrieved"))
            assert abs(r["fraction"] - (pred.get("hunk_line_recall") or 0)) < 1e-10
            rows.append(r)
        function = json.loads(metric_path.read_text())["all_instances"]["function"]
        nonzero = [r for r in function["detail"] if r["n_gold_functions"] > 0]
        assert {r["instance_id"] for r in function["detail"]}.issubset(gold)
        report["slices"][name] = {
            "provenance": {"gold": str(gold_path.relative_to(ROOT)), "gold_sha256": digest(gold_path),
                           "predictions": str(pred_path.relative_to(ROOT)), "predictions_sha256": digest(pred_path),
                           "metrics": str(metric_path.relative_to(ROOT)), "metrics_sha256": digest(metric_path),
                           "engine_shas": sorted({p["engine_sha"] for p in preds}, key=str)},
            "overall": summarize(rows),
            "function_diagnostic": {"published_pct": function["pct_correct"],
                                    "zero_gold_functions": len(function["detail"]) - len(nonzero),
                                    "nonzero_n": len(nonzero), "nonzero_correct": sum(r["correct"] for r in nonzero)},
            "by_gold_files": {str(k): summarize([r for r in rows if r["gold_files"] == k]) for k in sorted({r["gold_files"] for r in rows})},
            "missing_extensions": dict(extensions.most_common()),
            "instances": rows,
        }
        s = report["slices"][name]["overall"]
        print(name, json.dumps(s), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
