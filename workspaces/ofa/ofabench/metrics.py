"""Definitions keep missing, invalid and valid-but-inaccurate results distinct."""
from __future__ import annotations
import math
import numpy as np


def stats(values:list[float])->dict:
    x=np.asarray(values,dtype=float)
    x=x[np.isfinite(x)]
    if not x.size:
        return {"n":0,"mean":None,"p50":None,"p95":None,"p99":None,"min":None,"max":None}
    return {"n":int(x.size),"mean":float(x.mean()),"p50":float(np.percentile(x,50)),
            "p95":float(np.percentile(x,95)),"p99":float(np.percentile(x,99)),
            "min":float(x.min()),"max":float(x.max())}


def accuracy(rows:list[dict])->dict:
    labeled=[r for r in rows if r.get("gt_dx") is not None and r.get("observable",True)]
    errors=[float(r["error_px"]) for r in labeled if r.get("valid") and r.get("error_px") is not None]
    valid=len(errors); n=len(labeled)
    negative=[r for r in rows if not r.get("observable",True)]
    result={"pairs":len(rows),"labeled_observable_pairs":n,"unlabeled_pairs":sum(r.get("gt_dx") is None and r.get("observable",True) for r in rows),
            "valid_labeled_pairs":valid,"coverage":valid/n if n else None,
            "error_px_valid_only":stats(errors),
            "rmse_px_valid_only":math.sqrt(float(np.mean(np.square(errors)))) if errors else None,
            "unobservable_pairs":len(negative),
            "false_accept_rate_unobservable":sum(bool(r.get("valid")) for r in negative)/len(negative) if negative else None}
    for threshold in (.5,1.,2.,3.):
        # Invalid predictions remain in the denominator. Do not inflate accuracy by dropping them.
        result[f"success_le_{threshold:g}px"]=sum(e<=threshold for e in errors)/n if n else None
    return result


def add_error(pred:dict,gt:tuple[float,float]|None)->dict:
    result=dict(pred)
    result.update(gt_dx=gt[0] if gt else None,gt_dy=gt[1] if gt else None,error_px=None)
    if gt is not None and pred.get("valid"):
        result["error_px"]=math.hypot(pred["dx"]-gt[0],pred["dy"]-gt[1])
    return result


def sanitized(obj):
    if isinstance(obj,dict): return {str(k):sanitized(v) for k,v in obj.items()}
    if isinstance(obj,(tuple,list)): return [sanitized(v) for v in obj]
    if isinstance(obj,float) and not math.isfinite(obj): return None
    if isinstance(obj,np.generic): return sanitized(obj.item())
    return obj
