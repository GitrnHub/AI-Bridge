# Original OFA.zip provenance

FACT: retrieved the user-provided Library item named OFA.zip (1,592,249 bytes).
Archive SHA256: `d4b1843c78767f42d607fdb7169b444b95658ca0e5508a5f61bcda88d0962f0c`.

Archive contents reviewed: `OFA/ofa.py`, `OFA/tester.py`, `OFA/ofalog.txt`, and seven preview image pairs. Original scenario families included textured_dot, natural_texture, sparse_features, multi_object, occlusion, subpixel and repetitive_stress.

`vendor/ofa_v4.py` is an unchanged byte-for-byte copy of `OFA/ofa.py`:
- bytes: 72,889
- SHA256: `218dd1f1c40cd82d01fcfb3ef6f9ab6b98f4aaef4951c3112566191f777c2674`

The archived log reports Windows 11 / RTX 5070 / compute capability 12.0 / Python 3.12.13 / torch 2.13.0.dev20260609+cu132 / driver 610.47, timestamp 2026-07-15 23:30:23. These are **historical log statements, not independently reproduced facts about the target machine today**. Original FPS lines are not imported into the new comparison. Personal filesystem paths and bulk PNG previews are not committed. Original tester.py is inspected reference material, not the new benchmark runner.

The original source uses native Windows ctypes, driver NVOF C API 5.0, Torch-shared CUDA context, ring buffers, separate input/output streams, S10.5 SHORT2 vectors, UINT8 costs and a bidirectional option. The fused offset estimator uses NVRTC CUDA kernels with a Torch fallback in its original implementation. The new adapter passes an explicit backend and prohibits automatic fallback.

DECISION: retain the original source untouched, wrap it, and regenerate expanded deterministic fixtures. Compare original bidirectional postprocessing, forward-only original postprocessing, and a shared flow reducer as separate variants. Source displacement is raw_flow / 32; **grid spacing is not a multiplier for vector magnitude**. Native OFA sessions are closed in worker cleanup.

Rights/provenance: this is user-supplied source, with its original notices retained. No new third-party license is asserted for it. No NVIDIA driver/SDK binaries, model checkpoints or unrelated private files are redistributed. Git source files, not a duplicated source ZIP, are the source of truth for this handoff.
