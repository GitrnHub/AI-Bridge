# Web GPT implementation response

Source request: request.md. Status: ready for Codex target-machine verification, not verified.

Implemented: unchanged OFA V4 adapter and forward/common-reducer ablations; phase, masked ZNCC and translation-only pyramidal LK; explicit pretrained torchvision RAFT Small/Large; optional CUDA OpenCV Farneback; deterministic synthetic/real-manifest data; isolated worker runner; two synchronized request-latency boundaries, sustained throughput, optional forty-client FIFO simulation; CPU/RSS/NVML/Torch telemetry; raw JSON/CSV plus offline HTML/Markdown; environment/weights/input provenance and documentation.

Design deviations: source fixtures are an expanded deterministic suite, not byte-identical replay of original tester.py. Original log is provenance, not benchmark output. Farneback uses explicitly timed flow D2H/H2D interoperability. Global LK is a project implementation, not the OpenCV sparse tracking API. Hardware-only OFA occupancy is not available and remains null.

Checks actually run: 54 pytest cases passed on Python3.13.5 / Torch2.10.0+cpu; includes direct masked-ZNCC-vs-spatial-formula checks, direction/subpixel/flat/UI/grid-unit checks, input determinism, invalid-score denominators, missing GPU rejection, config validation and three-worker CPU report generation. The final publication record pins the implementation SHA and validation evidence.

Not verified: native Windows/NVOF DLL/API/NVRTC execution, any GPU backend runtime/performance, pretrained RAFT inference, custom CUDA cv2, NVML driver fields, proposed Python3.12 Windows installation recipe. No GPU scores are fabricated.

Risks: native wrapper platform limits, API/grid/driver capabilities, NVRTC GPU support, optional weight/network availability, RAFT high-resolution memory, known-mask-policy differences, telemetry sampling and desktop contamination. Commands and precise acceptance rules are in CODEX_HANDOFF.md.
