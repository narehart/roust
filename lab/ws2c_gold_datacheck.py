"""WS2c Gate 1 data check (campaign #56): do the new VENDOR_RE alternates
touch ANY gold file, on any bench?

New alternates (roust-rs/src/core.rs VENDOR_RE, commit 39b0b14):
  (^|/)(cextern|extern)(/|$)   and   (^|/)(libsvm|liblinear)(/|$)

Checks, per slice (MSWE c/cpp/go/rust/java/jsts + SWE-bench Lite-300 +
Verified-407):
  1. gold paths matching the NEW alternates          -> must be 0 everywhere
  2. gold paths matching the FULL OLD (main) VENDOR_RE -> itemized findings
     (gold that current defaults already exclude, e.g. Go vendor/)
  3. gold paths containing the substring 'extern' anywhere (the spec's
     "extern/-style" grep) -> itemized, to show near-misses the component
     anchoring spares

Gold extraction: swebench_driver2._DIFF_FILE_RE convention,
r"^diff --git a/(\\S+) b/" re.M over the patch column.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

LAB = Path(__file__).resolve().parent

DIFF_FILE_RE = re.compile(r"^diff --git a/(\S+) b/", re.M)
NEW_RE = re.compile(r"(?i)((^|/)(cextern|extern)(/|$)|(^|/)(libsvm|liblinear)(/|$))")
OLD_RE = re.compile(r"(?i)(vendor|vendored|third_party|node_modules|\.min\.(js|css)$|bundle\.js$)")


def slice_df(name: str) -> pd.DataFrame:
    if name in ("lite", "verified"):
        f = {"lite": "swebench_lite.parquet", "verified": "swebench_verified_heldout.parquet"}[name]
        return pd.read_parquet(LAB / f)
    if name == "jsts":
        return pd.read_parquet(LAB / "mswe_jsts.parquet")
    combined = pd.read_parquet(LAB / "mswe_ws2c.parquet")
    ids = set((LAB / f"mswe_{name}_instances.txt").read_text().split())
    df = combined[combined["instance_id"].isin(ids)].reset_index(drop=True)
    missing = ids - set(df["instance_id"])
    if missing:
        print(f"  !! {name}: {len(missing)} committed instance ids MISSING from rebuilt parquet: {sorted(missing)[:5]}")
    return df


def main() -> None:
    slices = ["c", "cpp", "go", "rust", "java", "jsts", "lite", "verified"]
    report = {}
    fail = False
    for name in slices:
        df = slice_df(name)
        new_hits, old_hits, extern_sub = [], [], []
        for _, row in df.iterrows():
            for p in sorted(set(DIFF_FILE_RE.findall(row["patch"]))):
                if NEW_RE.search(p):
                    new_hits.append((row["instance_id"], p))
                if OLD_RE.search(p):
                    old_hits.append((row["instance_id"], p))
                if "extern" in p.lower():
                    extern_sub.append((row["instance_id"], p))
        report[name] = {"n": len(df), "new_hits": new_hits, "old_hits": old_hits,
                        "extern_substring": extern_sub}
        print(f"[{name}] n={len(df)}  gold-paths-matching-NEW={len(new_hits)}  "
              f"matching-OLD-vendor-re={len(old_hits)}  extern-substring={len(extern_sub)}")
        for iid, p in new_hits:
            print(f"    NEW-HIT  {iid}: {p}")
            fail = True
        for iid, p in old_hits:
            print(f"    old-vendor-gold  {iid}: {p}")
        for iid, p in extern_sub:
            if not NEW_RE.search(p):
                print(f"    extern-substring-spared  {iid}: {p}")
    out = LAB / "results_regions/ws2c/gold_datacheck.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))
    print(f"\nwrote {out}")
    print("VERDICT:", "FAIL - new patterns exclude gold, STOP" if fail else
          "PASS - zero gold paths match the new alternates on any slice")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
