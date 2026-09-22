# Codex handoff: target-GPU verification

Read root AGENTS.md / bridge protocol, `.bridge/state.yaml`, current exchange, README and docs/METHODOLOGY.md first. User explicitly selected branch **OFA**, overriding the repository's default bridge/... branch convention. Do not merge main without a subsequent acceptance decision.

## Mission

Run the same-version comparison on the user's **native Windows/NVIDIA GPU**. Reference history mentions RTX 5070, but detect and record the actual GPU/driver first. Do not assume the archived driver/nightly environment is still installed. Do not modify the user's working inference environment. Recommend an isolated Python 3.12 environment and the pinned Torch pair in README; report any installation/API/NVRTC incompatibility rather than silently substituting algorithms.

## Checkout and evidence binding

```powershell
git fetch origin OFA
git switch OFA
git rev-parse HEAD
git status --porcelain
cd workspaces/ofa
```

Record the full tested SHA in verification.md. If the branch advanced since the handoff, inspect the diff first. Keep a clean source tree for each measurement; generated results are ignored. Hash the preserved source and verify docs/REFERENCE.md. Save `python -m pip freeze`, `nvidia-smi` and doctor.json. Record display workload, other CUDA jobs, power settings and GPU temperature. Do not change drivers or terminate unrelated processes automatically.

## Commands / acceptance

```powershell
python doctor.py --out doctor.json
python -m pytest -q
python download_weights.py
python benchmark.py --config configs/quick.json --strict
python download_weights.py --large
python benchmark.py --config configs/full.json
python benchmark.py --config configs/load_40.json --strict
python export_inputs.py --config configs/quick.json
```

1. Unit tests must pass; math/sign/mask/no-fallback tests are necessary but not proof of GPU correctness. Current author evidence is CPU-only.
2. Quick strict must run original OFA + phase + masked ZNCC + LK + pretrained RAFT-Small. Any missing member is a failure of the **requested run**, not a zero-FPS successful measurement. Obtain a small native OFA pass before a long run.
3. Check clean-texture predictions for displacement sign, units and finite results. Initial **proposed sanity gate**, not an achieved result: at least 90% <=2px on clean texture for OFA, phase and masked ZNCC at 256/640. Do not force complex/flat/repetitive scenes to pass by changing labels. Record actual accuracy by scenario for all methods, including failures.
4. Same scene/seed/resolution input hashes must agree across backends. ui_masked/ui_unmasked must use identical images and GT. No GT-fed masks or initializing from OFA answers.
5. Report success<=0.5/1/2/3px, valid coverage, valid-only error mean/P95/RMSE, flat false acceptance, resident and host mean/P95 latency, sustained FPS, board power/GPU/memory busy, RSS and VRAM with availability caveats. No direct OFA occupancy claim.
6. Repeat important GPU runs at least three times, using separate output directories. Optional full Farneback requires a validated custom CUDA cv2. CPU-only cv2 must remain UNAVAILABLE. RAFT OOM is explicit; do not silently reduce resolution or change precision. A separate fp16 config can be tested and labeled.
7. Forty-client simulation must report offered/completed/unserved requests, response P95/P99, queue delay and deadline misses. This is synthetic one-FIFO service, not forty live captured streams. Resource telemetry describes sustained resident load, not this paced phase.
8. Inspect exported fixtures and evaluate real minimap frame pairs. Real GT absent => accuracy N/A. Never use the algorithm under test as its own ground truth. Rotation, zoom, minimap-to-world relocalization and multi-stream temporal history are separate work.

## Troubleshooting priorities

- CUDA false / missing GPU architecture: verify selected Torch wheel, GPU and driver; never run CPU and label GPU.
- DLL/API error: original wrapper is native Windows-only. CUDA availability alone is insufficient. Record exact traceback and NVOF API/capability outputs. WSL/Linux requires a separately reviewed port, not relabeling.
- NVRTC failure: capture DLL path, capability and full compilation log. CUDA_PATH is a CUDA Toolkit location; cuda-python is a Python package and is not a path setting. Do not install it as a supposed fix for this wrapper.
- Missing weights: run explicit downloader before timing. Preserve checkpoint checksums. No random-weight RAFT timing disguised as a pretrained model.
- NVML unavailable / WDDM process VRAM missing: retain N/A and raw error. Use UUID mapping, not assumed matching ordinals. No NVENC/NVDEC percentage substituted for OFA.
- Original OFA result buffers are reused; consume/copy before subsequent calls. Do not accidentally retain aliases while testing.

## Return to Web GPT

Append an attempt to `.bridge/exchanges/20260922T073900Z-gpu-offset-benchmark/verification.md` with tested SHA, exact commands, environment, PASS/FAIL per acceptance item, raw errors, representative failed input IDs/hashes, and reproduction frequency. Small summary JSON/CSV/log excerpts may be committed to evidence; big images/logs go to artifacts with path/URL, size and SHA256 under the repository policy. Update artifacts.md and state.yaml. On failure set `verification_failed`, next_actor `web-gpt`; do not claim `verified` from code review or CPU smoke tests. Keep a failure report sufficient without this chat.
