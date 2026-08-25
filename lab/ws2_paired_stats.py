"""WS2 paired per-instance stats between two MSWE arms (campaign #56 ws2).

Generalization of lab/e23_paired_stats.py to argument-driven arm pairs so
the five-language gates (and the C/C++ main->idx->exp decomposition) reuse
one script. Semantics are IDENTICAL to the E23 version:

  FILE / LINE(all-or-nothing): paired binary outcomes -> gains/losses +
  two-sided exact sign (binomial) test on the discordant pairs.
  fraction: paired mean difference + sign counts.
  FUNCTION: from the scored metric JSONs' per-instance detail (requires
  --lang-functions scoring; instances missing from either detail list --
  engine errors / git_show failures -- are excluded from the pairing and
  counted, matching the unified errors-count-as-wrong convention at the
  aggregate level while pairing only the mutually-judged).

Usage:
  python lab/ws2_paired_stats.py A.jsonl B.jsonl [metric_A.json metric_B.json]
"""
import json
import sys
from math import comb


def load(p):
    recs = {}
    with open(p) as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                recs[r["instance_id"]] = r
    return recs


def sign_test(g, l):
    n = g + l
    if n == 0:
        return 1.0
    k = max(g, l)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n)


def main() -> None:
    a_path, b_path = sys.argv[1], sys.argv[2]
    a, b = load(a_path), load(b_path)
    ids = sorted(set(a) & set(b))
    print(f"paired instances: {len(ids)}  (A={a_path}  B={b_path})")

    for name, fn in [
        ("FILE  (all gold files)", lambda r: 1 if r.get("all_gold_files_retrieved") else 0),
        ("LINE  (all-or-nothing)", lambda r: 1 if r.get("hunk_line_recall") == 1.0 else 0),
    ]:
        g = sum(1 for i in ids if fn(b[i]) > fn(a[i]))
        l = sum(1 for i in ids if fn(b[i]) < fn(a[i]))
        na = sum(fn(a[i]) for i in ids)
        nb = sum(fn(b[i]) for i in ids)
        print(f"{name}: A {na}/{len(ids)} ({100*na/len(ids):.2f}) -> B {nb}/{len(ids)} "
              f"({100*nb/len(ids):.2f})  +{g}/-{l}  sign p={sign_test(g, l):.4g}")

    fa = [a[i].get("hunk_line_recall") or 0.0 for i in ids]
    fb = [b[i].get("hunk_line_recall") or 0.0 for i in ids]
    d = [y - x for x, y in zip(fa, fb)]
    g = sum(1 for x in d if x > 0)
    l = sum(1 for x in d if x < 0)
    print(f"fraction: A {sum(fa)/len(fa):.4f} -> B {sum(fb)/len(fb):.4f}  "
          f"mean diff {sum(d)/len(d):+.4f}  +{g}/-{l}  sign p={sign_test(g, l):.4g}")

    if len(sys.argv) > 4:
        ma = json.load(open(sys.argv[3]))
        mb = json.load(open(sys.argv[4]))
        da = {x["instance_id"]: x["correct"] for x in ma["all_instances"]["function"]["detail"]}
        db = {x["instance_id"]: x["correct"] for x in mb["all_instances"]["function"]["detail"]}
        fids = sorted(set(da) & set(db))
        g = sum(1 for i in fids if db[i] and not da[i])
        l = sum(1 for i in fids if da[i] and not db[i])
        na = sum(1 for i in fids if da[i])
        nb = sum(1 for i in fids if db[i])
        print(f"FUNCTION (exact, mutually-judged n={len(fids)}): "
              f"A {na} -> B {nb}  +{g}/-{l}  sign p={sign_test(g, l):.4g}")


if __name__ == "__main__":
    main()
