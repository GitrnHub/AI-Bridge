"""Deterministic, ground-truthed image pairs. No ground truth reaches a backend."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SCENES = (
    "texture", "subpixel", "textured_dot", "sparse", "multi_object",
    "repetitive", "large_shift", "brightness", "noise_blur", "occlusion",
    "ui_unmasked", "ui_masked", "independent_motion", "flat",
)

@dataclass
class Pair:
    name: str
    scene: str
    a: np.ndarray
    b: np.ndarray
    mask_a: np.ndarray
    mask_b: np.ndarray
    gt: tuple[float, float] | None
    observable: bool = True
    provenance: str = "synthetic"

    @property
    def fingerprint(self) -> str:
        h = hashlib.sha256()
        for x in (self.a, self.b, self.mask_a, self.mask_b):
            h.update(np.ascontiguousarray(x).tobytes())
        return h.hexdigest()

    def validate(self) -> None:
        if self.a.ndim != 2 or self.a.shape != self.b.shape:
            raise ValueError(f"{self.name}: equal-sized grayscale frames required")
        if min(self.a.shape) < 16:
            raise ValueError("Frames must be at least 16 x 16")
        if self.a.dtype != np.uint8 or self.b.dtype != np.uint8:
            raise ValueError("Frames must be uint8")
        for mask in (self.mask_a, self.mask_b):
            if mask.dtype != np.bool_ or mask.shape != self.a.shape:
                raise ValueError("Masks must be boolean and match the frames")
        if self.gt is not None and (len(self.gt) != 2 or not np.isfinite(self.gt).all()):
            raise ValueError("Ground truth must be finite or null")


def _texture(h: int, w: int, rng: np.random.Generator) -> np.ndarray:
    result = np.zeros((h, w), dtype=np.float32)
    for scale, weight in ((3, .38), (11, .36), (37, .26)):
        seed = rng.integers(0, 256, (max(2, h // scale), max(2, w // scale)), dtype=np.uint8)
        result += weight * np.asarray(Image.fromarray(seed).resize((w, h), Image.Resampling.BILINEAR))
    lo, hi = np.percentile(result, [1, 99])
    return np.clip((result - lo) * (230 / max(hi - lo, 1)) + 12, 0, 255).astype(np.uint8)


def _crop_shift(world: np.ndarray, h: int, w: int, margin: int, dx: float, dy: float) -> np.ndarray:
    # B(x + dx, y + dy) = A(x, y): positive x is right, positive y is down.
    y = np.arange(h, dtype=np.float64)[:, None] + margin - dy
    x = np.arange(w, dtype=np.float64)[None, :] + margin - dx
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    wx, wy = x - x0, y - y0
    if x0.min() < 0 or y0.min() < 0 or x0.max()+1 >= world.shape[1] or y0.max()+1 >= world.shape[0]:
        raise ValueError("World padding is insufficient")
    out = ((1-wx)*(1-wy)*world[y0, x0] + wx*(1-wy)*world[y0, x0+1]
           + (1-wx)*wy*world[y0+1, x0] + wx*wy*world[y0+1, x0+1])
    return np.rint(out).clip(0, 255).astype(np.uint8)


def make_pair(scene: str, width: int, height: int, seed: int = 0, max_shift: int = 64) -> Pair:
    if scene not in SCENES:
        raise ValueError(f"Unknown scene: {scene}")
    if max_shift < 2 or min(width, height) < 32:
        raise ValueError("max_shift >= 2 and image dimensions >= 32 are required")
    # The UI ablation MUST use identical frames and transformations.
    source_scene = "ui" if scene in ("ui_unmasked", "ui_masked") else scene
    digest = int.from_bytes(hashlib.sha256(source_scene.encode()).digest()[:4], "little")
    rng = np.random.default_rng(seed + digest)
    limit = min(max_shift - 1, max(2, min(width, height)//7))
    dx, dy = [int(x) for x in rng.integers(-limit, limit+1, 2)]
    if dx == dy == 0:
        dx = 2
    if scene == "subpixel":
        dx, dy = float(dx) + .35, float(dy) - .65
    if scene == "large_shift":
        dx, dy = min(max_shift-1, width//3), -min(max_shift-1, height//4)
    margin = max_shift + 4
    wh, ww = height+2*margin, width+2*margin
    world = _texture(wh, ww, rng)
    yy, xx = np.mgrid[:wh, :ww]
    if scene == "textured_dot":
        circle = (xx-(margin+width//2))**2 + (yy-(margin+height//2))**2 < (min(width, height)*.24)**2
        world = np.where(circle, world, 0).astype(np.uint8)
    elif scene == "sparse":
        im = Image.new("L", (ww, wh))
        dr = ImageDraw.Draw(im)
        for _ in range(max(40, width*height//2000)):
            x, y = int(rng.integers(0, ww)), int(rng.integers(0, wh))
            r = int(rng.integers(2, 7))
            dr.rectangle((x-r, y-r, x+r, y+r), fill=int(rng.integers(90, 255)))
        world = np.asarray(im).copy()
    elif scene == "multi_object":
        keep = np.zeros((wh, ww), bool)
        for fx, fy in ((.18,.18),(.65,.2),(.2,.7),(.7,.65)):
            x, y = margin+int(width*fx), margin+int(height*fy)
            keep[y:y+max(8,height//5), x:x+max(8,width//5)] = True
        world = np.where(keep, world, 0).astype(np.uint8)
    elif scene == "repetitive":
        checker = (((xx//12 + yy//12) % 2) * 200 + 20)
        world = np.clip(.78*checker + .22*world, 0, 255).astype(np.uint8)
    elif scene == "flat":
        world[:] = 128
    a = _crop_shift(world, height, width, margin, 0, 0)
    b = _crop_shift(world, height, width, margin, float(dx), float(dy))
    ma, mb = np.ones_like(a, bool), np.ones_like(b, bool)
    if scene == "brightness":
        b = np.rint(b.astype(float)*.73+34).clip(0,255).astype(np.uint8)
    elif scene == "noise_blur":
        b = np.asarray(Image.fromarray(b).filter(ImageFilter.GaussianBlur(.8))).astype(float)
        b = np.rint(b+rng.normal(0,8,b.shape)).clip(0,255).astype(np.uint8)
    elif scene in ("occlusion", "independent_motion"):
        ph, pw = max(8,height//3), max(8,width//3)
        x0, y0 = width//3, height//3
        patch = _texture(ph, pw, rng)
        b[y0:y0+ph,x0:x0+pw] = patch
        if scene == "independent_motion":
            x1, y1 = max(0,x0-9), max(0,y0+5)
            a[y1:y1+ph,x1:x1+pw] = patch
        # Unknown occlusion is deliberately NOT supplied as an oracle mask.
    elif scene in ("ui_unmasked", "ui_masked"):
        for x, y, r in ((width//2,height//2,max(4,width//28)),
                        (width//6,height//5,max(4,width//30)),
                        (width*4//5,height*3//4,max(4,width//24))):
            box = (slice(max(0,y-r),min(height,y+r+1)),slice(max(0,x-r),min(width,x+r+1)))
            icon = ((np.indices(a[box].shape).sum(axis=0)%3)*110+20).astype(np.uint8)
            a[box] = b[box] = icon
            if scene == "ui_masked":
                ma[box] = mb[box] = False
        # Only predefined, visible UI geometry is supplied; never GT occlusion.
    p = Pair(f"{scene}_{seed}",scene,a,b,ma,mb,None if scene=="flat" else (float(dx),float(dy)),scene!="flat")
    p.validate()
    return p


def load_manifest(path: str | Path) -> list[Pair]:
    path = Path(path).resolve()
    obj = json.loads(path.read_text(encoding="utf-8"))
    entries = obj["pairs"]
    pairs: list[Pair] = []
    for item in entries:
        def load(key: str) -> np.ndarray:
            with Image.open(path.parent / item[key]) as im:
                return np.asarray(im.convert("L")).copy()
        a, b = load("previous"), load("current")
        ma = load("mask_previous") > 0 if item.get("mask_previous") else np.ones_like(a, bool)
        mb = load("mask_current") > 0 if item.get("mask_current") else np.ones_like(b, bool)
        gt = item.get("displacement_xy")
        p = Pair(str(item["id"]),str(item.get("scene","real")),a,b,ma,mb,
                 tuple(map(float,gt)) if gt is not None else None,
                 bool(item.get("observable",True)),"manifest")
        p.validate()
        pairs.append(p)
    if not pairs or len({p.name for p in pairs}) != len(pairs):
        raise ValueError("Manifest must contain pairs with unique IDs")
    return pairs


def dataset(config: dict, width: int, height: int) -> list[Pair]:
    if config.get("manifest"):
        return [p for p in load_manifest(config["manifest"]) if p.a.shape == (height,width)]
    return [make_pair(s,width,height,int(seed),int(config["max_shift"]))
            for s in config["scenes"] for seed in config["seeds"]]
