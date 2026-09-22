"""Synchronized request latency and sustained throughput; one backend/shape is a separate process."""
from __future__ import annotations
import bisect
import gc
import json
from pathlib import Path
import time
import traceback
import numpy as np
import torch
from .backends import Unavailable,make_backend
from .data import dataset
from .metrics import accuracy,add_error,sanitized,stats
from .telemetry import Sampler,environment,MIB


def write_json(path:Path,obj)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(sanitized(obj),ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")


def _latency(backend,prepared,pairs,config,mode:str):
    wall,event=[],[]
    samples=[]
    n=int(config["latency_samples"])
    order=np.random.default_rng(510).permutation(len(pairs)).tolist()
    for i in range(n):
        k=order[i%len(order)]
        backend.synchronize()
        start=end=None
        if backend.device.type=="cuda" and backend.event_safe and mode=="resident":
            start,end=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)
        t=time.perf_counter_ns()
        if start is not None: start.record()
        p=prepared[k] if mode=="resident" else backend.prepare(pairs[k].a,pairs[k].b,pairs[k].mask_a,pairs[k].mask_b)
        pred=backend.predict(p)
        if end is not None: end.record()
        answer=pred.host()
        backend.synchronize()
        ms=(time.perf_counter_ns()-t)/1e6
        wall.append(ms)
        gpu_ms=start.elapsed_time(end) if start is not None else None
        if gpu_ms is not None: event.append(gpu_ms)
        samples.append({"pair_id":pairs[k].name,"wall_ms":ms,"cuda_graph_elapsed_ms":gpu_ms,"valid":answer["valid"]})
        if mode!="resident": del p
    summary=stats(wall)
    return {"wall_ms":summary,"fps_reciprocal_mean_latency":1000/summary["mean"],
            "cuda_graph_elapsed_ms":stats(event),"samples":samples,
            "boundary":"GPU-resident uint8 pair -> CPU dx/dy, includes preprocessing/reduction/sync" if mode=="resident" else
            "decoded CPU uint8 pair -> prepare/upload/mask estimator -> CPU dx/dy; excludes decoding and model/session init"}


def _sustained(backend,prepared,config):
    duration=float(config["throughput_seconds"])
    monitor=Sampler(str(backend.device),float(config["telemetry_interval"]),config.get("nvml_index")).start()
    backend.synchronize();t0=time.perf_counter();count=0
    chunk=int(config.get("throughput_chunk",8))
    while time.perf_counter()-t0<duration:
        for _ in range(chunk):
            # Complete offset pipeline, not raw flow only. Independent pairs, hints disabled.
            last=backend.predict(prepared[count%len(prepared)])
            count+=1
        backend.synchronize()
    backend.synchronize();seconds=time.perf_counter()-t0
    last.host()
    telemetry=monitor.stop()
    return {"pairs":count,"seconds":seconds,"fps":count/seconds,
            "ms_per_pair":seconds*1000/count,"chunk":chunk,
            "boundary":"resident complete pipeline; sync per chunk, final offset copied after timing; NOT host request latency"},telemetry,monitor.samples


def _load(backend,prepared,pairs,config):
    devices=int(config.get("load_devices",0))
    duration=float(config.get("load_seconds",0))
    if not devices or duration<=0: return None
    period=float(config.get("load_period_seconds",1.))
    rng=np.random.default_rng(911)
    arrivals=sorted((float(t),d) for d in range(devices)
                    for t in np.arange(rng.uniform(0,period),duration,period))
    times=[a[0] for a in arrivals]
    records=[];base=time.perf_counter();limit=max(duration*4,duration+5)
    for i,(scheduled,d) in enumerate(arrivals):
        now=time.perf_counter()-base
        if now>limit: break
        if now<scheduled: time.sleep(scheduled-now)
        started=time.perf_counter()-base
        queue_depth=max(0,bisect.bisect_right(times,started)-i-1)
        k=i%len(pairs)
        if config.get("load_input","host")=="host":
            p=backend.prepare(pairs[k].a,pairs[k].b,pairs[k].mask_a,pairs[k].mask_b)
        else: p=prepared[k]
        pred=backend.predict(p).host();backend.synchronize()
        done=time.perf_counter()-base
        records.append({"device":d,"scheduled_s":scheduled,"queue_ms":(started-scheduled)*1000,
                        "service_ms":(done-started)*1000,"response_ms":(done-scheduled)*1000,
                        "queue_depth":queue_depth,"valid":pred["valid"]})
    elapsed=time.perf_counter()-base
    deadline=float(config.get("load_deadline_ms",1000))
    return {"description":"Synthetic staggered clients, one FIFO worker, independent pairs. Not a real multi-device capture test.",
            "input_mode":config.get("load_input","host"),"devices":devices,"period_seconds":period,
            "offered_requests":len(arrivals),"completed":len(records),"unserved":len(arrivals)-len(records),
            "elapsed_seconds":elapsed,"completed_fps":len(records)/max(elapsed,1e-9),
            "deadline_ms":deadline,"deadline_misses":sum(r["response_ms"]>deadline for r in records)+len(arrivals)-len(records),
            "queue_ms":stats([r["queue_ms"] for r in records]),"response_ms":stats([r["response_ms"] for r in records]),
            "service_ms":stats([r["service_ms"] for r in records]),"records":records}


def run_worker(name:str,width:int,height:int,config:dict,out:Path)->int:
    out.mkdir(parents=True,exist_ok=True)
    result={"backend":name,"width":width,"height":height,"status":"error",
            "device":config["device"],"is_gpu_benchmark":config["device"].startswith("cuda"),
            "config":config}
    backend=None
    try:
        torch.set_num_threads(int(config.get("cpu_threads",1)))
        result["environment"]=environment(config["device"])
        torch.manual_seed(12345)
        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32=bool(config.get("allow_tf32",False))
            torch.backends.cudnn.allow_tf32=bool(config.get("allow_tf32",False))
        pairs=dataset(config,width,height)
        if not pairs: raise ValueError("No input pairs for this resolution")
        # Remove oracle labels at the backend boundary: only images and user-known masks.
        t=time.perf_counter()
        backend=make_backend(name,config["device"],(height,width),config)
        backend.synchronize()
        result["initialize_ms"]=(time.perf_counter()-t)*1000
        idle=Sampler(config["device"],float(config["telemetry_interval"]),config.get("nvml_index")).start()
        time.sleep(float(config.get("idle_seconds",.5)))
        result["idle_telemetry"]=idle.stop()
        t=time.perf_counter()
        prepared=[backend.prepare(p.a,p.b,p.mask_a,p.mask_b) for p in pairs]
        backend.synchronize()
        result["prepare_all_ms"]=(time.perf_counter()-t)*1000
        t=time.perf_counter();backend.predict(prepared[0]).host();backend.synchronize()
        result["first_call_ms"]=(time.perf_counter()-t)*1000
        for i in range(int(config["warmup"])):
            backend.predict(prepared[i%len(prepared)])
        backend.synchronize()
        if backend.device.type=="cuda":
            torch.cuda.reset_peak_memory_stats(backend.device)
            result["torch_memory_before_mib"]={"allocated":torch.cuda.memory_allocated(backend.device)/MIB,
                                               "reserved":torch.cuda.memory_reserved(backend.device)/MIB}
        rows=[]
        for p,ready in zip(pairs,prepared):
            pred=backend.predict(ready).host()
            row=add_error(pred,p.gt)
            row.update(pair_id=p.name,scene=p.scene,observable=p.observable,
                       provenance=p.provenance,input_sha256=p.fingerprint)
            rows.append(row)
        result["predictions"]=rows
        result["accuracy"]=accuracy(rows)
        result["accuracy_by_scene"]={s:accuracy([r for r in rows if r["scene"]==s]) for s in sorted({p.scene for p in pairs})}
        result["resident"]=_latency(backend,prepared,pairs,config,"resident")
        result["host_to_offset"]=_latency(backend,prepared,pairs,config,"host")
        throughput,telemetry,samples=_sustained(backend,prepared,config)
        result.update(throughput=throughput,telemetry=telemetry)
        write_json(out/"telemetry_samples.json",samples)
        result["load"]=_load(backend,prepared,pairs,config)
        if backend.device.type=="cuda":
            result["torch_memory_peak_mib"]={"allocated":torch.cuda.max_memory_allocated(backend.device)/MIB,
                                             "reserved":torch.cuda.max_memory_reserved(backend.device)/MIB}
        def mean_power(x): return x.get("fields",{}).get("board_power_w",{}).get("mean")
        active_power,idle_power=mean_power(telemetry),mean_power(result["idle_telemetry"])
        result["energy_estimates"]={"board_j_per_pair":active_power/throughput["fps"] if active_power is not None else None,
            "increment_above_idle_j_per_pair":(active_power-idle_power)/throughput["fps"]
                if active_power is not None and idle_power is not None and active_power>=idle_power else None,
            "note":"Sampled whole-board power / resident throughput. NOT isolated algorithm energy or direct OFA power."}
        result["backend_info"]=backend.info
        result["status"]="ok"
        code=0
    except Unavailable as exc:
        result.update(status="unavailable",error=str(exc));code=2
    except Exception as exc:
        result.update(status="error",error=f"{type(exc).__name__}: {exc}",traceback=traceback.format_exc());code=1
    finally:
        if backend is not None:
            try: backend.synchronize();backend.close()
            except Exception as exc: result["cleanup_error"]=str(exc);result["status"]="error";code=1
        write_json(out/"result.json",result)
        gc.collect()
    print(json.dumps({"backend":name,"size":f"{width}x{height}","status":result["status"],"error":result.get("error")},ensure_ascii=False))
    return code
