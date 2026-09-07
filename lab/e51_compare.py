#!/usr/bin/env python3
"""Strict paired E51 summaries; errors stay wrong and missing IDs are fatal."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest


def records(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert len({r["instance_id"] for r in rows}) == len(rows), "duplicate record"
    return {r["instance_id"]: r for r in rows}


def metrics(path, ids):
    d = json.loads(path.read_text())["all_instances"]
    assert d["n"] == len(ids)
    rows = d["function"]["detail"]
    assert len({r["instance_id"] for r in rows}) == len(rows)
    assert {r["instance_id"] for r in rows}.issubset(ids)
    return {r["instance_id"]: r for r in rows}, d


def paired_bool(before, after, n_arms=3, discovery_endpoints=2):
    gained = sum(not b and a for b, a in zip(before, after))
    lost = sum(b and not a for b, a in zip(before, after))
    p = float(binomtest(gained, gained + lost).pvalue) if gained + lost else 1.0
    return {"baseline_pct": 100 * sum(before) / len(before),
            "treatment_pct": 100 * sum(after) / len(after),
            "gained": gained, "lost": lost, "mcnemar_p": p,
            "p_bonferroni_candidate_arms": min(1.0, n_arms * p),
            ("p_bonferroni_discovery_function_line" if discovery_endpoints == 2 else "p_bonferroni_discovery_file_function_line"): min(1.0, 2 * discovery_endpoints * n_arms * p)}


def continuous(before, after):
    delta = np.asarray(after, dtype=float) - np.asarray(before, dtype=float)
    rng = np.random.default_rng(20260907)
    means = np.array([delta[rng.integers(0, len(delta), len(delta))].mean() for _ in range(10000)])
    return {"baseline_mean": float(np.mean(before)), "treatment_mean": float(np.mean(after)),
            "mean_delta": float(delta.mean()), "paired_bootstrap_95_ci": np.quantile(means, [0.025, 0.975]).tolist(),
            "gained": int((delta > 0).sum()), "lost": int((delta < 0).sum())}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", type=Path)
    args = ap.parse_args()
    m = json.loads(args.manifest.read_text())
    assert "outputs_sha256" in m, "evaluation incomplete"
    base_path = args.manifest.parent / f"{m['slice']}_baseline.jsonl"
    base = records(base_path)
    ids = sorted(base)
    assert set(ids) == set(m["ids"]) and len(ids) == m["n"]
    bf, bm = metrics(base_path.with_suffix(".metrics.json"), set(ids))
    result = {"slice": m["slice"], "n": len(ids), "full_gate": m["full_gate"],
              "baseline_errors": [i for i in ids if base[i].get("error")], "arms": {}}
    if "flag-off" in m["arms"]:
        off = records(args.manifest.parent / f"{m['slice']}_flag-off.jsonl")
        assert set(off) == set(base)
        differences = [i for i in ids if (base[i].get("error"), base[i].get("payload_sha256")) !=
                       (off[i].get("error"), off[i].get("payload_sha256"))]
        assert not differences, f"flag-off payload drift: {differences}"
        result["flag_off_payload_identical"] = len(ids)
    for arm in m["arms"]:
        if arm in ("baseline", "flag-off"):
            continue
        path = args.manifest.parent / f"{m['slice']}_{arm}.jsonl"
        after = records(path)
        assert set(after) == set(base), "paired sets differ"
        af, am = metrics(path.with_suffix(".metrics.json"), set(ids))
        def values(recs, func, key):
            if key == "function":
                return [not recs[i].get("error") and func.get(i, {}).get("correct", False) for i in ids]
            if key == "file":
                return [not recs[i].get("error") and recs[i].get("all_gold_files_retrieved", False) for i in ids]
            return [not recs[i].get("error") and recs[i].get("hunk_line_recall") == 1 for i in ids]
        n_arms = len(set(m["arms"]) - {"baseline", "flag-off"})
        pairs = {key: paired_bool(values(base, bf, key), values(after, af, key), n_arms, m.get("discovery_endpoints", 2)) for key in ("file", "function", "line")}
        if not {"--max-additions", "--local-feedback", "dense10", "hybrid26"}.intersection(m["arms"][arm]):
            assert pairs["file"]["gained"] == pairs["file"]["lost"] == 0, "packing changed FILE"
        pairs["fraction"] = continuous([base[i].get("hunk_line_recall") or 0 for i in ids],
                                       [after[i].get("hunk_line_recall") or 0 for i in ids])
        # Costs on pairs successful in both arms, explicitly report the size.
        ok = [i for i in ids if not base[i].get("error") and not after[i].get("error")]
        pairs["tokens"] = continuous([base[i]["tokens"] for i in ok], [after[i]["tokens"] for i in ok])
        pairs["tokens"]["n_successful_pairs"] = len(ok)
        pairs["errors"] = [i for i in ids if after[i].get("error")]
        for label, f, met in (("baseline", bf, bm), ("treatment", af, am)):
            nonzero = [v for v in f.values() if v.get("n_gold_functions", 0) > 0]
            pairs[label + "_function_nonvacuous"] = {"n": len(nonzero), "correct": sum(v["correct"] for v in nonzero),
                                                       "zero_gold_function_n": sum(v.get("n_gold_functions", 0) == 0 for v in f.values()),
                                                       "git_show_failures": met["function"].get("n_git_show_failures_counted_wrong", 0)}
        result["arms"][arm] = pairs
        print(m["slice"], arm, json.dumps({k: v for k, v in pairs.items() if k in ("file", "function", "line", "fraction", "tokens")}))
    out = args.manifest.with_name(m["slice"] + "_paired.json")
    out.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
