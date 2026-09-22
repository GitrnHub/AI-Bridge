import json
from pathlib import Path
import subprocess
import sys
import numpy as np
from PIL import Image
import pytest
from benchmark import DEFAULT, validate
from ofabench.data import SCENES, make_pair, load_manifest
from ofabench.metrics import accuracy, sanitized
from ofabench.telemetry import Sampler

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('scene',SCENES)
def test_fixture_reproducible_and_well_formed(scene):
    a=make_pair(scene,96,96,3,16);b=make_pair(scene,96,96,3,16)
    a.validate()
    assert a.fingerprint==b.fingerprint
    assert a.gt==b.gt


def test_invalid_counts_as_accuracy_failure_and_unlabeled_is_na():
    rows=[{'gt_dx':1.,'valid':True,'error_px':.1}, {'gt_dx':1.,'valid':False,'error_px':None},
          {'gt_dx':None,'valid':True,'error_px':None}, {'gt_dx':None,'valid':True,'observable':False}]
    r=accuracy(rows)
    assert r['success_le_1px']==.5 and r['coverage']==.5
    assert r['unlabeled_pairs']==1 and r['false_accept_rate_unobservable']==1
    assert accuracy([rows[2]])['success_le_1px'] is None


def test_manifest_null_gt_and_invalid_length(tmp_path):
    im=np.full((32,32),120,dtype=np.uint8);Image.fromarray(im).save(tmp_path/'a.png')
    entry={'id':'real','previous':'a.png','current':'a.png','displacement_xy':None}
    manifest=tmp_path/'pairs.json';manifest.write_text(json.dumps({'pairs':[entry]}))
    assert load_manifest(manifest)[0].gt is None
    entry['displacement_xy']=[1]
    manifest.write_text(json.dumps({'pairs':[entry]}))
    with pytest.raises(ValueError,match='Ground truth'):
        load_manifest(manifest)

@pytest.mark.parametrize('patch',[
    {'max_shift':128},{'telemetry_interval':.001},{'min_overlap':0},
    {'backends':['phase','phase']},{'sizes':[[256,256],[256,256]]},
    {'sizes':[[256.5,256]]},{'ofa_post':'auto'},{'seeds':[0,0]},
    {'scenes':['texture','texture']},{'throughput_seconds':0},
])
def test_bad_config_rejected(patch):
    with pytest.raises(ValueError):validate({**DEFAULT,**patch})


def test_no_nan_serialization_and_telemetry_null():
    assert json.dumps(sanitized({'x':float('nan'),'y':float('inf')}),allow_nan=False)=='{"x": null, "y": null}'
    s=Sampler('cpu',.1).start();r=s.stop()
    assert r['ofa_engine_occupancy_pct'] is None and not r['nvml_available']
    assert r['sample_count']>=2 and r['process_cpu_pct_one_core_100']>=0


def test_end_to_end_cpu_subprocess_and_reports(tmp_path):
    run=subprocess.run([sys.executable,'benchmark.py','--config','configs/cpu_smoke.json','--out',str(tmp_path/'out')],
                       cwd=ROOT,capture_output=True,text=True,timeout=120)
    assert run.returncode==0,run.stdout+'\n'+run.stderr
    out=tmp_path/'out';results=json.loads((out/'results.json').read_text())
    assert len(results)==3
    hashes=[{p['pair_id']:p['input_sha256'] for p in r['predictions']} for r in results]
    assert hashes[0]==hashes[1]==hashes[2]
    for r in results:
        assert r['status']=='ok' and not r['is_gpu_benchmark']
        assert r['environment']['torch_threads']==1
        assert r['resident']['wall_ms']['n']==4
        assert r['accuracy']['unobservable_pairs']==2
        assert r['throughput']['pairs']>0
    for name in ('report.html','report.md','summary.csv','predictions.csv','run_config.json'):
        assert (out/name).stat().st_size>0
