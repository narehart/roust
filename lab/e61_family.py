#!/usr/bin/env python3
"""Apply the complete registered discovery family correction to paired reports."""
import argparse
import hashlib
import json
from pathlib import Path

FAMILY = {"e56": {"dense10", "hybrid26"}, "e57": {"semantic-regions"},
          "e58": {"ast-semantic"}, "e60": {"leading-comments"},
          "e61": {"shared-source"}, "e63": {"cross-rerank"}}


def summarize(root):
    rows, sources = [], {}
    candidates = sum(map(len, FAMILY.values()))
    tests = candidates * 2 * 3
    for experiment, arms in FAMILY.items():
        for language, expected in [("rust", 239), ("cpp", 129)]:
            path = root / experiment / "discovery" / f"{language}_paired.json"
            data = path.read_bytes()
            report = json.loads(data)
            assert report["full_gate"] and report["n"] == expected
            assert report["slice"] == language and set(report["arms"]) == arms
            assert report["flag_off_payload_identical"] == expected
            sources[str(path)] = hashlib.sha256(data).hexdigest()
            for arm in sorted(arms):
                result = report["arms"][arm]
                row = {"experiment": experiment, "slice": language, "arm": arm,
                       "baseline_errors": report["baseline_errors"],
                       "treatment_errors": result["errors"]}
                for endpoint in ["file", "function", "line"]:
                    row[endpoint] = dict(result[endpoint])
                    row[endpoint]["p_bonferroni_full_family"] = min(1.0, tests * result[endpoint]["mcnemar_p"])
                row["fraction"] = result["fraction"]
                row["tokens"] = result["tokens"]
                rows.append(row)
    return {"kind": "complete discovery family; not a final adoption or parity gate",
            "candidates": candidates, "slices": 2, "binary_endpoints": 3, "bonferroni_tests": tests,
            "fraction_intervals": "descriptive paired bootstrap, unadjusted",
            "paired_reports_sha256": sources, "results": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("lab/results_regions"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.root)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
