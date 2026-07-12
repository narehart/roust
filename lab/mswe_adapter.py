"""Multi-SWE-bench (ByteDance-Seed) TypeScript/JavaScript adapter.

Downloads the ts/ and js/ dataset JSONL files listed at
https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench/tree/main
(via the HF tree API), converts each record to the swebench_driver2.py
schema (mirrors swebench_lite.parquet's columns exactly), and writes
mswe_jsts.parquet.

Per-record mapping:
  repo               = org + "/" + repo
  instance_id         = as-is
  base_commit         = base.sha
  patch               = fix_patch  (unified diff, "diff --git a/<path> b/..."
                         headers -- matches swebench_driver2._DIFF_FILE_RE)
  problem_statement   = PR title + "\n\n" + PR body + "\n\n" +
                         concatenated resolved_issues[].title + body
  test_patch          = test_patch (as-is)
  hints_text          = hints (as-is)
  FAIL_TO_PASS        = JSON list of f2p_tests dict keys (sorted)
  PASS_TO_PASS        = JSON list of p2p_tests dict keys (sorted)
  created_at, version = not present in Multi-SWE-bench records; left "" (unused
                         by the driver -- see load_instances() in
                         swebench_driver2.py, which only reads instance_id,
                         repo, base_commit, problem_statement, patch)
  environment_setup_commit = base.sha (no separate env-setup commit in the
                         source schema; the driver never reads this column)

Records with an empty/missing fix_patch or base.sha are dropped (no gold
patch to score against / can't checkout) and counted in the skip report.

Usage:  uv run python mswe_adapter.py [--cache-dir DIR] [--out PATH] [--langs ts js]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent

HF_API_TREE = "https://huggingface.co/api/datasets/ByteDance-Seed/Multi-SWE-bench/tree/main/{lang}"
HF_RESOLVE = "https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench/resolve/main/{path}"

LANGS = ["ts", "js"]

# Exact column set/order of swebench_lite.parquet (verified against the
# existing SWE-bench Lite cache in this LAB dir).
COLUMNS = [
    "repo", "instance_id", "base_commit", "patch", "test_patch",
    "problem_statement", "hints_text", "created_at", "version",
    "FAIL_TO_PASS", "PASS_TO_PASS", "environment_setup_commit",
]


def list_files(lang: str) -> list[dict]:
    url = HF_API_TREE.format(lang=lang)
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = json.loads(resp.read())
    return [f for f in data if f.get("type") == "file" and f["path"].endswith(".jsonl")]


def download(path: str, dest: Path) -> None:
    if dest.exists():
        return
    url = HF_RESOLVE.format(path=path)
    print(f"downloading {path} -> {dest}", flush=True)
    tmp = dest.with_name(dest.name + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)


def convert_record(rec: dict) -> dict | None:
    org = rec.get("org") or ""
    repo = rec.get("repo") or ""
    base_sha = (rec.get("base") or {}).get("sha") or ""
    patch = rec.get("fix_patch") or ""
    if not org or not repo or not base_sha or not patch.strip():
        return None

    title = rec.get("title") or ""
    body = rec.get("body") or ""
    issue_parts = []
    for ri in rec.get("resolved_issues") or []:
        issue_parts.append((ri.get("title") or "") + "\n" + (ri.get("body") or ""))
    issue_text = "\n\n".join(issue_parts)
    problem_statement = title + "\n\n" + body + "\n\n" + issue_text

    f2p = sorted((rec.get("f2p_tests") or {}).keys())
    p2p = sorted((rec.get("p2p_tests") or {}).keys())

    return {
        "repo": f"{org}/{repo}",
        "instance_id": rec["instance_id"],
        "base_commit": base_sha,
        "patch": patch,
        "test_patch": rec.get("test_patch") or "",
        "problem_statement": problem_statement,
        "hints_text": rec.get("hints") or "",
        "created_at": "",
        "version": "",
        "FAIL_TO_PASS": json.dumps(f2p),
        "PASS_TO_PASS": json.dumps(p2p),
        "environment_setup_commit": base_sha,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default=str(LAB_DIR / "mswe_raw"),
                     help="local dir for the raw per-repo .jsonl downloads")
    ap.add_argument("--out", default=str(LAB_DIR / "mswe_jsts.parquet"))
    ap.add_argument("--langs", nargs="+", default=LANGS)
    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    seen_ids: set[str] = set()
    dup = 0
    skipped = 0
    per_file_stats: list[tuple[str, str, int, int]] = []  # lang, fname, kept, total

    for lang in args.langs:
        files = list_files(lang)
        print(f"{lang}/: {len(files)} dataset files", flush=True)
        for f in files:
            path = f["path"]
            fname = Path(path).name
            dest = cache_dir / fname
            download(path, dest)

            total = 0
            kept = 0
            with dest.open() as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    total += 1
                    rec = json.loads(line)
                    conv = convert_record(rec)
                    if conv is None:
                        skipped += 1
                        continue
                    if conv["instance_id"] in seen_ids:
                        dup += 1
                        continue
                    seen_ids.add(conv["instance_id"])
                    records.append(conv)
                    kept += 1
            per_file_stats.append((lang, fname, kept, total))
            print(f"  {fname}: {kept}/{total} instances kept", flush=True)

    import pandas as pd
    df = pd.DataFrame(records, columns=COLUMNS)
    out_path = Path(args.out)
    df.to_parquet(out_path, index=False)
    print(f"\nwrote {len(df)} instances -> {out_path}", flush=True)
    print(f"skipped (missing patch/org/repo/base_sha): {skipped}, duplicate instance_ids: {dup}")
    print("\nper-repo instance counts:")
    for lang, fname, kept, total in per_file_stats:
        print(f"  {lang}/{fname}: {kept}/{total}")
    print("\nrepo counts in final parquet:")
    print(df["repo"].value_counts().to_string())


if __name__ == "__main__":
    main()
