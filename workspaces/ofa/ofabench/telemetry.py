"""Sample process CPU/RSS and optional NVML board metrics; unsupported is null.

NVML GPU utilization is NOT OFA engine occupancy, SM occupancy or Tensor Core
utilization. Board metrics include the desktop and all other processes.
"""
from __future__ import annotations
import importlib.metadata as md
import os
import platform
import subprocess
import threading
import time
from pathlib import Path
import psutil
import torch
from .metrics import stats

MIB=1024*1024


def environment(device:str)->dict:
    versions={}
    for p in ("torch","torchvision","numpy","Pillow","psutil","nvidia-ml-py","opencv-python","opencv-contrib-python"):
        try: versions[p]=md.version(p)
        except md.PackageNotFoundError: versions[p]=None
    def command(args):
        try:
            r=subprocess.run(args,capture_output=True,text=True,timeout=10,check=False)
            return {"returncode":r.returncode,"stdout":r.stdout.strip(),"stderr":r.stderr.strip()}
        except (OSError,subprocess.TimeoutExpired) as e:
            return {"error":str(e)}
    root=Path(__file__).resolve().parents[1]
    env={"python":platform.python_version(),"platform":platform.platform(),
         "packages":versions,"device_requested":device,"pid":os.getpid(),
         "torch_cuda":torch.version.cuda,"cuda_available":torch.cuda.is_available(),
         "cuda_visible_devices":os.environ.get("CUDA_VISIBLE_DEVICES"),
         "torch_threads":torch.get_num_threads(),"logical_cpus":psutil.cpu_count(),
         "git":command(["git","-C",str(root),"rev-parse","HEAD"]),
         "git_dirty":command(["git","-C",str(root),"status","--porcelain"]),
         "nvidia_smi":command(["nvidia-smi","--query-gpu=name,uuid,driver_version,memory.total","--format=csv,noheader"])}
    if device.startswith("cuda") and torch.cuda.is_available():
        d=torch.device(device)
        prop=torch.cuda.get_device_properties(d)
        env.update(gpu_name=prop.name,gpu_uuid=str(getattr(prop,"uuid","")),
                   compute_capability=[prop.major,prop.minor],gpu_total_mib=prop.total_memory/MIB,
                   torch_arch_list=torch.cuda.get_arch_list())
    return env

class Sampler:
    def __init__(self,device:str,interval:float=.1,nvml_index:int|None=None):
        if interval<.05:
            raise ValueError("Telemetry interval must be >= .05 seconds")
        self.device,self.interval=device,interval
        self.process=psutil.Process()
        self.samples=[]
        self.errors=[]
        self.nvml=None
        self.handle=None
        self.stop_event=threading.Event()
        self.mapping=None
        if device.startswith("cuda"):
            try:
                import pynvml
                pynvml.nvmlInit()
                self.nvml=pynvml
                if nvml_index is not None:
                    self.handle=pynvml.nvmlDeviceGetHandleByIndex(int(nvml_index))
                    self.mapping=f"explicit physical NVML index {nvml_index}; caller must verify UUID"
                else:
                    uuid=str(getattr(torch.cuda.get_device_properties(torch.device(device)),"uuid",""))
                    if not uuid:
                        raise RuntimeError("No Torch UUID: provide nvml_index; CUDA ordinal is not assumed to equal NVML ordinal")
                    self.handle=pynvml.nvmlDeviceGetHandleByUUID(uuid)
                    self.mapping="matched to torch CUDA device UUID"
                self.uuid=pynvml.nvmlDeviceGetUUID(self.handle)
                if isinstance(self.uuid,bytes): self.uuid=self.uuid.decode()
            except Exception as e:
                self.errors.append(f"NVML initialization: {type(e).__name__}: {e}")
                self.handle=None

    def _safe(self,field,fn):
        try:
            value=fn()
            if isinstance(value,(int,float)) and value>2**60:
                raise RuntimeError("NVML_VALUE_NOT_AVAILABLE")
            return value
        except Exception as e:
            msg=f"{field}: {type(e).__name__}: {e}"
            if msg not in self.errors: self.errors.append(msg)
            return None

    def _process_gpu_memory(self):
        n=self.nvml
        seen=[]
        for name in ("nvmlDeviceGetComputeRunningProcesses","nvmlDeviceGetGraphicsRunningProcesses"):
            try:
                for p in getattr(n,name)(self.handle):
                    if p.pid==os.getpid() and p.usedGpuMemory<2**60:
                        seen.append(p.usedGpuMemory/MIB)
            except n.NVMLError:
                pass
        return max(seen) if seen else None

    def _sample(self):
        s={"t_seconds":time.perf_counter()-self.start_time,
           "process_rss_mib":self._safe("rss",lambda:self.process.memory_info().rss/MIB)}
        if self.handle is not None:
            n,h=self.nvml,self.handle
            u=self._safe("utilization",lambda:n.nvmlDeviceGetUtilizationRates(h))
            s.update(board_gpu_busy_pct=u.gpu if u else None,board_dram_busy_pct=u.memory if u else None,
                board_memory_used_mib=self._safe("board_memory",lambda:n.nvmlDeviceGetMemoryInfo(h).used/MIB),
                process_gpu_memory_mib=self._safe("process_gpu_memory",self._process_gpu_memory),
                board_power_w=self._safe("power",lambda:n.nvmlDeviceGetPowerUsage(h)/1000.),
                temperature_c=self._safe("temperature",lambda:n.nvmlDeviceGetTemperature(h,n.NVML_TEMPERATURE_GPU)),
                sm_clock_mhz=self._safe("clock",lambda:n.nvmlDeviceGetClockInfo(h,n.NVML_CLOCK_SM)))
        self.samples.append(s)

    def _loop(self):
        while not self.stop_event.wait(self.interval): self._sample()

    def start(self):
        self.start_time=time.perf_counter()
        c=self.process.cpu_times();self.start_cpu=c.user+c.system
        self._sample()
        self.thread=threading.Thread(target=self._loop,daemon=True)
        self.thread.start()
        return self

    def stop(self)->dict:
        self.stop_event.set()
        self.thread.join(timeout=5)
        self._sample()
        self.seconds=time.perf_counter()-self.start_time
        c=self.process.cpu_times();cpu_pct=100*(c.user+c.system-self.start_cpu)/max(self.seconds,1e-9)
        fields={k for s in self.samples for k in s if k!="t_seconds"}
        result={"seconds":self.seconds,"sample_count":len(self.samples),"interval_seconds":self.interval,
                "process_cpu_pct_one_core_100":cpu_pct,
                "process_cpu_pct_machine_normalized":cpu_pct/max(1,psutil.cpu_count() or 1),
                "nvml_available":self.handle is not None,"nvml_mapping":self.mapping,
                "nvml_gpu_uuid":getattr(self,"uuid",None),"errors":self.errors,
                "ofa_engine_occupancy_pct":None,
                "note":"Board-wide samples, not per-process GPU utilization or OFA/TensorCore occupancy; samples include monitoring overhead",
                "fields":{k:stats([s[k] for s in self.samples if s.get(k) is not None]) for k in sorted(fields)}}
        if self.nvml is not None:
            self._safe("nvml_shutdown",self.nvml.nvmlShutdown)
        return result
