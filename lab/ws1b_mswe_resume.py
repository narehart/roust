"""Resume the WS1b MSWE additive arm: run ONLY the missing instances
(scratchpad ws1b_mswe_missing.json) with provenance keys identical to
parity/region_eval_full.py's loop, writing to a separate JSONL for
concatenation. Mirrors region_eval_full: rev.SWEBENCH_REPOS repoint,
EXTRA_ENGINE_FLAGS = --index-all-additive, pad/len defaults always
forwarded (5 / 0.85), timeout = region_eval_full's default.
"""
import json
import sys
import time
from pathlib import Path

MAIN = Path("/Users/nicholasarehart/programming-projects/bgrep")
sys.path.insert(0, str(MAIN / "parity"))
import region_eval_verified as rev  # noqa: E402

MISSING = json.load(open(sys.argv[1]))
OUT = Path(sys.argv[2])
REPOS = Path(sys.argv[3])

rev.SWEBENCH_REPOS = REPOS
rev.EXTRA_ENGINE_FLAGS = ["--index-all-additive"]

rows = rev.load_verified_rows(MAIN / "lab/mswe_jsts.parquet", limit=0)
want = set(MISSING)
rows = [r for r in rows if r["instance_id"] in want]
assert len(rows) == len(MISSING), f"resolved {len(rows)} of {len(MISSING)} missing rows"
print(f"resuming {len(rows)} instances -> {OUT}", flush=True)

n_ok = n_err = 0
t0 = time.time()
with OUT.open("w") as fh:
    for i, row in enumerate(rows, 1):
        rec = rev.eval_verified_instance(row, 180.0, rev.DEFAULT_PAD_LINES, rev.DEFAULT_LEN_EXP)
        rec["shard"] = "1/1"
        rec["bm25_only"] = False
        rec["ts_blocks"] = False
        rec["index_all"] = False
        rec["index_all_additive"] = True
        rec["newcomer_reserve"] = 0.0
        fh.write(json.dumps(rec, default=str) + "\n")
        fh.flush()
        if rec["error"] is None:
            n_ok += 1
        else:
            n_err += 1
        if i % 10 == 0 or i == len(rows):
            print(f"[{i}/{len(rows)}] {row['instance_id']:45} "
                  f"elapsed={time.time()-t0:.0f}s ok={n_ok} err={n_err}", flush=True)
print(f"done: {n_ok} ok, {n_err} err", flush=True)
