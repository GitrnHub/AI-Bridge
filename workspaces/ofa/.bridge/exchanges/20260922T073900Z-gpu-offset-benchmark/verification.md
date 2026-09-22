# Verification

## Author attempt 1: CPU-only pre-publication checks

Environment: Linux; Python3.13.5; Torch2.10.0+cpu; torchvision0.25.0+cpu; CUDA unavailable. Full local environment is in evidence/local_validation.json.
Command: `python -m pytest -q`
Observed: 54 passed. Includes subprocess benchmark/report integration. This verifies the CPU math and harness only, **not target-GPU acceptance**. No claim of Windows API, NVRTC, RAFT pretrained inference, custom CUDA OpenCV or real GPU performance pass.
Implementation SHA is pinned in the final publication record; the Git blob manifest ties these tested bytes to the published tree.

## Codex attempt 1: pending

Tested commit: pending full SHA.
Environment / commands / acceptance items / measurements / evidence / issues: pending.
Conclusion: GPU verification pending; do not set workspace status to verified yet.
