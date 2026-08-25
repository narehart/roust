"""WS3d step-0 broader-class mining from WS3b/WS3c artifacts (issue #56).

Anchor channel: parse ws3c itemize_{jsts,java,rust}.txt (every
metric-changed instance, with base/v2 anchor_promotions from --explain
reruns). A FIRE = an anchor present under v2 and not under base (same
file). Trace channel: ws3b goldrank_*.jsonl (frames fired, gold flags,
gold rank base->v2) joined with the base-arm packed files.

Emits a fire-level CSV + a per-instance summary + the discriminator
table: for each candidate rule, seeds caught / helpful fires suppressed /
neutral+loss coverage.
"""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from pathlib import Path

RES = Path("lab/results_regions")

SEEDS = {
    "sveltejs__svelte-11104", "clap-rs__clap-2161",  # trace
    "mui__material-ui-34337", "fasterxml__jackson-databind-4219",
    "clap-rs__clap-4059", "clap-rs__clap-5227",  # anchor
}
# nominally protected wins (itemized adoption evidence)
WINS_ANCHOR = {
    "mui__material-ui-32713", "fasterxml__jackson-databind-3509",
    "mockito__mockito-3129", "clap-rs__clap-5015",
    "fasterxml__jackson-databind-4013", "iamkun__dayjs-1953",
}
WINS_TRACE = {
    "fasterxml__jackson-databind-4325", "mui__material-ui-32182",
    "clap-rs__clap-3212", "clap-rs__clap-4474",
    "apache__dubbo-7041", "fasterxml__jackson-databind-4360",
}

# extended testlike: current TESTLIKE_RE analog + fixture-dir shapes
CUR_TESTLIKE = re.compile(
    r"(^|/)tests?(/|$)|(^|/)testing(/|$)|(^|/)test_[^/]*$|_test\.[^/.]+$|"
    r"\.(test|spec)\.[^/]+$|(^|/)__tests__(/|$)|(^|/)spec(/|$)|(^|/)conftest\.py$",
    re.I,
)
FIXTURE_DIR = re.compile(r"(^|/)[^/]+\.(test|spec)s?(/|$)|(^|/)(fixtures?|testdata|test_data|__fixtures__|__mocks__)(/|$)", re.I)


def testshape(path: str) -> str:
    if CUR_TESTLIKE.search(path):
        return "testlike"
    if FIXTURE_DIR.search(path):
        return "fixture-dir"
    return "-"


def parse_itemize(path: Path, slice_name: str):
    insts = []
    cur = None
    for ln in path.read_text().splitlines():
        if ln.startswith("== "):
            cur = {"slice": slice_name, "iid": ln[3:].strip()}
            insts.append(cur)
        elif cur is None:
            continue
        elif m := re.match(r"\s+FILE (\S+)->(\S+)\s+LINE (\S+)->(\S+)\s+frac ([\d.]+)->([\d.]+)\s+FUNC (\S+)->(\S+)", ln):
            cur["file"] = (m.group(1), m.group(2))
            cur["line"] = (m.group(3), m.group(4))
            cur["frac"] = (float(m.group(5)), float(m.group(6)))
            cur["func"] = (m.group(7), m.group(8))
        elif m := re.match(r"\s+gold=(\[.*\])\s+gold_rank (\S+)->(\S+)", ln):
            cur["gold"] = ast.literal_eval(m.group(1))
            cur["grank"] = (None if m.group(2) == "None" else int(m.group(2)),
                            None if m.group(3) == "None" else int(m.group(3)))
        elif m := re.match(r"\s+anchors base=(\[.*\])", ln):
            cur["anch_base"] = ast.literal_eval(m.group(1)) if m.group(1).startswith("[[") or m.group(1) == "[]" else []
        elif m := re.match(r"\s+anchors v2  =(\[.*\])", ln):
            cur["anch_v2"] = ast.literal_eval(m.group(1)) if m.group(1).startswith("[[") or m.group(1) == "[]" else []
    return insts


def direction(inst) -> str:
    f0, f1 = inst["frac"]
    d = 0.0
    d += f1 - f0
    fl = {"1.0": 1, "True": 1, "0.0": 0, "False": 0}
    for key in ("file", "line"):
        a, b = inst[key]
        try:
            d += float(b) - float(a)
        except ValueError:
            pass
    fa, fb = inst["func"]
    if fa != fb and "None" not in (fa, fb):
        d += (1 if fb == "True" else -1)
    if d > 1e-9:
        return "gain"
    if d < -1e-9:
        return "loss"
    return "neutral"


def load_jsonl(p):
    out = {}
    with open(p) as fh:
        for ln in fh:
            if ln.strip():
                r = json.loads(ln)
                out[r["instance_id"]] = r
    return out


def main():
    fires = []  # rows: channel, slice, iid, direction, file, feature dict

    # ---------------- anchor channel (ws3c itemize) ----------------
    insts = []
    for sl in ("jsts", "java", "rust"):
        insts += parse_itemize(RES / "ws3c" / f"itemize_{sl}.txt", sl)
    n_par = 0
    for inst in insts:
        if "anch_v2" not in inst or "anch_base" not in inst:
            n_par += 1
            continue
        base_files = {a[0] for a in inst["anch_base"]}
        gold = set(inst.get("gold", []))
        dirn = direction(inst)
        for f, s, act, kind in inst["anch_v2"]:
            if f in base_files:
                continue  # not a NEW v2 fire
            fires.append({
                "channel": "anchor", "slice": inst["slice"], "iid": inst["iid"],
                "dir": dirn, "file": f, "is_gold": f in gold,
                "strength": s, "action": act, "kind": kind,
                "testshape": testshape(f),
                "gold_rank_base": inst["grank"][0], "gold_rank_v2": inst["grank"][1],
            })
    print(f"anchor: parsed {len(insts)} itemized instances ({n_par} without anchor reruns)")

    # ---------------- trace channel (ws3b goldrank + base packs) ----------------
    base_packs = {}
    for sl in ("java", "rust"):
        base_packs.update({k: set(v.get("regions") or {})
                           for k, v in load_jsonl(RES / "ws3b" / f"mswe_{sl}_ws3b_base.jsonl").items()})
    for sl in ("go", "jsts"):
        base_packs.update({k: set(v.get("regions") or {})
                           for k, v in load_jsonl(RES / "ws3b" / f"mswe_{sl}_micro_ws3b_base.jsonl").items()})
    # metric direction for trace channel: recompute from arm jsonls
    def arm_pair(sl, micro):
        pre = f"mswe_{sl}_micro_ws3b" if micro else f"mswe_{sl}_ws3b"
        return (load_jsonl(RES / "ws3b" / f"{pre}_base.jsonl"),
                load_jsonl(RES / "ws3b" / f"{pre}_v2.jsonl"))

    arm = {}
    for sl, micro in (("java", False), ("rust", False), ("go", True), ("jsts", True)):
        arm[sl] = arm_pair(sl, micro)

    for sl in ("java", "rust", "go", "jsts"):
        gr = load_jsonl(RES / "ws3b" / f"goldrank_{sl}.jsonl")
        a, b = arm[sl]
        for iid, r in gr.items():
            if not r["frames_fired"]:
                continue
            ra, rb = a.get(iid, {}), b.get(iid, {})
            d = ((rb.get("hunk_line_recall") or 0) - (ra.get("hunk_line_recall") or 0)) \
                + (int(bool(rb.get("hunk_file_covered"))) - int(bool(ra.get("hunk_file_covered")))) \
                + (int(bool(rb.get("hunk_touched"))) - int(bool(ra.get("hunk_touched"))))
            dirn = "gain" if d > 1e-9 else ("loss" if d < -1e-9 else "neutral")
            gold = set(r["gold"])
            any_gold_frame = bool(r["frames_that_are_gold"])
            for rank, f in enumerate(r["frames_fired"], 1):
                fires.append({
                    "channel": "trace", "slice": sl, "iid": iid, "dir": dirn,
                    "file": f, "is_gold": f in gold, "strength": 1.0 / rank,
                    "action": "boost", "kind": f"frame{rank}",
                    "testshape": testshape(f),
                    "gold_rank_base": r["gold_rank_base"], "gold_rank_v2": r["gold_rank_v2"],
                    "frame_in_base_pack": f in base_packs.get(iid, set()),
                    "any_gold_frame": any_gold_frame,
                })

    # ---------------- per-instance rollup ----------------
    by_inst = defaultdict(list)
    for f in fires:
        by_inst[(f["channel"], f["iid"])].append(f)

    print(f"\nfire-level rows: {len(fires)}  instances with fires: {len(by_inst)}")
    print("\n== per-instance rollup (channel, iid, dir, non-gold fires / fires, notes)")
    rule_hits = defaultdict(set)  # rule -> set of (channel, iid)

    for (ch, iid), rows in sorted(by_inst.items()):
        dirn = rows[0]["dir"]
        ng = [r for r in rows if not r["is_gold"]]
        notes = []
        gr0 = rows[0]["gold_rank_base"]
        # candidate rules evaluated at INSTANCE level (a guard damps a fire-set)
        if ch == "anchor":
            weak_ng = [r for r in ng if r["strength"] < 2.0]
            test_ng = [r for r in ng if r["testshape"] != "-"]
            if test_ng:
                rule_hits["A:test/fixture-shaped non-gold anchor"].add((ch, iid))
            if weak_ng:
                rule_hits["B:strength<2.0 non-gold anchor"].add((ch, iid))
            if [r for r in ng if r["strength"] < 2.0 and r["action"] == "insert"]:
                rule_hits["B2:strength<2.0 non-gold INSERT"].add((ch, iid))
            if [r for r in ng if r["action"] == "insert"]:
                rule_hits["D:any non-gold insert while gold ranked<=10"].add((ch, iid)) if (gr0 or 99) <= 10 else None
        else:
            if not rows[0]["any_gold_frame"]:
                rule_hits["C0:no frame is gold (oracle)"].add((ch, iid))
            if not any(r["frame_in_base_pack"] for r in rows):
                rule_hits["C:no fired frame in base pack (no lexical mass proxy)"].add((ch, iid))
            if [r for r in ng if r["testshape"] != "-"]:
                rule_hits["A:test/fixture-shaped non-gold anchor"].add((ch, iid))
        flags = []
        if iid in SEEDS:
            flags.append("SEED")
        if iid in WINS_ANCHOR | WINS_TRACE:
            flags.append("WIN")
        for r in ng:
            if r["testshape"] != "-":
                notes.append(f"{r['file']}[{r['testshape']}]")
        print(f"  {ch:6} {iid:45} {dirn:7} ng={len(ng)}/{len(rows)} grank={gr0}->{rows[0]['gold_rank_v2']} "
              f"{' '.join(flags)} {'; '.join(notes[:3])}")

    # ---------------- discriminator table ----------------
    print("\n== discriminator table (instance-level)")
    seeds_all = {("anchor", i) for i in SEEDS if "svelte" not in i and "2161" not in i} | \
                {("trace", i) for i in ("sveltejs__svelte-11104", "clap-rs__clap-2161")}
    wins_all = {("anchor", i) for i in WINS_ANCHOR} | {("trace", i) for i in WINS_TRACE}
    for rule, hit in sorted(rule_hits.items()):
        s = seeds_all & hit
        w = wins_all & hit
        losses = {k for k in hit if by_inst[k][0]["dir"] == "loss"}
        gains = {k for k in hit if by_inst[k][0]["dir"] == "gain"}
        neut = {k for k in hit if by_inst[k][0]["dir"] == "neutral"}
        print(f"  {rule}")
        print(f"    hits={len(hit)}  seeds {len(s)}/{len(seeds_all & set(by_inst))}  "
              f"WINS-suppressed {len(w)}: {sorted(i for _, i in w)}")
        print(f"    hit direction split: gain={len(gains)} {sorted(i for _,i in gains)[:6]} "
              f"loss={len(losses)} {sorted(i for _,i in losses)[:8]} neutral={len(neut)}")

    with open(RES / "ws3d" / "mine_fires.json", "w") as fh:
        json.dump(fires, fh, indent=1)
    print(f"\nwrote {RES/'ws3d'/'mine_fires.json'}")


if __name__ == "__main__":
    main()
