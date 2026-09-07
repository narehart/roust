#!/usr/bin/env python3
"""Post-run autopsy: trace the largest fractional win/loss in each E53 slice.

Selection is explicit and uses completed discovery labels; traces are diagnosis,
not an additional tuning set or evidence of average improvement.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import pandas as pd
from e51_run import ROOT, SLICES, sha256


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary',type=Path,required=True)
    args=ap.parse_args(); binary=args.binary.resolve()
    root=Path(tempfile.mkdtemp(prefix='bgrep-e53-trace-',dir='/private/tmp'))
    report=dict(binary=dict(sha256=sha256(binary),version=subprocess.check_output([str(binary),'--version'],text=True).strip()),cases=[])
    for sl in ['rust','cpp']:
        directory=ROOT/'lab/results_regions/e53/discovery'
        manifest=json.loads((directory/f'{sl}_manifest.json').read_text());assert 'outputs_sha256' in manifest
        rows={a:{r['instance_id']:r for r in map(json.loads,(directory/f'{sl}_{a}.jsonl').read_text().splitlines())} for a in ['baseline','emitted']}
        ids=sorted(rows['baseline'], key=lambda i:((rows['emitted'][i].get('hunk_line_recall') or 0)-(rows['baseline'][i].get('hunk_line_recall') or 0),i))
        pq,repos,_=SLICES[sl]; gold={r['instance_id']:r for r in pd.read_parquet(ROOT/'lab'/pq).to_dict('records')}
        for which,i in [('largest_loss',ids[0]),('largest_gain',ids[-1])]:
            row=gold[i];dest=root/i
            subprocess.run(['git','clone','--quiet','--shared','--no-checkout',str(ROOT/'lab'/repos/row['repo'].replace('/','__')),str(dest)],check=True)
            subprocess.run(['git','checkout','-q',row['base_commit']],cwd=dest,check=True)
            case=dict(slice=sl,instance_id=i,selection=which,arms={})
            for arm,flags in [('baseline',[]),('emitted',['--emitted-coverage'])]:
                o=subprocess.run([str(binary),row['problem_statement'],str(dest),'--json','--no-cache','--budget','8192','--pad-lines','5','--len-exp','0.85','--pack-trace',*flags],capture_output=True,text=True,timeout=180)
                assert o.returncode==0,o.stderr
                payload=json.loads(o.stdout)
                digest=hashlib.sha256(json.dumps({k:payload[k] for k in ['regions','bundle']},sort_keys=True).encode()).hexdigest()
                assert digest==rows[arm][i]['payload_sha256'], (sl,i,arm,'trace payload drift')
                traces=[json.loads(line.removeprefix('ROUST_PACK_TRACE ')) for line in o.stderr.splitlines() if line.startswith('ROUST_PACK_TRACE ')]
                case['arms'][arm]=dict(payload_sha256=digest,fraction=rows[arm][i]['hunk_line_recall'],
                    final_regions=payload['regions'],traces=traces)
            report['cases'].append(case)
    (ROOT/'lab/results_regions/e53/traces.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
