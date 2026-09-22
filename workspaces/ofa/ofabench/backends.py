"""Backend contracts: prepared inputs never contain labels or expected shifts."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import contextlib
import hashlib
import importlib.util
import os
import sys
from typing import Any
import numpy as np
import torch
import torch.nn.functional as F
from .mathops import aggregate_flow, peak_offset, phase_offset, translation_lk, zncc_surface

NAMES=("phase","masked_zncc","pyr_lk","raft_small","raft_large",
       "ofa_v4","ofa_v4_forward","ofa_common","opencv_farneback")

class Unavailable(RuntimeError):
    """Requested hardware or optional dependency is unavailable; never fallback."""

@dataclass
class Input:
    a: Any
    b: Any
    ma: Any
    mb: Any
    estimator: Any = None

@dataclass
class Prediction:
    xy: torch.Tensor
    confidence: torch.Tensor
    valid: torch.Tensor

    def host(self) -> dict:
        # One compact D2H copy. This synchronization is INSIDE request latency.
        values=torch.cat((self.xy.reshape(2),self.confidence.float().reshape(1),
                          self.valid.float().reshape(1))).detach().cpu().tolist()
        valid=bool(values[3]) and bool(np.isfinite(values[:2]).all())
        return {"dx":float(values[0]) if valid else None,
                "dy":float(values[1]) if valid else None,
                "valid":valid,
                "confidence":float(values[2]) if np.isfinite(values[2]) else None}

class Backend:
    event_safe=True
    def __init__(self,name:str,device:torch.device,shape:tuple[int,int],config:dict):
        self.name,self.device,self.shape,self.config=name,device,shape,config
        self.max_shift=int(config["max_shift"])
        self.info={"name":name,"device":str(device),"precision":"fp32",
                   "mask_policy":"known source/target ROI only","output":"global translation in image pixels"}

    def prepare(self,a:np.ndarray,b:np.ndarray,ma:np.ndarray,mb:np.ndarray)->Input:
        return Input(*(torch.from_numpy(np.ascontiguousarray(x)).to(self.device) for x in (a,b,ma,mb)))

    def predict(self,p:Input)->Prediction:
        if self.name=="phase":
            args=phase_offset(p.a,p.b,self.max_shift,self.config.get("phase_window",True))
        elif self.name=="masked_zncc":
            args=peak_offset(zncc_surface(p.a,p.b,p.ma,p.mb,float(self.config.get("min_overlap",.35))),self.max_shift)
        elif self.name=="pyr_lk":
            args=translation_lk(p.a,p.b,p.ma,p.mb,self.max_shift,
                                int(self.config.get("lk_levels",4)),int(self.config.get("lk_iterations",12)))
        else:
            raise ValueError(f"No implementation: {self.name}")
        return Prediction(*args)

    def synchronize(self)->None:
        if self.device.type=="cuda":
            torch.cuda.synchronize(self.device)

    def close(self)->None:
        pass

class RaftBackend(Backend):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        try:
            from torchvision.models.optical_flow import raft_small,raft_large,Raft_Small_Weights,Raft_Large_Weights
        except (ImportError,RuntimeError) as exc:
            raise Unavailable(f"A matching torchvision wheel is required: {exc}") from exc
        small=self.name=="raft_small"
        weights=(Raft_Small_Weights.C_T_V2 if small else Raft_Large_Weights.C_T_SKHT_V2)
        # Explicit weights, never random-weight 'benchmarks'. Do not download by surprise.
        from urllib.parse import urlparse
        filename=Path(urlparse(weights.url).path).name
        checkpoint=Path(torch.hub.get_dir())/"checkpoints"/filename
        if not checkpoint.exists() and not self.config.get("download_weights",False):
            raise Unavailable(f"Missing {filename}. Run download_weights.py or use --download-weights.")
        self.model=(raft_small if small else raft_large)(weights=weights,progress=True).eval().to(self.device)
        self.amp=self.config.get("raft_precision","fp32")=="fp16"
        if self.amp and self.device.type!="cuda":
            raise Unavailable("RAFT fp16 requires CUDA; use fp32 for explicit CPU checks")
        self.steps=int(self.config.get("raft_updates",12))
        self.info.update(weights=weights.name,weights_url=weights.url,
                         checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),updates=self.steps,
                         precision="autocast-fp16" if self.amp else "fp32",compile=False,
                         mask_policy="unmasked model inference; known masks in common flow reducer",
                         padding="replicate to multiples of 8, minimum 128; no resizing")

    def predict(self,p:Input)->Prediction:
        h,w=self.shape
        ph,pw=max(128,((h+7)//8)*8),max(128,((w+7)//8)*8)
        a=F.pad(p.a.float()[None,None].repeat(1,3,1,1)/127.5-1,(0,pw-w,0,ph-h),mode="replicate")
        b=F.pad(p.b.float()[None,None].repeat(1,3,1,1)/127.5-1,(0,pw-w,0,ph-h),mode="replicate")
        autocast=torch.autocast("cuda",dtype=torch.float16) if self.amp else contextlib.nullcontext()
        with torch.inference_mode(),autocast:
            flow=self.model(a,b,num_flow_updates=self.steps)[-1][0,:,:h,:w].permute(1,2,0).float()
        return Prediction(*aggregate_flow(flow,p.ma,p.mb,p.a,self.max_shift))

class OFABackend(Backend):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if os.name!="nt" or self.device.type!="cuda":
            raise Unavailable("The OFA.zip V4 ctypes implementation requires native Windows + NVIDIA CUDA; not WSL/Linux/CPU")
        module_path=Path(__file__).resolve().parents[1]/"vendor"/"ofa_v4.py"
        if not module_path.exists():
            raise Unavailable("Missing vendor/ofa_v4.py; restore the source pinned in docs/REFERENCE.md")
        key="_ofabench_legacy_v4"
        spec=importlib.util.spec_from_file_location(key,module_path)
        if spec is None or spec.loader is None:
            raise Unavailable("Cannot load the V4 OFA source")
        self.legacy=importlib.util.module_from_spec(spec)
        sys.modules[key]=self.legacy
        spec.loader.exec_module(self.legacy)
        self.grid=int(self.config.get("ofa_grid",4))
        self.both=self.name=="ofa_v4"
        self.fused=self.name!="ofa_common"
        self.post=str(self.config.get("ofa_post","cuda"))
        if self.post not in ("cuda","torch"):
            raise ValueError("ofa_post must be cuda or torch; auto fallback is forbidden")
        self.engine=self.legacy.NvidiaOpticalFlowCuda(self.shape[1],self.shape[0],
            gpu_id=int(self.device.index or 0),grid_size=self.grid,preset=self.config.get("ofa_preset","medium"),
            enable_cost=True,buffer_count=4,bidirectional=self.both)
        self.info.update(precision="hardware S10.5; CUDA reduction",api=self.engine.api_version_text,
            driver_api=self.engine.driver_api_version_text,grid=self.grid,preset=self.engine.preset,
            temporal_hints=False,bidirectional=self.both,
            post_backend=self.post if self.fused else "common torch histogram",
            mask_policy="V4 source activity ROI + cost/FB; no target ROI" if self.fused else "known source/target ROI",
            preparation="V4 per-pair mask and estimator allocation included in host_to_offset, excluded from resident")

    def prepare(self,a:np.ndarray,b:np.ndarray,ma:np.ndarray,mb:np.ndarray)->Input:
        p=super().prepare(a,b,ma,mb)
        if self.fused:
            h,w=self.shape
            gh,gw=(h+self.grid-1)//self.grid,(w+self.grid-1)//self.grid
            activity=((p.a>8)&p.ma).float()[None,None]
            activity=F.pad(activity,(0,gw*self.grid-w,0,gh*self.grid-h))
            activity=F.avg_pool2d(activity,self.grid,self.grid)[0,0]>.25
            # Sparse/empty masks are a rejection, not an exception or false zero shift.
            if int(activity.sum().item())>=8:
                p.estimator=self.legacy.FusedOffsetEstimator(activity,grid_size=self.grid,
                    cost_threshold=int(self.config.get("ofa_cost_threshold",64)),bin_size=.5,
                    peak_radius=1.75,max_displacement=float(self.max_shift),
                    fb_threshold=float(self.config.get("ofa_fb_threshold",2.)),backend=self.post)
        return p

    def predict(self,p:Input)->Prediction:
        if self.both:
            f,b=self.engine.execute_bidirectional(p.a,p.b,disable_temporal_hints=True,convert_to_float=False,copy_result=False)
        else:
            f=self.engine.execute(p.a,p.b,disable_temporal_hints=True,convert_to_float=False,copy_result=False)
            b=None
        if self.fused:
            if p.estimator is None:
                return Prediction(torch.full((2,),float("nan"),device=self.device),
                                  torch.tensor(0.,device=self.device),torch.tensor(False,device=self.device))
            r=p.estimator.estimate(f,b)
            valid=torch.isfinite(r.offset).all()&(r.valid_ratio>0)&(r.confidence>0)
            return Prediction(r.offset,r.confidence,valid)
        flow=f.raw_flow.float()/32.0
        # Shared reducer has no hidden knowledge of OFA cost (fair postprocess ablation).
        return Prediction(*aggregate_flow(flow,p.ma,p.mb,p.a,self.max_shift,self.grid))

    def close(self)->None:
        if hasattr(self,"engine"):
            self.engine.close()

class OpenCVBackend(Backend):
    event_safe=False
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.device.type!="cuda":
            raise Unavailable("opencv_farneback is CUDA-only; never replace with CPU Farneback")
        try:
            import cv2
        except ImportError as exc:
            raise Unavailable("Requires a custom CUDA-enabled OpenCV + opencv_contrib build") from exc
        if not hasattr(cv2,"cuda") or cv2.cuda.getCudaEnabledDeviceCount()<=0:
            raise Unavailable("cv2 has no CUDA support. Ordinary opencv-python/contrib-python wheels are CPU-only")
        factory=getattr(getattr(cv2,"cuda_FarnebackOpticalFlow",None),"create",None)
        if factory is None:
            factory=getattr(cv2.cuda,"FarnebackOpticalFlow_create",None)
        if factory is None:
            raise Unavailable("cv2 CUDA Farneback bindings missing; rebuild cudaoptflow")
        if os.environ.get("CUDA_VISIBLE_DEVICES"):
            raise Unavailable("Unset CUDA_VISIBLE_DEVICES for the OpenCV comparison; physical index mapping must be explicit")
        cv2.cuda.setDevice(int(self.device.index or 0))
        self.cv2=cv2
        self.engine=factory(5,.5,False,21,5,7,1.5,0)
        self.info.update(opencv_version=cv2.__version__,
            transfer_policy="GpuMat inputs; flow.download then H2D for common torch reducer; BOTH transfers timed",
            gpu_event_ms=None,mask_policy="unmasked CUDA flow; known masks in common reducer")

    def prepare(self,a:np.ndarray,b:np.ndarray,ma:np.ndarray,mb:np.ndarray)->Input:
        ga,gb=self.cv2.cuda_GpuMat(),self.cv2.cuda_GpuMat()
        ga.upload(a);gb.upload(b)
        return Input(ga,gb,torch.from_numpy(ma).to(self.device),torch.from_numpy(mb).to(self.device),
                     torch.from_numpy(a).to(self.device))

    def predict(self,p:Input)->Prediction:
        flow=self.engine.calc(p.a,p.b,None).download()
        flow=torch.from_numpy(np.ascontiguousarray(flow)).to(self.device)
        return Prediction(*aggregate_flow(flow,p.ma,p.mb,p.estimator,self.max_shift))

    def synchronize(self)->None:
        self.cv2.cuda.Stream_Null().waitForCompletion()
        super().synchronize()


def make_backend(name:str,device:str,shape:tuple[int,int],config:dict)->Backend:
    if name not in NAMES:
        raise ValueError(f"Unknown backend {name}; choose from {NAMES}")
    d=torch.device(device)
    if d.type not in ("cpu","cuda"):
        raise Unavailable("Only explicit cpu or cuda devices are supported")
    if d.type=="cuda":
        if not torch.cuda.is_available():
            raise Unavailable("CUDA is unavailable; use --device cpu ONLY for correctness smoke tests")
        torch.cuda.set_device(d)
    cls=OFABackend if name.startswith("ofa_") else RaftBackend if name.startswith("raft_") else OpenCVBackend if name=="opencv_farneback" else Backend
    obj=cls(name,d,shape,config)
    if name=="phase":
        obj.info["mask_policy"]="ignores masks; Hann window baseline (not masked phase correlation)"
    return obj
