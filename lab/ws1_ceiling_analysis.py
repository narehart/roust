"""WS1 pre-run analysis over the 135 ceiling-blocked MSWE instances.

For every instance with >=1 gold file outside CODE_EXTENSIONS, check out the
base commit in a PRIVATE scratchpad clone and evaluate each out-of-allowlist
gold file against the --index-all inclusion chain:
  vendor regex -> 2MB size cap -> content sniff (NUL/UTF-8, first 8KB)
  -> 3000-char max-line filter.
Reports: recoverable vs still-blocked (and why), size distribution of
currently-indexed vs newly-admitted files on each repo's first checkout,
and whether any repo has node_modules under git control.
"""
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

MAIN_REPO = Path("/Users/nicholasarehart/programming-projects/bgrep")
CLONES = Path(sys.argv[1])
sys.path.insert(0, str(MAIN_REPO / "parity"))
from region_eval import parse_gold_hunks  # noqa: E402

import pandas as pd

CODE_EXTS = {".py", ".ts", ".js", ".go", ".rs", ".java", ".kt", ".cs",
             ".swift", ".tsx", ".jsx"}
VENDOR_RE = re.compile(r"(?i)(vendor|vendored|third_party|node_modules|\.min\.(js|css)$|bundle\.js$)")
MAX_FILE_BYTES = 2_000_000
MAX_LINE_CHARS = 3000


def suffix_of(rel: str) -> str:
    name = rel.rsplit("/", 1)[-1]
    i = name.rfind(".")
    return name[i:] if i > 0 else ""


def sniff_is_text(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError as e:
        # tolerate only an incomplete multi-byte char truncated at the cut
        return e.start + 1 >= len(head) - 3 and e.reason.startswith("unexpected end")


def classify(full: Path, rel: str) -> str:
    """Return 'recoverable' or the first blocking reason."""
    if VENDOR_RE.search(rel):
        return "vendor_re"
    if not full.is_file():
        return "missing_on_disk"
    size = full.stat().st_size
    if size > MAX_FILE_BYTES:
        return "size_cap"
    data = full.read_bytes()
    if not sniff_is_text(data[:8192]):
        return "sniff_binary"
    text = data.decode("utf-8", errors="replace")
    maxlen = max((len(l) for l in text.splitlines()), default=0)
    if maxlen > MAX_LINE_CHARS:
        return "long_line"
    return "recoverable"


df = pd.read_parquet(MAIN_REPO / "lab/mswe_jsts.parquet")
df = df.sort_values(["repo", "instance_id"]).reset_index(drop=True)
df["slug"] = df["repo"].str.replace("/", "__")

blocked = []
for _, row in df.iterrows():
    gold = sorted(parse_gold_hunks(row["patch"]).keys())
    outside = [f for f in gold if suffix_of(f) not in CODE_EXTS]
    if outside:
        blocked.append((row, gold, outside))
print(f"ceiling-blocked instances: {len(blocked)}/580", flush=True)

ext_counter = Counter()
verdicts = Counter()
inst_verdict = Counter()   # per-instance: all outside-gold recoverable?
by_reason_files = defaultdict(list)
records = []
size_dist_done = set()
node_modules_report = {}

for row, gold, outside in blocked:
    rp = CLONES / row["slug"]
    subprocess.run(["git", "checkout", "-f", "-q", row["base_commit"]], cwd=rp,
                   check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=rp, capture_output=True)
    file_verdicts = {}
    for f in outside:
        ext_counter[suffix_of(f) or "<none>"] += 1
        v = classify(rp / f, f)
        verdicts[v] += 1
        file_verdicts[f] = v
        if v != "recoverable":
            by_reason_files[v].append((row["instance_id"], f))
    all_ok = all(v == "recoverable" for v in file_verdicts.values())
    inst_verdict["fully_recoverable" if all_ok else "still_blocked_partially"] += 1
    records.append({"instance_id": row["instance_id"], "slug": row["slug"],
                    "base_commit": row["base_commit"], "n_gold": len(gold),
                    "outside": file_verdicts})

    if row["slug"] not in size_dist_done:
        size_dist_done.add(row["slug"])
        ls = subprocess.run(["git", "ls-files", "-z"], cwd=rp, capture_output=True)
        rels = [r.decode() for r in ls.stdout.split(b"\x00") if r]
        node_modules_report[row["slug"]] = sum(1 for r in rels if "node_modules/" in r)
        cur, new = [], []
        for rel in rels:
            if VENDOR_RE.search(rel):
                continue
            p = rp / rel
            if not p.is_file():
                continue
            (cur if suffix_of(rel) in CODE_EXTS else new).append(p.stat().st_size)
        def dist(v):
            if not v:
                return {}
            v = sorted(v)
            pct = lambda q: v[min(len(v) - 1, int(q * len(v)))]
            return {"n": len(v), "p50": pct(.5), "p90": pct(.9), "p99": pct(.99),
                    "max": v[-1], "n_over_2mb": sum(1 for x in v if x > MAX_FILE_BYTES)}
        print(f"[size-dist] {row['slug']}: indexed={dist(cur)} newly_admitted={dist(new)}",
              flush=True)

print("\nout-of-allowlist gold files by ext:", dict(ext_counter.most_common()))
print("per-file verdicts:", dict(verdicts))
print("per-instance:", dict(inst_verdict))
print("node_modules under git control (file counts):", node_modules_report)
for reason, files in by_reason_files.items():
    print(f"\nBLOCKED [{reason}] ({len(files)}):")
    for iid, f in files[:40]:
        print(f"  {iid}: {f}")

out = Path(sys.argv[2])
out.write_text("\n".join(json.dumps(r) for r in records) + "\n")
print(f"\nwrote {len(records)} records to {out}")
