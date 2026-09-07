#!/usr/bin/env python3
"""E55 oracle-file diagnosis; NEVER interpret oracle output as retrieval.

Uses E51 private clones, frozen binaries, input hashes and existing scorer.
The baseline is the shipped CLI. Flag-off is the lab example without a file
override and must reproduce baseline payloads. Oracle-files supplies sorted
old-side gold paths, preserving lexical scores and all packing parameters.
"""
import json
import subprocess

import e51_run as rig

rig.ARMS = {"baseline": [], "flag-off": [], "oracle-files": ["oracle-files"]}
rig.ISOLATE_BLOCK_CACHE = True
original_run = rig.evaluator.run_roust
original_eval = rig.evaluator.eval_verified_instance
current = {}
diagnostic = {}


def run(query, repo_path, timeout, pad_lines, len_exp):
    diagnostic.clear()
    if rig.evaluator.ROUST_BIN.name != "research_pack":
        return original_run(query, repo_path, timeout, pad_lines, len_exp)
    assert pad_lines == 5 and len_exp == 0.85
    request = {"repo": str(repo_path), "query": query}
    if rig.evaluator.EXTRA_ENGINE_FLAGS:
        request["files"] = sorted(rig.evaluator.parse_gold_hunks(current["patch"]))
    try:
        proc = subprocess.run([str(rig.evaluator.ROUST_BIN)], input=json.dumps(request),
                              capture_output=True, text=True, timeout=timeout)
        if proc.returncode:
            return None, f"exit {proc.returncode}: {proc.stderr[:300]}"
        obj = json.loads(proc.stdout)
        diagnostic.update(obj["diagnostic"])
        return obj, None
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        return None, str(exc)


def evaluate(row, *args):
    current.clear()
    current.update(row)
    diagnostic.clear()
    result = original_eval(row, *args)
    result["e55_diagnostic"] = dict(diagnostic)
    return result


if __name__ == "__main__":
    rig.evaluator.run_roust = run
    rig.evaluator.eval_verified_instance = evaluate
    rig.main()
