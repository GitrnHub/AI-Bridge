from dataclasses import fields
import numpy as np
import pytest
import torch
from benchmark import DEFAULT
from ofabench.backends import Input, Prediction, make_backend, Unavailable
from ofabench.data import make_pair
from ofabench.mathops import zncc_surface, peak_offset, aggregate_flow

torch.set_num_threads(1)

@pytest.mark.parametrize('backend', ['phase', 'masked_zncc', 'pyr_lk'])
@pytest.mark.parametrize('seed', [0, 1, 2])
def test_sign_and_integer_shift(backend, seed):
    cfg={**DEFAULT, 'max_shift':16}
    p=make_pair('texture',96,96,seed,16)
    b=make_backend(backend,'cpu',p.a.shape,cfg)
    r=b.predict(b.prepare(p.a,p.b,p.mask_a,p.mask_b)).host()
    assert r['valid']
    assert np.linalg.norm(np.array([r['dx'],r['dy']])-p.gt)<.35

@pytest.mark.parametrize('backend,tolerance', [('phase',.5),('masked_zncc',.2),('pyr_lk',.2)])
def test_fractional_translation(backend,tolerance):
    p=make_pair('subpixel',96,96,0,16)
    b=make_backend(backend,'cpu',p.a.shape,{**DEFAULT,'max_shift':16})
    r=b.predict(b.prepare(p.a,p.b,p.mask_a,p.mask_b)).host()
    assert r['valid'] and np.linalg.norm(np.array([r['dx'],r['dy']])-p.gt)<tolerance

@pytest.mark.parametrize('backend', ['phase','masked_zncc','pyr_lk'])
def test_textureless_is_rejected(backend):
    p=make_pair('flat',96,96,0,16)
    b=make_backend(backend,'cpu',p.a.shape,{**DEFAULT,'max_shift':16})
    assert b.predict(b.prepare(p.a,p.b,p.mask_a,p.mask_b)).host()['valid'] is False

@pytest.mark.parametrize('dx,dy', [(0,0),(3,-4),(-5,2),(7,8)])
def test_masked_zncc_matches_direct_spatial_formula(dx,dy):
    rng=np.random.default_rng(123)
    a=torch.tensor(rng.integers(0,256,(40,48)),dtype=torch.uint8)
    b=torch.tensor(rng.integers(0,256,(40,48)),dtype=torch.uint8)
    ma=torch.tensor(rng.random((40,48))>.25)
    mb=torch.tensor(rng.random((40,48))>.35)
    y0,y1=max(0,-dy),min(40,40-dy)
    x0,x1=max(0,-dx),min(48,48-dx)
    mask=ma[y0:y1,x0:x1]&mb[y0+dy:y1+dy,x0+dx:x1+dx]
    aa=a[y0:y1,x0:x1][mask].double();bb=b[y0+dy:y1+dy,x0+dx:x1+dx][mask].double()
    aa-=aa.mean();bb-=bb.mean()
    exact=(aa*bb).sum()/torch.sqrt(aa.square().sum()*bb.square().sum())
    actual=zncc_surface(a,b,ma,mb,.1)[dy%(80),dx%(96)]
    assert abs(float(actual-exact))<2e-5


def test_ui_ablation_and_mask_aware_result():
    a=make_pair('ui_unmasked',96,96,0,16);b=make_pair('ui_masked',96,96,0,16)
    assert np.array_equal(a.a,b.a) and np.array_equal(a.b,b.b) and a.gt==b.gt
    assert a.mask_a.all() and not b.mask_a.all()
    algo=make_backend('masked_zncc','cpu',b.a.shape,{**DEFAULT,'max_shift':16})
    r=algo.predict(algo.prepare(b.a,b.b,b.mask_a,b.mask_b)).host()
    assert np.linalg.norm(np.array([r['dx'],r['dy']])-b.gt)<.2

@pytest.mark.parametrize('grid',[1,4])
def test_common_reducer_uses_image_pixels_not_grid_units(grid):
    shape=(64//grid,64//grid)
    flow=torch.empty(*shape,2);flow[:]=torch.tensor([6.5,-3.25])
    mask=torch.ones(64,64,dtype=torch.bool);source=torch.full((64,64),128,dtype=torch.uint8)
    xy,conf,valid=aggregate_flow(flow,mask,mask,source,16,grid)
    assert valid and torch.allclose(xy,torch.tensor([6.5,-3.25]),atol=1e-5)
    assert conf==1


def test_no_oracle_fields_in_backend_input():
    assert {f.name for f in fields(Input)}=={'a','b','ma','mb','estimator'}


def test_empty_zncc_and_prediction_nonfinite():
    a=torch.ones(32,32,dtype=torch.uint8);m=torch.zeros_like(a,dtype=torch.bool)
    xy,peak,valid=peak_offset(zncc_surface(a,a,m,m),8)
    p=Prediction(xy,peak,valid).host()
    assert not p['valid'] and p['dx'] is None and p['confidence'] is None


def test_cuda_absence_never_silent_fallback(monkeypatch):
    monkeypatch.setattr(torch.cuda,'is_available',lambda:False)
    with pytest.raises(Unavailable,match='CUDA is unavailable'):
        make_backend('phase','cuda:0',(96,96),DEFAULT)


def test_legacy_requires_windows_and_cuda():
    import hashlib
    from pathlib import Path
    source=Path(__file__).resolve().parents[1]/"vendor"/"ofa_v4.py"
    assert hashlib.sha256(source.read_bytes()).hexdigest()=="218dd1f1c40cd82d01fcfb3ef6f9ab6b98f4aaef4951c3112566191f777c2674"
    with pytest.raises(Unavailable,match='native Windows'):
        make_backend('ofa_v4','cpu',(256,256),DEFAULT)
