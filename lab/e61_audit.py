#!/usr/bin/env python3
"""Audit shared-source region containment and cost on complete frozen runs."""
import argparse
import hashlib
import json
from pathlib import Path


def covered(span, ranges):
    cursor, end = span
    for a, b in sorted(ranges):
        if b < cursor:
            continue
        if a > cursor:
            return False
        cursor = max(cursor, b + 1)
        if cursor > end:
            return True
    return False


def audit(path):
    manifest = json.loads(path.read_text())
    assert manifest["full_gate"] and "outputs_sha256" in manifest
    arms = {}
    for arm in ["baseline", "flag-off", "shared-source"]:
        raw = (path.parent / f"{manifest['slice']}_{arm}.jsonl").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest["outputs_sha256"][arm]
        rows = [json.loads(line) for line in raw.splitlines()]
        assert len(rows) == manifest["n"]
        arms[arm] = {r["instance_id"]: r for r in rows}
        assert set(arms[arm]) == set(manifest["ids"])
    changed, expanded, saved = [], [], 0
    for iid, base in arms["baseline"].items():
        off, after = arms["flag-off"][iid], arms["shared-source"][iid]
        assert not any(r.get("error") for r in [base, off, after]), iid
        assert base["payload_sha256"] == off["payload_sha256"], iid
        assert set(base["regions"]) == set(after["regions"]), iid
        assert after["tokens"] <= base["tokens"], iid
        saved += base["tokens"] - after["tokens"]
        for file, spans in base["regions"].items():
            assert all(covered(span, after["regions"][file]) for span in spans), (iid, file)
        if any(not covered(span, base["regions"][file])
               for file, spans in after["regions"].items() for span in spans):
            expanded.append(iid)
        if after["payload_sha256"] != base["payload_sha256"]:
            changed.append(iid)
    return {"slice": manifest["slice"], "n": manifest["n"],
            "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "flag_off_identical": True, "all_original_regions_contained": True,
            "all_original_files_retained": True, "no_instance_token_increase": True,
            "total_tokens_saved": saved, "changed_instances": changed,
            "expanded_instances": expanded,
            "limitation": "region/cost audit; alias source identity is separately tested in the engine"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    report = audit(args.manifest)
    args.manifest.with_name(report["slice"] + "_integrity.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in report.items()}))
