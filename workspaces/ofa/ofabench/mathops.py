"""GPU-capable math, also exercised on CPU for correctness (not GPU benchmarks)."""
from __future__ import annotations
import math
import torch
import torch.nn.functional as F


def peak_offset(score: torch.Tensor, max_shift: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Decode circular FFT indices, restrict search, and refine with 3-point parabolas."""
    h, w = score.shape
    yy, xx = torch.meshgrid(torch.arange(h,device=score.device),torch.arange(w,device=score.device),indexing="ij")
    sy, sx = torch.where(yy <= h//2,yy,yy-h),torch.where(xx <= w//2,xx,xx-w)
    admissible = (sx.abs()<=max_shift)&(sy.abs()<=max_shift)&torch.isfinite(score)
    s = torch.where(admissible, score, -torch.inf)
    k = s.flatten().argmax()
    y, x = k//w, k%w
    center = s[y,x]
    def refine(lo: torch.Tensor, hi: torch.Tensor) -> torch.Tensor:
        den = lo-2*center+hi
        safe = torch.isfinite(lo)&torch.isfinite(hi)&torch.isfinite(center)&(den.abs()>1e-10)&(den<0)
        value = .5*(lo-hi)/torch.where(safe,den,torch.ones_like(den))
        return torch.where(safe,value.clamp(-.5,.5),torch.zeros_like(value))
    subx = refine(s[y,(x-1)%w], s[y,(x+1)%w])
    suby = refine(s[(y-1)%h,x], s[(y+1)%h,x])
    offset = torch.stack((sx[y,x].float()+subx,sy[y,x].float()+suby))
    valid = torch.isfinite(center)
    return torch.where(valid,offset,torch.full_like(offset,float("nan"))),center,valid


def phase_offset(a: torch.Tensor,b: torch.Tensor,max_shift: int,window: bool=True) -> tuple[torch.Tensor,torch.Tensor,torch.Tensor]:
    a,b = a.float()/255,b.float()/255
    informative = (a.var()>1e-7)&(b.var()>1e-7)
    a,b = a-a.mean(),b-b.mean()
    if window:
        win = torch.hann_window(a.shape[0],periodic=False,device=a.device)[:,None]*torch.hann_window(a.shape[1],periodic=False,device=a.device)[None,:]
        a,b = a*win,b*win
    cross = torch.fft.rfft2(a).conj()*torch.fft.rfft2(b)
    cross = cross/cross.abs().clamp_min(1e-8)
    corr = torch.fft.irfft2(cross,s=a.shape)
    offset,peak,valid = peak_offset(corr,max_shift)
    valid = valid&informative
    return torch.where(valid,offset,torch.full_like(offset,float("nan"))),peak,valid


def zncc_surface(a:torch.Tensor,b:torch.Tensor,ma:torch.Tensor,mb:torch.Tensor,min_overlap:float=.35) -> torch.Tensor:
    """Exact overlap-normalized masked ZNCC, using six linear correlations.

    corr(X,Y)[dy,dx] = sum X(y,x)*Y(y+dy,x+dx).
    Mask overlap, means and variances are re-evaluated for EVERY displacement.
    Simply multiplying images by masks and phase-correlating is NOT equivalent.
    """
    a,b,ma,mb = a.float()/255,b.float()/255,ma.float(),mb.float()
    shape = (2*a.shape[0],2*a.shape[1])
    left = torch.fft.rfft2(torch.stack((ma,a*ma,a.square()*ma)),s=shape)
    right = torch.fft.rfft2(torch.stack((mb,b*mb,b.square()*mb)),s=shape)
    products = torch.stack((left[0].conj()*right[0],left[1].conj()*right[0],
                            left[0].conj()*right[1],left[2].conj()*right[0],
                            left[0].conj()*right[2],left[1].conj()*right[1]))
    n,sa,sb,saa,sbb,sab = torch.fft.irfft2(products,s=shape).unbind(0)
    n = n.clamp_min(0)
    safe_n = n.clamp_min(1)
    va,vb = (saa-sa.square()/safe_n).clamp_min(0),(sbb-sb.square()/safe_n).clamp_min(0)
    den = (va*vb).sqrt()
    ok = (n>=torch.minimum(ma.sum(),mb.sum())*min_overlap)&(n>=16)&(va>1e-6*safe_n)&(vb>1e-6*safe_n)
    score = ((sab-sa*sb/safe_n)/den.clamp_min(1e-12)).clamp(-1,1)
    return torch.where(ok,score,-torch.inf)


def translation_lk(a:torch.Tensor,b:torch.Tensor,ma:torch.Tensor,mb:torch.Tensor,
                   max_shift:int,levels:int=4,iterations:int=12) -> tuple[torch.Tensor,torch.Tensor,torch.Tensor]:
    """Robust pyramidal inverse-compositional Lucas-Kanade, translation-only.

    A global two-parameter model, not OpenCV's sparse feature-tracking API.
    No initialization from GT, OFA, or another tested algorithm.
    """
    aa,bb = a.float()[None,None]/255,b.float()[None,None]/255
    mm,nn = ma.float()[None,None],mb.float()[None,None]
    levels = min(levels,max(1,int(math.log2(min(a.shape)/24))+1))
    shift = torch.zeros(2,device=a.device)
    last_h,last_w = None,None
    support = torch.tensor(0.,device=a.device)
    determinant = torch.tensor(0.,device=a.device)
    for level in reversed(range(levels)):
        h,w = max(16,a.shape[0]//2**level),max(16,a.shape[1]//2**level)
        size=(h,w)
        A,B = F.interpolate(aa,size=size,mode="area"),F.interpolate(bb,size=size,mode="area")
        M,N = F.interpolate(mm,size=size,mode="area")>.99,F.interpolate(nn,size=size,mode="area")>.99
        if last_h is not None:
            shift = shift*shift.new_tensor((w/last_w,h/last_h))
        last_h,last_w=h,w
        pad=F.pad(A,(1,1,1,1),mode="replicate")
        gx=.5*(pad[:,:,1:-1,2:]-pad[:,:,1:-1,:-2])
        gy=.5*(pad[:,:,2:,1:-1]-pad[:,:,:-2,1:-1])
        yy,xx=torch.meshgrid(torch.arange(h,device=a.device),torch.arange(w,device=a.device),indexing="ij")
        for _ in range(iterations):
            x,y=xx+shift[0],yy+shift[1]
            grid=torch.stack((2*x/(w-1)-1,2*y/(h-1)-1),-1)[None]
            warped=F.grid_sample(B,grid,mode="bilinear",align_corners=True)
            target_valid=F.grid_sample(N.float(),grid,mode="bilinear",align_corners=True)>.999
            good=M&target_valid&(x[None,None]>1)&(x[None,None]<w-2)&(y[None,None]>1)&(y[None,None]<h-2)
            residual=A-warped
            weights=good.float()*(.04/residual.abs().clamp_min(.04))
            hxx=(weights*gx.square()).sum(); hxy=(weights*gx*gy).sum(); hyy=(weights*gy.square()).sum()
            rx=(weights*gx*residual).sum(); ry=(weights*gy*residual).sum()
            determinant=hxx*hyy-hxy.square()
            safe=determinant.clamp_min(1e-12)
            delta=torch.stack(((hyy*rx-hxy*ry)/safe,(hxx*ry-hxy*rx)/safe)).clamp(-3,3)
            shift=shift+torch.where(determinant>1e-8,delta,torch.zeros_like(delta))
            limit=shift.new_tensor((max_shift*w/a.shape[1],max_shift*h/a.shape[0]))
            shift=torch.maximum(torch.minimum(shift,limit),-limit)
            support=good.float().mean()
    valid=(determinant>1e-8)&(support>.1)&torch.isfinite(shift).all()
    return torch.where(valid,shift,torch.full_like(shift,float("nan"))),support,valid


def aggregate_flow(flow:torch.Tensor,ma:torch.Tensor,mb:torch.Tensor,source:torch.Tensor,
                   max_shift:int,grid_size:int=1,radius:float=1.75) -> tuple[torch.Tensor,torch.Tensor,torch.Tensor]:
    """2D motion-mode histogram then mean refinement; all work stays on device.

    Masks contain only known UI/ROI. Target-mask lookup uses predicted flow,
    never ground truth. Fixed-grid OFA vectors are already in IMAGE pixels.
    """
    h,w=flow.shape[:2]
    yy,xx=torch.meshgrid(torch.arange(h,device=flow.device),torch.arange(w,device=flow.device),indexing="ij")
    src_y=(yy*grid_size+grid_size//2).clamp_max(ma.shape[0]-1)
    src_x=(xx*grid_size+grid_size//2).clamp_max(ma.shape[1]-1)
    finite=torch.isfinite(flow).all(-1)
    clean=torch.nan_to_num(flow,nan=0.,posinf=0.,neginf=0.)
    tx=src_x+clean[...,0]; ty=src_y+clean[...,1]
    inside=(tx>=0)&(ty>=0)&(tx<=mb.shape[1]-1)&(ty<=mb.shape[0]-1)
    target=mb[ty.round().long().clamp(0,mb.shape[0]-1),tx.round().long().clamp(0,mb.shape[1]-1)]
    # Visible source activity avoids stationary zero-background dominating sparse fixtures.
    active=source[src_y,src_x]>8
    good=finite&ma[src_y,src_x]&target&inside&active&(clean.abs()<=max_shift).all(-1)
    bins=2*max_shift+1
    q=clean.round().long().clamp(-max_shift,max_shift)+max_shift
    hist=torch.zeros(bins*bins,device=flow.device)
    hist.scatter_add_(0,(q[...,1]*bins+q[...,0]).flatten(),good.float().flatten())
    peak=hist.argmax()
    mode=torch.stack((peak%bins-max_shift,peak//bins-max_shift)).float()
    inlier=good&((clean-mode).square().sum(-1)<=radius*radius)
    n=inlier.sum(); total=good.sum()
    offset=(clean*inlier[...,None]).sum((0,1))/n.clamp_min(1)
    valid=(n>=8)&(total>=8)&torch.isfinite(offset).all()
    return torch.where(valid,offset,torch.full_like(offset,float("nan"))),n/total.clamp_min(1),valid
