#!/usr/bin/env python3
"""Paired cache-cold / warm CLI timings and payload identity on fixed inputs.

Use private clones per binary. Corpus indexing is warmed separately; block-cold
means only the private structural side-cache is deleted. Alternate binary order
by repeat, keep all observations, and do not treat a small timing sample as recall.
"""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import tempfile
import time
from e51_run import ROOT, SLICES, sha256
import pandas as pd


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--fixed', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    assert not args.out.exists()
    binaries = {k: getattr(args, k).resolve() for k in ['baseline', 'fixed']}
    provenance = {k: dict(path=str(v), sha256=sha256(v), version=subprocess.check_output([str(v), '--version'], text=True).strip()) for k,v in binaries.items()}
    assert all('clean' in p['version'] and 'dirty' not in p['version'] for p in provenance.values())
    root = Path(tempfile.mkdtemp(prefix='bgrep-e53-perf-', dir='/private/tmp'))
    slices = ["rust", "cpp", "jsts", "c", "java", "go", "lite"]
    input_hashes = {sl: sha256(ROOT / "lab" / SLICES[sl][0]) for sl in slices}
    driver_hash = sha256(Path(__file__))
    rows = []
    for sl in ['rust', 'cpp', 'jsts', 'c', 'java', 'go', 'lite']:
        pq, repos, _ = SLICES[sl]
        for i, row in enumerate(pd.read_parquet(ROOT/'lab'/pq).to_dict('records')[:2]):
            targets = {}
            for arm in binaries:
                dest = root / f'{sl}-{i}-{arm}'
                source = ROOT/'lab'/repos/row['repo'].replace('/', '__')
                subprocess.run(['git','clone','--quiet','--shared','--no-checkout',str(source),str(dest)],check=True)
                subprocess.run(['git','checkout','-q',row['base_commit']],cwd=dest,check=True)
                targets[arm] = dest
            expected = None
            observations = []
            def run(arm):
                start = time.perf_counter()
                result = subprocess.run([str(binaries[arm]), row['problem_statement'], str(targets[arm]), '--json', '--budget','8192','--pad-lines','5','--len-exp','0.85'], capture_output=True, text=True, timeout=180)
                elapsed = time.perf_counter()-start
                assert result.returncode == 0, result.stderr
                obj = json.loads(result.stdout)
                return {k: obj[k] for k in ['regions','bundle']}, elapsed
            for arm in binaries:
                payload, _ = run(arm)  # corpus warmup, excluded
                if expected is None: expected = payload
                assert payload == expected, (sl, i, arm, 'warmup drift')
            for repeat in range(3):
                order = list(binaries) if repeat % 2 == 0 else list(reversed(binaries))
                for state in ['block-cold', 'warm']:
                    for arm in order:
                        if state == 'block-cold':
                            (targets[arm]/'.roust/blocks.json').unlink(missing_ok=True)
                        payload, elapsed = run(arm)
                        assert payload == expected, (sl, i, arm, state, 'payload drift')
                        observations.append(dict(arm=arm, state=state, repeat=repeat, seconds=elapsed))
            rows.append(dict(slice=sl, instance_id=row['instance_id'], base_commit=row['base_commit'], observations=observations, payload_identical=True))
            print(sl, i, 'identical', flush=True)
    summary = {}
    for state in ['block-cold','warm']:
        ratios=[]
        for row in rows:
            med={a:statistics.median(o['seconds'] for o in row['observations'] if o['arm']==a and o['state']==state) for a in binaries}
            ratios.append(med['fixed']/med['baseline'])
        summary[state]=dict(n=len(ratios), median_per_case_fixed_over_baseline=statistics.median(ratios), per_case_ratios=ratios)
    assert all(sha256(binaries[a]) == provenance[a]['sha256'] for a in binaries)
    assert all(sha256(ROOT / 'lab' / SLICES[sl][0]) == h for sl, h in input_hashes.items())
    assert sha256(Path(__file__)) == driver_hash
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(dict(binaries=provenance,inputs_sha256=input_hashes,driver_sha256=driver_hash,summary=summary, cases=rows),indent=2)+'\n')
    print(summary)


if __name__=='__main__': main()
