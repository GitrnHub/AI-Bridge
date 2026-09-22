# OFA / GPU image-displacement benchmark

Compare **global frame-to-frame translation** on the same decoded grayscale inputs. This is not large-world-map localization, image retrieval, dense-flow ground-truth evaluation, or video-decoder throughput.

**Status: implementation + CPU validation; target Windows/NVIDIA GPU validation pending.**
The original `OFA.zip` V4 source is retained unchanged at `vendor/ofa_v4.py`. New inputs, masks, timing boundaries, failure handling and telemetry are shared across comparisons. No CPU fallback is disguised as GPU execution.

## Start here

Recommended new environment: **native Windows 11, Python 3.12 x64**, and an NVIDIA GPU/driver supporting both the selected CUDA runtime and NVOF API. Python 3.12 is a recommendation, not an assertion that every other version fails.

```powershell
# Run from the repository's workspaces/ofa directory.
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements.txt
python doctor.py --out doctor.json
python -m pytest -q
python download_weights.py
python benchmark.py --config configs/quick.json --strict
```

The pinned Torch/vision CUDA 12.8 pair is a **reproducible proposed baseline**, not a claim to be the latest release. It is listed in the official PyTorch previous-versions instructions. Keep an already-working OFA environment intact; test this environment separately. Do not upgrade or downgrade the display driver automatically. Local author validation used Python 3.13.5 / Torch 2.10.0+cpu, not this Windows recipe.

Native OFA uses driver `nvofapi64.dll` + `nvcuda.dll`; fused postprocessing additionally needs an NVRTC DLL supporting the GPU compute capability. The original loader searches CUDA_PATH/bin, Torch library directories and PATH. If unavailable, report the actual error; do not quietly replace the CUDA reducer. `ofa_post: "torch"` is an explicit, separately labeled ablation. There is **no TensorRT, ONNX Runtime, LightGlue or cuda-python requirement** for this project.

## Compared implementations

| Name | Implementation | Role |
|---|---|---|
| `ofa_v4` | Original native OFA, bidirectional + cost/FB + fused CUDA reducer | Primary historical-code baseline |
| `ofa_v4_forward` | Original native OFA, forward only + original reducer | Bidirectionality cost/quality ablation |
| `ofa_common` | Native OFA forward only + common Torch motion-mode reducer | Postprocessor ablation |
| `phase` | Torch FFT normalized phase correlation + subpixel peak | Lightweight global translation; deliberately ignores masks |
| `masked_zncc` | GPU FFT, six linear correlations with overlap-specific means/variances | Genuine known-mask-aware translation |
| `pyr_lk` | Robust, pyramidal, two-parameter Lucas-Kanade in Torch | Iterative global translation, no model weights |
| `raft_small` / `raft_large` | Official torchvision pretrained RAFT + common reducer | Learned dense-flow alternatives |
| `opencv_farneback` | Optional custom CUDA OpenCV/contrib build + common reducer | Traditional dense-flow alternative |

The LK implementation is translation-only, not OpenCV sparse PyrLK. Farneback's Python integration downloads flow then uploads for the shared reducer: **both transfers are timed**. It must not be described as zero-copy. Standard pip OpenCV wheels are CPU-only; Farneback is optional until a custom CUDA build is validated.

## Runs and output

```powershell
python benchmark.py --config configs/quick.json --strict
python download_weights.py --large
python benchmark.py --config configs/full.json
python benchmark.py --config configs/load_40.json --strict
python export_inputs.py --config configs/quick.json
python benchmark.py --config configs/cpu_smoke.json
```

Quick: 256x256 and 640x480, 14 scenario families, four seeds. Full: adds 1280x720, twelve seeds and all nine backends. Load: forty staggered synthetic clients at 1 request/s each, one FIFO worker. It does not connect to forty physical devices.

`results/<UTC run>/` contains offline `report.html`, `report.md`, `summary.csv`, `predictions.csv`, merged `results.json`, exact `run_config.json`, and per-backend environment/parameters/errors/telemetry samples. CSV is UTF-8 with BOM. Missing information is N/A/null, never a manufactured zero.

`--only phase,masked_zncc` restricts backends. `--strict` makes every selected backend mandatory. Otherwise missing optional RAFT/Farneback dependencies are explicit UNAVAILABLE rows; required OFA/math backends still make the command fail. Each backend/resolution runs in an isolated subprocess. OOM, timeout and native crashes do not erase other results. Existing nonempty output directories are rejected.

See [measurement definitions](docs/METHODOLOGY.md), [research and selection](docs/ALGORITHMS.md), [reference provenance](docs/REFERENCE.md) and **[Codex handoff](CODEX_HANDOFF.md)**. The active exchange is in `.bridge/state.yaml`.
