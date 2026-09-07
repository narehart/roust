#!/usr/bin/env python3
"""Score completed E51 arms with the existing exact language-aware scorer.

Run in an environment with pandas, pyarrow, scipy, tree_sitter, and the
tree_sitter_{javascript,typescript,java,go,rust,c,cpp} grammar packages.
"""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from collections import OrderedDict
import hashlib
from functools import lru_cache
import importlib.metadata
import json
from pathlib import Path
import sys

from e51_run import ROOT, sha256
import agentless_metric_full as scorer


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--reuse-baseline", type=Path, help="prior control JSONL; reuse metrics only after exact input/output identity")
    args = ap.parse_args()
    manifest = json.loads(args.manifest.read_text())
    assert "outputs_sha256" in manifest, "evaluation incomplete"
    packages = ["pandas", "pyarrow", "scipy", "tree_sitter", "tree_sitter_javascript",
                "tree_sitter_typescript", "tree_sitter_java", "tree_sitter_go", "tree_sitter_rust",
                "tree_sitter_c", "tree_sitter_cpp"]
    provenance = {"python": sys.version, "packages": {p: importlib.metadata.version(p) for p in packages},
                  "scorer_sha256": sha256(ROOT / "lab/agentless_metric_full.py"),
                  "scoring_helpers_sha256": sha256(ROOT / "lab/agentless_metric_verified.py"),
                  "gold_parser_sha256": sha256(ROOT / "parity/region_eval.py"),
                  "driver_sha256": sha256(Path(__file__)),
                  "span_cache": "4096 entries keyed by path, SHA256(source), and grammar gates"}
    args.manifest.with_name(manifest["slice"] + "_scoring.json").write_text(json.dumps(provenance, indent=2) + "\n")
    # Pure reads of immutable commit objects and pure parses. Reusing them
    # across arms avoids repeated git processes and grammar walks; no scoring
    # decisions are changed. Bounded caches keep large headers under control.
    scorer.amv.git_show = lru_cache(maxsize=256)(scorer.amv.git_show)
    original_spans = scorer.amv.function_spans_for_path
    span_cache = OrderedDict()

    def cached_spans(path, source):
        # Retain small hashes/spans rather than megabyte source strings as
        # LRU keys. This also keeps more immutable parses across whole arms.
        key = (path, hashlib.sha256(source.encode("utf8")).digest(),
               scorer.amv.TS_FUNCTIONS, scorer.amv.LANG_FUNCTIONS)
        if key in span_cache:
            span_cache.move_to_end(key)
            return span_cache[key]
        value = original_spans(path, source)
        span_cache[key] = value
        if len(span_cache) > 4096:
            span_cache.popitem(last=False)
        return value

    scorer.amv.function_spans_for_path = cached_spans
    for arm in manifest["arms"]:
        if arm == "flag-off":
            continue  # verified payload-identical separately
        predictions = args.manifest.parent / f"{manifest['slice']}_{arm}.jsonl"
        assert sha256(predictions) == manifest["outputs_sha256"][arm]
        ids = [json.loads(line)["instance_id"] for line in predictions.read_text().splitlines()]
        assert ids == manifest["ids"], "record order or membership changed"
        out = predictions.with_suffix(".metrics.json")
        log = predictions.with_suffix(".metrics.log")
        if arm == "baseline" and args.reuse_baseline:
            previous = args.reuse_baseline
            previous_manifest = json.loads(previous.with_name(manifest["slice"] + "_manifest.json").read_text())
            assert previous_manifest["gold_sha256"] == manifest["gold_sha256"]
            assert sha256(previous) == previous_manifest["outputs_sha256"]["baseline"]
            keys = ("instance_id", "repo", "base_commit", "error", "regions", "payload_sha256",
                    "hunk_line_recall", "all_gold_files_retrieved", "tokens", "n_gold_files", "engine_sha", "engine_dirty")
            def projection(path):
                return [{k: r.get(k) for k in keys} for r in map(json.loads, path.read_text().splitlines())]
            assert projection(previous) == projection(predictions), "control changed; cannot reuse scores"
            previous_metrics = previous.with_suffix(".metrics.json")
            reused = json.loads(previous_metrics.read_text())
            reused["source"]["reuse_verified_against"] = str(predictions)
            reused["source"]["original_metrics_sha256"] = sha256(previous_metrics)
            out.write_text(json.dumps(reused, indent=2) + "\n")
            print(manifest["slice"], "baseline metrics reused after complete control identity proof", flush=True)
            continue
        with log.open("w") as stream:
            old_argv = sys.argv
            sys.argv = [
                str(ROOT / "lab/agentless_metric_full.py"),
                "--predictions", str(predictions), "--gold-parquet", str(ROOT / manifest["gold"]),
                "--repos-dir", manifest["repos"], "--expect-n", str(manifest["n"]),
                "--ts-functions", "--lang-functions", "--out", str(out),
            ]
            try:
                with redirect_stdout(stream), redirect_stderr(stream):
                    scorer.main()
            finally:
                sys.argv = old_argv
        metrics = json.loads(out.read_text())["all_instances"]
        assert metrics["n"] == manifest["n"]
        print(manifest["slice"], arm, "FILE", metrics["file"]["pct_correct"],
              "FUNCTION", metrics["function"]["pct_correct"],
              "LINE", metrics["line"]["pct_correct_all_or_nothing"],
              "fraction", metrics["line"]["mean_fraction_covered"], flush=True)


if __name__ == "__main__":
    main()
