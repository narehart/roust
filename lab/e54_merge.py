#!/usr/bin/env python3
"""Combine complete shards, verifying hashes, provenance, and exact full ID sets."""
import argparse
import json
from pathlib import Path
import pandas as pd
from e51_run import ROOT, SLICES, sha256


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifests',nargs='+',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args(); ms=[json.loads(p.read_text()) for p in args.manifests]
    first=ms[0];sl=first['slice'];pq,repos,n=SLICES[sl]
    assert len(ms)==first['shards'] and {m['shard'] for m in ms}==set(range(len(ms)))
    for m in ms:
        assert 'outputs_sha256' in m and m['input_n']==n
        for k in ['slice','shards','input_n','gold','gold_sha256','binaries','arms','budget','pad_lines','len_exp','timeout','isolate_block_cache','discovery_endpoints']:
            assert m[k]==first[k],('inconsistent shard metadata',k)
    ids=pd.read_parquet(ROOT/'lab'/pq)['instance_id'].tolist()
    assert len(ids)==n and len(set(ids))==n
    assert sha256(ROOT/'lab'/pq)==first['gold_sha256']
    args.out.mkdir(parents=True,exist_ok=True)
    assert not list(args.out.glob(f'{sl}_*')), 'refuse to overwrite aggregate'
    outputs={}
    for arm in first['arms']:
        records={}
        for p,m in zip(args.manifests,ms):
            path=p.parent/f'{sl}_{arm}.jsonl'
            assert sha256(path)==m['outputs_sha256'][arm]
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            assert [r['instance_id'] for r in rows]==m['ids']
            for r in rows:
                assert r['instance_id'] not in records,'duplicate ID across shards'
                records[r['instance_id']]=r
        assert set(records)==set(ids),'incomplete or extra evaluation IDs'
        path=args.out/f'{sl}_{arm}.jsonl'
        path.write_text(''.join(json.dumps(records[i],separators=(',',':'))+'\n' for i in ids))
        outputs[arm]=sha256(path)
    result={**first,'n':n,'full_gate':True,'ids':ids,'outputs_sha256':outputs,
            'repos':str(ROOT/'lab'/repos), # scorer uses immutable git-show only
            'source_manifests':[{ 'path':str(p),'sha256':sha256(p)} for p in args.manifests],
            'elapsed_seconds_sum':sum(m['elapsed_seconds'] for m in ms)}
    result.pop('shard');result.pop('elapsed_seconds')
    (args.out/f'{sl}_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(sl,n,'complete IDs and hashes verified')


if __name__=='__main__':main()
