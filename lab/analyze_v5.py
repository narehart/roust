"""Compare hist_v3 (base), anchor_v4 (old promotion), anchor_v5 (tiered promotion)
on File@1/@5/@10/@all, plus gained/lost lists at @10 and @all for v5 vs v3,
and a top-5 structural-invariance check of v5 vs v3."""
import json
from pathlib import Path

BASE = Path("/private/tmp/claude-501/-Users-nicholasarehart-programming-projects-bgrep/3ab12e71-fab2-4a81-bb2b-84700d211ef2/scratchpad/bgrep_lab/results_swebench")
LANES = {
    "hist_v3": BASE / "abl_hist_v3.jsonl",
    "anchor_v4": BASE / "abl_anchor_v4.jsonl",
    "anchor_v5": BASE / "abl_anchor_v5.jsonl",
}


def load(path):
    recs = {}
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            recs[d["instance_id"]] = d
    return recs


def at_k(rec, k):
    gold = set(rec["gold_files"])
    returned = rec["returned_files"][:k] if k is not None else rec["returned_files"]
    return gold.issubset(set(returned))


def main():
    data = {name: load(p) for name, p in LANES.items()}
    ids = sorted(set.intersection(*(set(d) for d in data.values())))
    print(f"instances compared: {len(ids)}\n")

    print(f"{'lane':<12} {'@1':>8} {'@5':>8} {'@10':>8} {'@all':>8}")
    results = {}
    for name, recs in data.items():
        row = {}
        for k, label in [(1, "@1"), (5, "@5"), (10, "@10"), (None, "@all")]:
            n = sum(1 for i in ids if at_k(recs[i], k))
            row[label] = n
        results[name] = row
        print(f"{name:<12} " + " ".join(f"{row[l]:>4}/{len(ids)}" for l in ("@1", "@5", "@10", "@all")))

    print()
    # gained / lost @10 and @all, v5 vs v3
    for k, label in [(10, "@10"), (None, "@all")]:
        v3 = {i: at_k(data["hist_v3"][i], k) for i in ids}
        v5 = {i: at_k(data["anchor_v5"][i], k) for i in ids}
        gained = [i for i in ids if v5[i] and not v3[i]]
        lost = [i for i in ids if v3[i] and not v5[i]]
        print(f"v5 vs v3 {label}: gained={len(gained)} lost={len(lost)} net={len(gained) - len(lost)}")
        print(f"  gained: {gained}")
        print(f"  lost:   {lost}")
    print()

    # gained / lost @10 and @all, v4 vs v3 (for reference, same as before)
    for k, label in [(10, "@10"), (None, "@all")]:
        v3 = {i: at_k(data["hist_v3"][i], k) for i in ids}
        v4 = {i: at_k(data["anchor_v4"][i], k) for i in ids}
        gained = [i for i in ids if v4[i] and not v3[i]]
        lost = [i for i in ids if v3[i] and not v4[i]]
        print(f"v4 vs v3 {label}: gained={len(gained)} lost={len(lost)} net={len(gained) - len(lost)}")
    print()

    # top-5 structural invariance: v5 returned_files[:5] must equal v3 returned_files[:5]
    # (this checks the promotion logic didn't touch positions 0-4; spec calls for
    # top-7 invariance but the driver's returned_files[:5] is the readily-available
    # slice, so we check both 5 and 7 explicitly.)
    for n in (5, 7):
        mismatches = []
        for i in ids:
            a = data["hist_v3"][i]["returned_files"][:n]
            b = data["anchor_v5"][i]["returned_files"][:n]
            if a != b:
                mismatches.append(i)
        print(f"top-{n} invariance v5 vs v3: {len(ids) - len(mismatches)}/{len(ids)} identical, {len(mismatches)} mismatches")
        if mismatches:
            print(f"  mismatched instances: {mismatches[:20]}{' ...' if len(mismatches) > 20 else ''}")


if __name__ == "__main__":
    main()
