"""E27 seat-fire anatomy: did the extra seats fire, and did they seat gold?

Two independent views of the same mechanism, because either alone can lie:

  FIRE SIDE (from the engine's own trace, ROUST_E27_SEAT_TRACE). Every extra
  seat the engine admitted, with the source that seated it and the historical
  co-change count that bought the seat. Answers "how often were extra seats
  taken" -- a question the output diff cannot answer, because a seated file
  that the default arm also selected leaves no trace in the output.

  CONSEQUENCE SIDE (from the two arms' prediction JSONLs). Which files the
  arm's bundle contains that the default's does not, and whether they are
  gold. A seat that fires but changes nothing downstream is not a win, and
  this campaign's own meta-finding is that displacement is consequence-side.

Gold files are parsed from the gold patch with the harness's own
parse_gold_hunks, so "was the seated file gold" uses exactly the file set the
FILE metric scores against.

Usage:
  uv run --no-project --with pandas --with pyarrow python lab/e27_seats.py \
      --label jsts_s3 --trace TRACE.jsonl --def-jsonl A.jsonl \
      --arm-jsonl B.jsonl --gold-parquet P.parquet --out OUT.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "parity"))
from region_eval import parse_gold_hunks  # noqa: E402


def load_records(jsonl: Path) -> dict[str, dict]:
    out = {}
    for line in Path(jsonl).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["instance_id"]] = r
    return out


def load_gold(parquet: Path) -> dict[str, set[str]]:
    import pandas as pd
    df = pd.read_parquet(parquet)
    return {row["instance_id"]: set(parse_gold_hunks(row["patch"]).keys())
            for _, row in df.iterrows()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument("--def-jsonl", type=Path, required=True)
    ap.add_argument("--arm-jsonl", type=Path, required=True)
    ap.add_argument("--gold-parquet", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    gold = load_gold(a.gold_parquet)
    d_recs, s_recs = load_records(a.def_jsonl), load_records(a.arm_jsonl)

    # ---- fire side ------------------------------------------------------
    # One trace line per roust invocation. Keyed by instance tag; a repeated
    # tag would mean the engine was invoked twice for one instance, so keep
    # the LAST and count the collisions rather than silently summing them.
    fired: dict[str, dict] = {}
    dup = 0
    for line in a.trace.read_text().splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        if t["tag"] in fired:
            dup += 1
        fired[t["tag"]] = t

    traced = [t for t in fired.values() if t["tag"] in s_recs]
    n_traced = len(traced)
    n_any = sum(1 for t in traced if t["n_extra"] > 0)
    seats_all = [t["n_extra"] for t in traced]
    seats_fired = [t["n_extra"] for t in traced if t["n_extra"] > 0]

    seat_rows = []
    for t in traced:
        g = gold.get(t["tag"], set())
        for src, cand, n in t["extra"]:
            seat_rows.append({"instance_id": t["tag"], "source": src, "seated": cand,
                              "cochange": n, "seated_is_gold": cand in g,
                              "source_is_gold": src in g})
    n_seats = len(seat_rows)
    n_gold_seats = sum(1 for r in seat_rows if r["seated_is_gold"])
    # A seat is only a RESCUE if the default arm did not already have the file.
    n_gold_rescue = sum(1 for r in seat_rows if r["seated_is_gold"]
                        and r["seated"] not in (d_recs.get(r["instance_id"], {}).get("regions") or {}))
    n_from_gold_src = sum(1 for r in seat_rows if r["source_is_gold"])

    # ---- consequence side -----------------------------------------------
    ids = sorted(set(d_recs) & set(s_recs))
    added_total = added_gold = dropped_total = dropped_gold = 0
    changed_bundles = 0
    per_inst = []
    for i in ids:
        dset = set((d_recs[i].get("regions") or {}).keys())
        sset = set((s_recs[i].get("regions") or {}).keys())
        if dset == sset:
            continue
        changed_bundles += 1
        g = gold.get(i, set())
        add, drop = sset - dset, dset - sset
        added_total += len(add)
        dropped_total += len(drop)
        ag, dg = add & g, drop & g
        added_gold += len(ag)
        dropped_gold += len(dg)
        per_inst.append({"instance_id": i, "n_gold_files": d_recs[i].get("n_gold_files"),
                         "added": sorted(add), "dropped": sorted(drop),
                         "added_gold": sorted(ag), "dropped_gold": sorted(dg)})

    out = {
        "label": a.label,
        "fire_side": {
            "instances_traced": n_traced,
            "duplicate_tags": dup,
            "instances_with_any_extra_seat": n_any,
            "pct_instances_fired": round(100 * n_any / n_traced, 2) if n_traced else 0.0,
            "total_extra_seats": n_seats,
            "mean_seats_per_instance": round(statistics.mean(seats_all), 3) if seats_all else 0.0,
            "mean_seats_where_fired": round(statistics.mean(seats_fired), 3) if seats_fired else 0.0,
            "max_seats_one_instance": max(seats_all) if seats_all else 0,
            "seated_files_that_are_gold": n_gold_seats,
            "seat_gold_precision_pct": round(100 * n_gold_seats / n_seats, 2) if n_seats else 0.0,
            "gold_seats_the_default_lacked": n_gold_rescue,
            "seats_whose_source_was_gold": n_from_gold_src,
            "pct_seats_from_gold_source": round(100 * n_from_gold_src / n_seats, 2) if n_seats else 0.0,
        },
        "consequence_side": {
            "instances_compared": len(ids),
            "bundles_changed": changed_bundles,
            "pct_bundles_changed": round(100 * changed_bundles / len(ids), 2) if ids else 0.0,
            "files_added": added_total, "files_added_gold": added_gold,
            "files_dropped": dropped_total, "files_dropped_gold": dropped_gold,
            "net_gold": added_gold - dropped_gold,
            "added_gold_precision_pct": round(100 * added_gold / added_total, 2) if added_total else 0.0,
        },
        "seats": seat_rows,
        "changed_bundles": per_inst,
    }
    a.out.write_text(json.dumps(out, indent=1))

    f, c = out["fire_side"], out["consequence_side"]
    print(f"=== {a.label} seat-fire anatomy ===")
    print(f"  fired on {f['instances_with_any_extra_seat']}/{f['instances_traced']} instances "
          f"({f['pct_instances_fired']}%), {f['total_extra_seats']} extra seats total, "
          f"mean {f['mean_seats_where_fired']} where fired, max {f['max_seats_one_instance']}")
    print(f"  seated file was gold: {f['seated_files_that_are_gold']}/{f['total_extra_seats']} "
          f"({f['seat_gold_precision_pct']}%); of those {f['gold_seats_the_default_lacked']} "
          f"were gold the DEFAULT arm did not have")
    print(f"  seat's source file was itself gold: {f['seats_whose_source_was_gold']} "
          f"({f['pct_seats_from_gold_source']}%)")
    print(f"  bundles changed: {c['bundles_changed']}/{c['instances_compared']} "
          f"({c['pct_bundles_changed']}%); files +{c['files_added']} (gold {c['files_added_gold']}) "
          f"/ -{c['files_dropped']} (gold {c['files_dropped_gold']}), net gold {c['net_gold']:+d}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
