#!/usr/bin/env python3
"""Validate E55 controls and summarize the gold-informed intervention."""
import argparse
from collections import Counter
import json
from pathlib import Path

from e51_run import sha256


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", type=Path)
    args = ap.parse_args()
    m = json.loads(args.manifest.read_text())
    assert "outputs_sha256" in m
    rows = {}
    for arm, digest in m["outputs_sha256"].items():
        p = args.manifest.parent / f"{m['slice']}_{arm}.jsonl"
        assert sha256(p) == digest
        rows[arm] = [json.loads(x) for x in p.read_text().splitlines()]
        assert [r["instance_id"] for r in rows[arm]] == m["ids"]
    assert len(set(m["ids"])) == m["n"]
    for b, o in zip(rows["baseline"], rows["flag-off"]):
        assert not b["error"] and not o["error"], (b["instance_id"], b["error"], o["error"])
        assert b["payload_sha256"] == o["payload_sha256"], b["instance_id"]
    report = {"kind": "oracle diagnostic, not deployable retrieval", "n": m["n"],
              "slice": m["slice"], "control_payloads_identical": m["n"], "arms": {}}
    for arm in ["baseline", "oracle-files"]:
        rr = rows[arm]
        p = args.manifest.parent / f"{m['slice']}_{arm}.metrics.json"
        metrics = json.loads(p.read_text())["all_instances"]
        assert metrics["n"] == m["n"]
        report["arms"][arm] = {
            "file": metrics["file"],
            "function": {k: v for k, v in metrics["function"].items() if k != "detail"},
            "line_pct": 100 * sum(not r["error"] and r.get("hunk_line_recall") == 1 for r in rr) / m["n"],
            "fraction_errors_zero": sum(0 if r["error"] else r.get("hunk_line_recall") or 0 for r in rr) / m["n"],
            "mean_tokens_successes": sum(r["tokens"] for r in rr if not r["error"]) / sum(not r["error"] for r in rr),
            "errors": [r["instance_id"] for r in rr if r["error"]],
        }
    absent = {r["instance_id"]: r["e55_diagnostic"]["absent_files"]
              for r in rows["oracle-files"] if not r["error"] and r["e55_diagnostic"]["absent_files"]}
    report["absent_gold"] = {"instances": len(absent), "by_instance": absent,
        "suffix_occurrences": dict(Counter(Path(f).suffix for fs in absent.values() for f in fs))}
    out = args.manifest.with_name(m["slice"] + "_diagnosis.json")
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "absent_gold"}, indent=2))


if __name__ == "__main__":
    main()
