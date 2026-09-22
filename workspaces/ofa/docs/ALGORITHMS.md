# Research / selection record (2026-09-22)

These are representative established algorithm families with GPU implementations, not an invented GitHub-star popularity ranking. Final suitability must be measured on the user's inputs and GPU.

| Family | Why included | Main trade-off |
|---|---|---|
| Phase correlation | FFT global translation without weights | Circular ambiguity, repeating textures, fixed overlays; no mask semantics in this baseline |
| Masked ZNCC | Directly relevant to minimap icons / known UI exclusions | Six padded linear correlations cost more memory/work; no learned invariance |
| Pyramidal Lucas-Kanade | Classical iterative image alignment | Local basin of convergence; translation-only model and photometric assumptions |
| RAFT Small/Large | Widely used learned dense optical flow, maintained torchvision entry point | Model/activation memory, distribution shift, iterative latency; global mode still needs reduction |
| CUDA Farneback | Traditional GPU dense flow via OpenCV contrib | Custom CUDA build and Python interoperability overhead |
| Original NVOFA | Dedicated optical-flow hardware baseline already used by the user | Driver/API/GPU capabilities, grid/cost/FB choices and CUDA postprocessing still matter |

## Primary sources

- NVIDIA NVOFA programming guide: https://docs.nvidia.com/video-technologies/optical-flow-sdk/nvofa-programming-guide/index.html
  Driver-exposed interfaces, flow units, hint handling, streams and CUDA pre/postprocessing. The SDK supports Windows/Linux; the user's preserved wrapper is Windows-only.
- NVIDIA hardware application note: https://docs.nvidia.com/video-technologies/optical-flow-sdk/nvofa-application-note/index.html
  Grid/cost capabilities are queried at runtime; do not infer support just from CUDA availability. Older tables are not used to certify a new GPU.
- Torchvision RAFT tutorial: https://docs.pytorch.org/vision/stable/auto_examples/others/plot_optical_flow.html
- Torchvision implementation/weights: https://github.com/pytorch/vision/blob/main/torchvision/models/optical_flow/raft.py
  Use explicit C_T_V2 (small) / C_T_SKHT_V2 (large), input normalization [-1,1], replicate padding to multiples of eight and minimum 128. No random weights and no resize-induced unit changes.
- RAFT original authors: https://github.com/princeton-vl/RAFT
- OpenCV CUDA optical-flow declarations: https://github.com/opencv/opencv_contrib/blob/4.x/modules/cudaoptflow/include/opencv2/cudaoptflow.hpp
  Includes CUDA PyrLK and Farneback. Our global LK implementation is not claimed to be this exact implementation.
- OpenCV Python packaging: https://github.com/opencv/opencv-python#installation-and-usage
  Standard wheels are CPU-only; custom CUDA/contrib builds are required for the optional backend.
- Mask-aware registration reference: https://scikit-image.org/docs/stable/auto_examples/registration/plot_masked_register_translation.html
  Masking is not equivalent to zeroing and applying ordinary phase correlation. This project implements displacement-specific overlap means/variances in Torch.
- PyTorch version pairs: https://pytorch.org/get-started/previous-versions/
- NVML utilization semantics: https://docs.nvidia.com/deploy/nvml-api/api/structnvmlUtilization__t.html

Implementations of the classical Torch algorithms here are project code, not copied performance claims from those libraries. External FPS numbers are deliberately not mixed with this benchmark. Weights are downloaded only by explicit action, kept out of Git and identified by checksum. Dependency/model licenses remain those of their authors.
