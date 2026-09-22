"""Save environment diagnostics; do not import the native Windows OFA DLL on Linux."""
import argparse
from pathlib import Path
import json
import os
import torch
from ofabench.runner import write_json
from ofabench.telemetry import environment,Sampler

p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--device",default="cuda:0")
p.add_argument("--out",type=Path,default=Path("doctor.json"))
p.add_argument("--nvml-index",type=int)
a=p.parse_args()
r=environment(a.device)
r["original_ofa_platform_supported"]=os.name=="nt"
r["warnings"]=["CUDA availability does not prove OFA support. The benchmark queries API version/capabilities when constructing a session."]
if a.device.startswith("cuda") and torch.cuda.is_available():
    try:
        x=torch.rand(16,16,device=a.device);y=torch.fft.rfft2(x);torch.cuda.synchronize(torch.device(a.device))
        r["cuda_fft_probe"]="PASS"
    except Exception as e:r["cuda_fft_probe"]=f"FAIL: {e}"
s=Sampler(a.device,nvml_index=a.nvml_index).start()
r["telemetry_probe"]=s.stop()
write_json(a.out,r)
print(json.dumps(r,ensure_ascii=False,indent=2))
