#!/usr/bin/env python3
"""Run from workspaces/ofa: python benchmark.py --config configs/quick.json."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
from ofabench.backends import NAMES
from ofabench.data import SCENES
from ofabench.report import build_report
from ofabench.runner import run_worker,write_json

ROOT=Path(__file__).resolve().parent
DEFAULT={"device":"cuda:0","backends":["ofa_v4","phase","masked_zncc","pyr_lk","raft_small"],
    "required_backends":["ofa_v4","phase","masked_zncc","pyr_lk"],
    "sizes":[[256,256],[640,480]],"scenes":list(SCENES),"seeds":[0,1,2,3],
    "max_shift":64,"warmup":12,"latency_samples":40,"throughput_seconds":4.,"throughput_chunk":8,
    "telemetry_interval":.1,"idle_seconds":1.,"cpu_threads":1,"worker_timeout_seconds":1800,
    "ofa_preset":"medium","ofa_grid":4,"ofa_post":"cuda","ofa_cost_threshold":64,
    "ofa_fb_threshold":2.,"raft_precision":"fp32","raft_updates":12,"download_weights":False,
    "allow_tf32":False,"phase_window":True,"min_overlap":.35,"lk_levels":4,"lk_iterations":12,
    "load_devices":0,"load_seconds":0.,"load_period_seconds":1.,"load_input":"host","load_deadline_ms":1000}


def validate(c:dict)->None:
    if not c["backends"] or any(x not in NAMES for x in c["backends"]):raise ValueError(f"Invalid backend list; available: {NAMES}")
    if len(set(c["backends"]))!=len(c["backends"]):raise ValueError("Duplicate backends")
    if not c["sizes"] or any(len(s)!=2 or any(type(v) is not int or v<32 for v in s) for s in c["sizes"]):raise ValueError("sizes must be [width,height], each >=32")
    if len(set(map(tuple,c["sizes"])))!=len(c["sizes"]):raise ValueError("Duplicate sizes")
    if len(set(c["scenes"]))!=len(c["scenes"]):raise ValueError("Duplicate scenes")
    if "phase" in c["backends"] and any(c["max_shift"] >= min(s)/2 for s in c["sizes"]):raise ValueError("Phase search must be less than half the smaller image dimension")
    if not c["scenes"] or any(x not in SCENES for x in c["scenes"]):raise ValueError("Unknown/empty synthetic scenes")
    if not c["seeds"] or len(c["seeds"])!=len(set(c["seeds"])):raise ValueError("Seeds must be nonempty and unique")
    if c["max_shift"]<2 or c["latency_samples"]<1 or c["warmup"]<0:raise ValueError("Invalid shift/sample/warmup counts")
    if c["throughput_seconds"]<=0 or c["throughput_chunk"]<1 or c["idle_seconds"]<0:raise ValueError("Invalid measurement durations")
    if c["telemetry_interval"]<.05:raise ValueError("Telemetry interval must be >=50 ms")
    if not 0<c["min_overlap"]<=1:raise ValueError("min_overlap must be in (0,1]")
    if c["ofa_post"] not in ("cuda","torch"):raise ValueError("No automatic OFA postprocess fallback")
    if c["raft_precision"] not in ("fp32","fp16"):raise ValueError("Unknown RAFT precision")
    if c["ofa_grid"] not in (1,2,4) or c["ofa_preset"] not in ("slow","medium","fast"):raise ValueError("Invalid OFA grid/preset")
    if c["load_devices"]<0 or c["load_seconds"]<0 or c["load_period_seconds"]<=0:raise ValueError("Invalid load parameters")
    if c["load_input"] not in ("host","resident"):raise ValueError("Invalid load_input")
    if c["raft_updates"]<1 or c["lk_levels"]<1 or c["lk_iterations"]<1 or c["cpu_threads"]<1:raise ValueError("Iteration/thread counts must be positive")


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path)
    parser.add_argument("--device")
    parser.add_argument("--only",help="Comma-separated backend names")
    parser.add_argument("--out",type=Path)
    parser.add_argument("--download-weights",action="store_true")
    parser.add_argument("--strict",action="store_true",help="Treat every selected backend as required")
    parser.add_argument("--manifest",type=Path,help="Real-image manifest; images must match configured sizes")
    parser.add_argument("--worker",nargs=3,metavar=("BACKEND","WIDTH","HEIGHT"),help=argparse.SUPPRESS)
    args=parser.parse_args()
    config=dict(DEFAULT)
    if args.config:
        config.update(json.loads(args.config.read_text(encoding="utf-8")))
        if config.get("manifest"):
            config["manifest"]=str((args.config.resolve().parent/config["manifest"]).resolve())
    if args.device:config["device"]=args.device
    if args.only:config["backends"]=args.only.split(",")
    if args.download_weights:config["download_weights"]=True
    if args.manifest:config["manifest"]=str(args.manifest.resolve())
    if args.strict:config["required_backends"]=list(config["backends"])
    validate(config)
    if args.worker:
        name,w,h=args.worker
        if args.out is None:raise ValueError("Worker requires --out")
        return run_worker(name,int(w),int(h),config,args.out.resolve())
    out=(args.out or ROOT/"results"/dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if out.exists() and any(out.iterdir()):raise ValueError("Output directory must be new/empty; never mix distinct runs")
    out.mkdir(parents=True,exist_ok=True)
    write_json(out/"run_config.json",config)
    results=[]
    for w,h in config["sizes"]:
        for name in config["backends"]:
            job=out/f"{name}_{w}x{h}"
            job.mkdir(parents=True,exist_ok=True)
            cmd=[sys.executable,str(ROOT/"benchmark.py"),"--config",str(out/"run_config.json"),
                 "--worker",name,str(w),str(h),"--out",str(job)]
            print(f"Running {name} {w}x{h} ({config['device']})",flush=True)
            with (job/"worker.log").open("w",encoding="utf-8") as log:
                try:
                    completed=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,
                        timeout=float(config["worker_timeout_seconds"]),check=False)
                    exitcode=completed.returncode
                except subprocess.TimeoutExpired:
                    exitcode=-999
            path=job/"result.json"
            if path.exists():
                result=json.loads(path.read_text(encoding="utf-8"))
            else:
                result={"backend":name,"width":w,"height":h,"device":config["device"],"status":"error",
                        "error":f"Worker exited {exitcode} without results (native crash/timeout); inspect worker.log"}
            result["worker_exitcode"]=exitcode
            if exitcode not in (0,2) and result["status"]=="ok":
                result.update(status="error",error=f"Worker exit {exitcode} despite result; inspect worker.log")
            write_json(path,result)
            results.append(result)
            write_json(out/"results.json",results)
            build_report(out,results)
            print("  "+result["status"]+(": "+result["error"] if result.get("error") else ""),flush=True)
    print(f"Report: {out/'report.html'}")
    failed=any(r["status"]=="error" or (r["backend"] in config["required_backends"] and r["status"]!="ok") for r in results)
    if not any(r["status"]=="ok" for r in results):failed=True
    return 2 if failed else 0

if __name__=="__main__":
    raise SystemExit(main())
