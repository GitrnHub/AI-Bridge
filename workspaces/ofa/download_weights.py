"""Explicitly download official RAFT weights before timing. No model weights in Git."""
import argparse
import hashlib
from pathlib import Path
from urllib.parse import urlparse
import torch
from torchvision.models.optical_flow import Raft_Small_Weights,Raft_Large_Weights

p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--large",action="store_true",help="Also cache RAFT-Large")
a=p.parse_args()
weights=[Raft_Small_Weights.C_T_V2]
if a.large:weights.append(Raft_Large_Weights.C_T_SKHT_V2)
for w in weights:
    torch.hub.load_state_dict_from_url(w.url,check_hash=True,map_location="cpu")
    path=Path(torch.hub.get_dir())/"checkpoints"/Path(urlparse(w.url).path).name
    print(path.name, path.stat().st_size,hashlib.sha256(path.read_bytes()).hexdigest())
