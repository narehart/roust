"""E25 drift audit: committed per-language baselines vs freshly-run abb96af
defaults, so the engine drift since each baseline was scored is quantified
SEPARATELY from anything --shape-blocks does.

Why this exists: the committed baselines were scored on different engine
commits (jsts at the WS3d pin, java/rust at WS3c, c/cpp at WS3b/0c0fc79,
go back at WS2 -- before WS3b even taught the tracer Go frame formats).
Pairing an abb96af shape arm against those artifacts would have charged
shape for three since-adopted changes. Every shape comparison in this round
is therefore against a same-commit default arm; this table is the audit of
what the intervening engine moves were worth on their own.
"""

from __future__ import annotations

import json
from pathlib import Path

R = Path("/Users/nicholasarehart/programming-projects/bgrep/lab/results_regions")

# slice -> (committed baseline artifact, stated headline in the brief)
BASELINES = {
    "jsts": ("ws3d/agentless_metric_ws3d_jsts_guard.json", (46.38, 31.21, 14.14, 0.26156)),
    "java": ("ws3c/agentless_metric_ws3c_java_v2.json",    (49.22, 35.16, 14.84, 0.39691)),
    "go":   ("ws2/agentless_metric_mswe_go_exp.json",      (63.79, 29.21, 16.59, 0.41140)),
    "rust": ("ws3c/agentless_metric_ws3c_rust_v2.json",    (60.25, 19.67,  7.53, 0.24315)),
    "c":    ("ws3b/agentless_metric_ws3b_c_base.json",     (46.88, 26.56, 10.94, 0.19768)),
    "cpp":  ("ws3b/agentless_metric_ws3b_cpp_base.json",   (65.12, 17.83,  6.98, 0.29476)),
}


def headline(path: Path):
    a = json.loads(path.read_text())
    src = json.loads(path.read_text()).get("source", {})
    return (a["all_instances"]["file"]["pct_correct"],
            a["all_instances"]["function"]["pct_correct"],
            a["all_instances"]["line"]["pct_correct_all_or_nothing"],
            a["all_instances"]["line"]["mean_fraction_covered"],
            a["all_instances"]["n"],
            ",".join(src.get("engine_shas_seen", []) or ["?"]))


def main():
    rows = []
    print(f"{'slice':6} {'arm':22} {'n':>5} {'sha':>10} "
          f"{'FILE':>7} {'FUNC':>7} {'LINE':>7} {'frac':>9}")
    for slice_, (rel, stated) in BASELINES.items():
        bpath, npath = R / rel, R / "e25" / f"metric_{slice_}_def.json"
        b = headline(bpath)
        print(f"{slice_:6} {'committed baseline':22} {b[4]:5d} {b[5]:>10} "
              f"{b[0]:7.2f} {b[1]:7.2f} {b[2]:7.2f} {b[3]:9.5f}")
        # Does the committed artifact still reproduce the number in the brief?
        repro = (round(b[0], 2) == stated[0] and round(b[1], 2) == stated[1]
                 and round(b[2], 2) == stated[2] and round(b[3], 5) == round(stated[3], 5))
        if not repro:
            print(f"{'':6} {'  !! brief says':22} {'':5} {'':>10} "
                  f"{stated[0]:7.2f} {stated[1]:7.2f} {stated[2]:7.2f} {stated[3]:9.5f}")
        if not npath.exists():
            print(f"{'':6} {'  (no abb96af default arm yet)':22}")
            continue
        n = headline(npath)
        print(f"{'':6} {'abb96af default':22} {n[4]:5d} {n[5]:>10} "
              f"{n[0]:7.2f} {n[1]:7.2f} {n[2]:7.2f} {n[3]:9.5f}")
        print(f"{'':6} {'DRIFT':22} {'':5} {'':>10} "
              f"{n[0]-b[0]:+7.2f} {n[1]-b[1]:+7.2f} {n[2]-b[2]:+7.2f} {n[3]-b[3]:+9.5f}")
        rows.append({"slice": slice_, "baseline_artifact": rel,
                     "baseline_reproduces_brief": repro,
                     "baseline": {"n": b[4], "sha": b[5], "file": b[0], "function": b[1],
                                  "line": b[2], "mean_fraction": b[3]},
                     "abb96af_default": {"n": n[4], "sha": n[5], "file": n[0], "function": n[1],
                                         "line": n[2], "mean_fraction": n[3]},
                     "drift": {"file": round(n[0]-b[0], 2), "function": round(n[1]-b[1], 2),
                               "line": round(n[2]-b[2], 2),
                               "mean_fraction": round(n[3]-b[3], 6)}})
    out = R / "e25" / "drift_audit.json"
    out.write_text(json.dumps(rows, indent=1))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
