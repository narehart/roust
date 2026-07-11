"""Compare anchor_v5 (base) vs bridge_v6 (test-file lexical bridge channel added)
on File@1/@5/@10/@all, plus gained/lost lists at @10 and @all for v6 vs v5,
and a top-7 structural-invariance check of v6 vs v5 (positions 0-6 must never
be touched by the testbridge tiering)."""
import json
from pathlib import Path

BASE = Path("/private/tmp/claude-501/-Users-nicholasarehart-programming-projects-bgrep/3ab12e71-fab2-4a81-bb2b-84700d211ef2/scratchpad/bgrep_lab/results_swebench")
LANES = {
    "anchor_v5": BASE / "abl_anchor_v5.jsonl",
    "bridge_v6": BASE / "abl_bridge_v6.jsonl",
}


def load(path):
    recs = {}
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            if "error" in d:
                continue
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
    # gained / lost @10 and @all, v6 vs v5
    gained_lost = {}
    for k, label in [(10, "@10"), (None, "@all")]:
        v5 = {i: at_k(data["anchor_v5"][i], k) for i in ids}
        v6 = {i: at_k(data["bridge_v6"][i], k) for i in ids}
        gained = [i for i in ids if v6[i] and not v5[i]]
        lost = [i for i in ids if v5[i] and not v6[i]]
        gained_lost[label] = (gained, lost)
        print(f"v6 vs v5 {label}: gained={len(gained)} lost={len(lost)} net={len(gained) - len(lost)}")
        print(f"  gained: {gained}")
        print(f"  lost:   {lost}")
    print()

    # top-7 structural invariance: v6 returned_files[:7] must equal v5 returned_files[:7]
    # (positions 0-6 must never be touched by testbridge tiering, per spec).
    for n in (5, 7):
        mismatches = []
        for i in ids:
            a = data["anchor_v5"][i]["returned_files"][:n]
            b = data["bridge_v6"][i]["returned_files"][:n]
            if a != b:
                mismatches.append(i)
        print(f"top-{n} invariance v6 vs v5: {len(ids) - len(mismatches)}/{len(ids)} identical, {len(mismatches)} mismatches")
        if mismatches:
            print(f"  mismatched instances: {mismatches[:20]}{' ...' if len(mismatches) > 20 else ''}")

    print()
    # if losses exceed gains at @10 or @all, dump the losing instances' testbridge entries
    for label in ("@10", "@all"):
        gained, lost = gained_lost[label]
        if len(lost) > len(gained):
            print(f"-- {label}: losses ({len(lost)}) exceed gains ({len(gained)}); testbridge entries for losers --")
            for i in lost:
                tb = data["bridge_v6"][i].get("testbridge", [])
                print(f"  {i}: testbridge={tb}")


if __name__ == "__main__":
    main()
