"""Compare anchor_v5 (base) vs bridge_v6 (v6 head+tail testbridge) vs
bridges_v7 (v7: testbridge tail-only + specificity score, plus new
tail-only docsbridge channel) on File@1/@5/@10/@all, plus gained/lost lists
at @10 and @all for v7 vs v5 and v7 vs v6, and a top-10 structural-invariance
check of v7 vs v5 (both v7 channels are tail-only at position >=14, so the
top-10 lists must be IDENTICAL to v5 -- if not 0, diagnose)."""
import json
from pathlib import Path

BASE = Path("/private/tmp/claude-501/-Users-nicholasarehart-programming-projects-bgrep/3ab12e71-fab2-4a81-bb2b-84700d211ef2/scratchpad/bgrep_lab/results_swebench")
LANES = {
    "anchor_v5": BASE / "abl_anchor_v5.jsonl",
    "bridge_v6": BASE / "abl_bridge_v6.jsonl",
    "bridges_v7": BASE / "abl_bridges_v7.jsonl",
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
    # gained / lost @10 and @all, v7 vs v5 AND v7 vs v6
    for base_name in ("anchor_v5", "bridge_v6"):
        gained_lost = {}
        for k, label in [(10, "@10"), (None, "@all")]:
            base = {i: at_k(data[base_name][i], k) for i in ids}
            v7 = {i: at_k(data["bridges_v7"][i], k) for i in ids}
            gained = [i for i in ids if v7[i] and not base[i]]
            lost = [i for i in ids if base[i] and not v7[i]]
            gained_lost[label] = (gained, lost)
            print(f"v7 vs {base_name} {label}: gained={len(gained)} lost={len(lost)} net={len(gained) - len(lost)}")
            print(f"  gained: {gained}")
            print(f"  lost:   {lost}")
        print()

    # top-10 structural invariance: v7 returned_files[:10] must equal v5
    # returned_files[:10] exactly (both v7 channels -- testbridge tail and
    # docsbridge -- only ever insert at position >=14, so nothing at
    # positions 0-9 should ever move relative to v5).
    for n in (7, 10):
        mismatches = []
        for i in ids:
            a = data["anchor_v5"][i]["returned_files"][:n]
            b = data["bridges_v7"][i]["returned_files"][:n]
            if a != b:
                mismatches.append(i)
        print(f"top-{n} invariance v7 vs v5: {len(ids) - len(mismatches)}/{len(ids)} identical, {len(mismatches)} mismatches")
        if mismatches:
            print(f"  mismatched instances: {mismatches[:20]}{' ...' if len(mismatches) > 20 else ''}")
            for i in mismatches[:5]:
                print(f"    {i}:")
                print(f"      v5: {data['anchor_v5'][i]['returned_files'][:n]}")
                print(f"      v7: {data['bridges_v7'][i]['returned_files'][:n]}")

    print()
    # mean tokens per lane
    print(f"{'lane':<12} {'mean_tokens':>12}")
    for name, recs in data.items():
        toks = [recs[i]["tokens_packed"] for i in ids]
        print(f"{name:<12} {sum(toks) / len(toks):>12.1f}")

    print()
    # if losses exceed gains at @10 or @all (vs v5), dump the losing
    # instances' testbridge/docsbridge entries for diagnosis
    for base_name in ("anchor_v5", "bridge_v6"):
        for k, label in [(10, "@10"), (None, "@all")]:
            base = {i: at_k(data[base_name][i], k) for i in ids}
            v7 = {i: at_k(data["bridges_v7"][i], k) for i in ids}
            gained = [i for i in ids if v7[i] and not base[i]]
            lost = [i for i in ids if base[i] and not v7[i]]
            if len(lost) > len(gained):
                print(f"-- v7 vs {base_name} {label}: losses ({len(lost)}) exceed gains ({len(gained)}); "
                      f"testbridge/docsbridge entries for losers --")
                for i in lost:
                    tb = data["bridges_v7"][i].get("testbridge", [])
                    db = data["bridges_v7"][i].get("docsbridge", [])
                    print(f"  {i}: testbridge={tb} docsbridge={db}")


if __name__ == "__main__":
    main()
