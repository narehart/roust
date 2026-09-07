"""Integrity tests for combining independent evaluation shards."""
import json
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
import e54_merge as merger


def fixture(tmp_path):
    lab=tmp_path/'lab';lab.mkdir()
    pd.DataFrame({'instance_id':['a','b','c','d']}).to_parquet(lab/'gold.parquet')
    manifests=[]
    for shard, ids in enumerate([['a','c'],['b','d']]):
        directory=tmp_path/str(shard);directory.mkdir()
        rows=''.join(json.dumps(dict(instance_id=i,payload=i))+'\n' for i in ids)
        predictions=directory/'probe_baseline.jsonl';predictions.write_text(rows)
        m=dict(slice='probe',shards=2,shard=shard,input_n=4,n=2,ids=ids,
               gold='lab/gold.parquet',gold_sha256=merger.sha256(lab/'gold.parquet'),
               binaries={'baseline':{'sha256':'frozen'}},arms={'baseline':[]},
               budget=8192,pad_lines=5,len_exp=.85,timeout=180,isolate_block_cache=True,
               discovery_endpoints=3,elapsed_seconds=1,
               outputs_sha256={'baseline':merger.sha256(predictions)})
        path=directory/'probe_manifest.json';path.write_text(json.dumps(m));manifests.append(path)
    return manifests


def run(tmp_path, manifests):
    argv=['merge',*map(str,manifests),'--out',str(tmp_path/'aggregate')]
    with patch.object(merger,'ROOT',tmp_path), patch.object(merger,'SLICES',{'probe':('gold.parquet','repos',4)}), patch('sys.argv',argv):
        merger.main()


def test_complete_shards_restore_original_order(tmp_path):
    manifests=fixture(tmp_path);run(tmp_path,list(reversed(manifests)))
    m=json.loads((tmp_path/'aggregate/probe_manifest.json').read_text())
    rows=[json.loads(line) for line in (tmp_path/'aggregate/probe_baseline.jsonl').read_text().splitlines()]
    assert m['full_gate'] and m['n']==4
    assert [r['instance_id'] for r in rows]==['a','b','c','d']


def test_duplicate_cross_shard_ids_are_rejected_even_with_updated_hash(tmp_path):
    manifests=fixture(tmp_path)
    p=tmp_path/'1/probe_baseline.jsonl';p.write_text(p.read_text().replace('"b"','"a"'))
    m=json.loads(manifests[1].read_text());m['ids'][0]='a';m['outputs_sha256']['baseline']=merger.sha256(p)
    manifests[1].write_text(json.dumps(m))
    with pytest.raises(AssertionError,match='duplicate ID'):run(tmp_path,manifests)


def test_changed_output_bytes_are_rejected(tmp_path):
    manifests=fixture(tmp_path)
    p=tmp_path/'0/probe_baseline.jsonl';p.write_text(p.read_text()+'\n')
    with pytest.raises(AssertionError):run(tmp_path,manifests)


def test_missing_shard_is_rejected(tmp_path):
    manifests=fixture(tmp_path)
    with pytest.raises(AssertionError):run(tmp_path,manifests[:1])
