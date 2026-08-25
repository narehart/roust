"""WS3d fire-level discriminator table (issue #56).

Instance-level rules overcount win suppression: a guard damps individual
FIRES. A win is suppressed only if the rule matches its WIN-CARRYING fire
(the gold-anchoring fire / gold frame). A seed is caught only if the rule
matches >=1 culprit fire (non-gold fire confirmed displacing).

Reads mine_fires.json (from ws3d_mine.py).
"""

import json
from collections import defaultdict

FIRES = json.load(open("lab/results_regions/ws3d/mine_fires.json"))

WINS = {
    ("anchor", "mui__material-ui-32713"), ("anchor", "fasterxml__jackson-databind-3509"),
    ("anchor", "mockito__mockito-3129"), ("anchor", "clap-rs__clap-5015"),
    ("anchor", "fasterxml__jackson-databind-4013"), ("anchor", "iamkun__dayjs-1953"),
    ("trace", "fasterxml__jackson-databind-4325"), ("trace", "mui__material-ui-32182"),
    ("trace", "clap-rs__clap-3212"), ("trace", "clap-rs__clap-4474"),
    ("trace", "apache__dubbo-7041"), ("trace", "fasterxml__jackson-databind-4360"),
}
SEEDS = {
    ("trace", "sveltejs__svelte-11104"), ("trace", "clap-rs__clap-2161"),
    ("anchor", "mui__material-ui-34337"), ("anchor", "fasterxml__jackson-databind-4219"),
    ("anchor", "clap-rs__clap-4059"), ("anchor", "clap-rs__clap-5227"),
}

RULES = {
    "a:test/fixture-shaped fired file": lambda f: f["testshape"] != "-",
    "a1:fixture-dir only": lambda f: f["testshape"] == "fixture-dir",
    "b:weak anchor (strength<2.0)": lambda f: f["channel"] == "anchor" and f["strength"] < 2.0,
    "b2:weak AND insert": lambda f: f["channel"] == "anchor" and f["strength"] < 2.0 and f["action"] == "insert",
    "c:trace fire w/ no frame in base pack": lambda f: f["channel"] == "trace" and not f.get("any_frame_in_pack", True),
    "e:any anchor insert (no ranked presence)": lambda f: f["channel"] == "anchor" and f["action"] == "insert",
    "f:strong insert (>=2.0, head)": lambda f: f["channel"] == "anchor" and f["strength"] >= 2.0 and f["action"] == "insert",
}

# annotate instance-level any_frame_in_pack for trace fires
by_inst = defaultdict(list)
for f in FIRES:
    by_inst[(f["channel"], f["iid"])].append(f)
for key, rows in by_inst.items():
    if rows[0]["channel"] == "trace":
        anyp = any(r.get("frame_in_base_pack") for r in rows)
        for r in rows:
            r["any_frame_in_pack"] = anyp

print(f"{len(FIRES)} fires across {len(by_inst)} instances")
print(f"win instances w/ fire data: {sorted(i for c,i in set(by_inst) & WINS)}")

print("\n== win-carrying fires (gold fires inside win instances)")
for (ch, iid), rows in sorted(by_inst.items()):
    if (ch, iid) not in WINS:
        continue
    for r in rows:
        tag = "GOLD" if r["is_gold"] else "non-gold"
        print(f"  {ch:6} {iid:42} {tag:8} {r['file']}"
              f"  s={r['strength']:.2f} {r['action']}/{r['kind']} shape={r['testshape']}")

print("\n== culprit fires (non-gold fires inside seed instances)")
for (ch, iid), rows in sorted(by_inst.items()):
    if (ch, iid) not in SEEDS:
        continue
    for r in rows:
        if r["is_gold"]:
            continue
        print(f"  {ch:6} {iid:42} {r['file']}"
              f"  s={r['strength']:.2f} {r['action']}/{r['kind']} shape={r['testshape']}")

print("\n== fire-level discriminator table")
print(f"{'rule':44} {'seed_caught':>11} {'win_supp':>8} {'loss_fires':>10} {'gain_fires':>10} {'neut':>5}")
for name, pred in RULES.items():
    seeds_caught = set()
    wins_supp = set()
    n_loss = n_gain = n_neu = 0
    for f in FIRES:
        key = (f["channel"], f["iid"])
        if not pred(f):
            continue
        if key in SEEDS and not f["is_gold"]:
            seeds_caught.add(key[1])
        if key in WINS and f["is_gold"]:
            wins_supp.add(key[1])
        if f["dir"] == "loss":
            n_loss += 1
        elif f["dir"] == "gain":
            n_gain += 1
        else:
            n_neu += 1
    print(f"{name:44} {len(seeds_caught):>11} {len(wins_supp):>8} {n_loss:>10} {n_gain:>10} {n_neu:>5}")
    if seeds_caught:
        print(f"    seeds: {sorted(seeds_caught)}")
    if wins_supp:
        print(f"    WINS SUPPRESSED: {sorted(wins_supp)}")

# gold fires damped by each rule anywhere (potential hidden gain loss)
print("\n== gold fires matched by each rule (any instance) -- collateral risk")
for name, pred in RULES.items():
    gold_hits = [(f["iid"], f["file"]) for f in FIRES if pred(f) and f["is_gold"]]
    print(f"  {name}: {len(gold_hits)}")
    for iid, fl in gold_hits[:8]:
        print(f"      {iid}: {fl}")
