"""Export deterministic inputs/known masks and GT for visual inspection or replay."""
import argparse
import json
from pathlib import Path
from PIL import Image
from benchmark import DEFAULT,validate
from ofabench.data import dataset
from ofabench.runner import write_json

p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--config",type=Path,default=Path("configs/quick.json"))
p.add_argument("--out",type=Path,default=Path("generated_inputs"))
a=p.parse_args();c={**DEFAULT,**json.loads(a.config.read_text(encoding="utf-8"))};validate(c)
if c.get("manifest"):
    c["manifest"]=str((a.config.resolve().parent/c["manifest"]).resolve())
if a.out.exists() and any(a.out.iterdir()):
    raise ValueError("Export directory must be new/empty")
for w,h in c["sizes"]:
    root=a.out/f"{w}x{h}";root.mkdir(parents=True,exist_ok=True);items=[]
    for index,pair in enumerate(dataset(c,w,h)):
        item={"id":pair.name,"scene":pair.scene,"displacement_xy":pair.gt,"observable":pair.observable,"sha256":pair.fingerprint}
        for key,data in (("previous",pair.a),("current",pair.b),("mask_previous",pair.mask_a.astype("uint8")*255),("mask_current",pair.mask_b.astype("uint8")*255)):
            # Numerical filenames avoid interpreting manifest IDs as filesystem paths.
            name=f"{index:06d}_{key}.png";Image.fromarray(data).save(root/name);item[key]=name
        items.append(item)
    write_json(root/"manifest.json",{"convention":"previous to current, +x right, +y down","pairs":items})
    print(root/"manifest.json")
