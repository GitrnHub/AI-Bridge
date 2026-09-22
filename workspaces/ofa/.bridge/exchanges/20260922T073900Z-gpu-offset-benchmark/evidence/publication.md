# Publication / validation binding

Implementation commit: `45862657fa96feb68c712f12be3165e8eeeab16a`.
Implementation tree: `3a6853364b7579862cc2f81600d0cc1e13a4c0a5`.
Parent accepted-protocol baseline: `5c83157d385f82d1e64341f4e27db3acb9b9efaf`.
Branch: `OFA`. No merge into main is authorized or performed by this handoff.

The following evidence-only commit records this implementation SHA without changing Python source. Codex may test the branch handoff tip, but must record its actual full tested SHA, inspect any later differences and not replace the ID with "latest".

## Checks actually performed

- Local `python -m pytest -q`: **54 passed in 11.28s** on Linux / Python 3.13.5 / Torch 2.10.0+cpu / torchvision 0.25.0+cpu. CUDA unavailable.
- Separate `python benchmark.py --config configs/cpu_smoke.json --out <fresh-output-directory>` completed three isolated CPU workers and generated HTML/Markdown/CSV/JSON reports.
- Exported eight CPU-smoke pairs and successfully read their manifest. Source syntax compilation passed.
- Git blob IDs for all 15 Python files match local tested source. The complete ofabench, tests, vendor and docs tree objects were independently reconstructed from local bytes and match the uploaded Git tree IDs.
- Original source SHA256 matches the supplied OFA.zip member. `.gitattributes` preserves LF on Windows so checkout does not change that checksum.

See `source_blobs.json` for exact Python Git blob IDs and `local_validation.json` for the environment summary. Config JSON whitespace may differ from the local authoring layout; parsed configuration values are unchanged. These are pre-publication CPU checks bound by source identity, not a claim that the native target machine checked out and ran this commit.

## Unverified

Windows environment installation; NVOF API/DLL/NVRTC; all GPU latency/FPS/accuracy/resource figures; pretrained RAFT inference; CUDA-enabled OpenCV; NVML driver measurements. The target-GPU acceptance attempt remains pending. No CPU timing or historical OFA log is presented as a current GPU benchmark.
