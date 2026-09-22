# Measurement contract

## Task and ground truth

Output is one `(dx, dy)` in original image pixels, **previous -> current**, positive right/down. Thus `B(x+dx,y+dy)=A(x,y)`. This is object/image-content displacement, not the inverse registration correction. It is not camera/world position without an application-specific sign transform.

Synthetic A and B are crops from a larger latent world, with bilinear fractional sampling. There are no artificial warp-border strips that reveal the answer. The expanded scenario set references the original OFA tests but is **not bit-identical replay** of tester.py. Same scene/seed/resolution produces the same frame and mask hashes in every worker.

Scenarios: texture, subpixel, textured_dot, sparse, multi_object, repetitive, large_shift, brightness, noise_blur, occlusion, ui_unmasked, ui_masked, independent_motion, flat. The two UI cases use exactly the same images/GT; only known static UI masks differ. Unknown occlusion masks are not supplied as oracle information. Independent-motion truth describes the background. Ground truth never enters Backend.prepare/predict. No backend is initialized from another algorithm's answer.

`max_shift` is the common declared search limit, not a per-pair oracle. Phase's circular ambiguity requires this limit to be less than half the smaller image dimension. It is enforced. Repetitive/low-texture and large-shift failures are legitimate results, not fixtures to delete. LK is local optimization and may converge to the wrong mode. The flat scene is intentionally unobservable and tests false acceptance rather than a fabricated zero-motion truth.

Real images: copy `configs/real_manifest.example.json`, set relative image/mask paths, configure matching `[width,height]` in a new run config, then use `--manifest <path>`. Unknown GT stays `null`; such pairs produce latency/coverage observations but **no accuracy score**. Ground truth should come from controlled displacement, verified annotations, or independent instrumentation, not OFA/RAFT agreement. RGB input is converted to L consistently before timing. Input decoding/capture is outside timing.

## Accuracy

Per-pair Euclidean endpoint error = sqrt((dx-dx_gt)^2+(dy-dy_gt)^2). This is the endpoint error of the single global translation, NOT dense-flow EPE. Success at <=0.5/1/2/3 px divides by **all labeled observable pairs**, including invalid results as failures. Valid-only mean/P95/RMSE must be read together with coverage. Unlabeled observations and explicitly unobservable negatives have separate counts. No post-hoc removal of difficult scenes. Compare per-scene results, not just aggregate averages.

Confidence fields are backend-specific: correlation peak, support, mode-inlier ratio or original OFA confidence. They are **not calibrated probabilities and not mutually comparable**. Acceptance policies are explicit in source, not tuned to test labels. A full ROC/threshold-calibration experiment is not included. Keep separate calibration and holdout seeds if changing thresholds; the benchmark itself does not train models.

## Timing boundaries

| Field | Starts | Ends | Includes / excludes |
|---|---|---|---|
| initialize_ms | Backend constructor | Ready session/model | DLL/model load and session creation; explicit weight download can occur here |
| prepare_all_ms | CPU arrays | All resident inputs ready | Uploads/masks; OFA mask estimators and first NVRTC compilation |
| first_call_ms | First prepared pair | CPU dx/dy | Separate cold operator execution; not a warmed result |
| resident.wall_ms | Resident uint8 images/masks | CPU dx/dy and synchronized work | Conversion, algorithm, reduction, compact D2H; no source upload |
| host_to_offset.wall_ms | Decoded CPU arrays | CPU dx/dy and synchronized work | Preparation, uploads, masks/estimator construction, algorithm, reduction, D2H |
| throughput.fps | Resident repeated complete offset pipeline | Synchronized chunk end | Complete algorithm/reducer, sync per chunk; last output copy after timing |

Latency reports mean/P50/P95/P99 and `1000 / mean_ms`; sustained throughput is a separate quantity, not the same latency boundary. CUDA event time covers the dependency graph including OFA stream joins; it is not pure OFA execution or SM busy time. OpenCV cross-runtime event timing is omitted. Warmup results and initialization are excluded from steady-state timings. The throughput loop executes varied deterministic inputs, not one endlessly cached tensor. Temporal hints are disabled for every independent OFA pair. No RAW-flow-only FPS is placed alongside end-to-end offset FPS.

The reference OFA estimator precomputes a mask; resident tests reuse it, while host-to-offset constructs it for each request. This deliberately exposes the difference between a cached ROI deployment and a dynamic per-request deployment. RAFT preprocessing remains inside both prediction paths. Prepared inputs for the complete dataset stay resident; memory includes this input cache. Change seed count only with this memory effect in mind.

## Resource measurements

Resource samples cover the **sustained resident window**, not the separately timed host-latency or paced-load windows. The load report measures queue/service/response latency and deadline misses; it does not claim separate paced-load power measurements.

Process CPU = process user+system CPU time / elapsed time; 100% is one logical core. A normalized-machine percentage is also available. Process RSS is sampled. NVML reports board kernel-busy time, board memory-interface-busy time, used VRAM, power, temperature and clock. GPU identity maps from Torch UUID to NVML UUID, not blindly from CUDA ordinal. An explicit `nvml_index` override requires manually verifying the UUID.

NVML **GPU% is not OFA occupancy**, Tensor Core utilization, SM occupancy, or the fraction of total arithmetic capacity used. Memory% is busy-time fraction, not achieved GB/s or percentage of peak bandwidth. The hardware sample window can be 1/6 to 1 second; polling every 100 ms can repeat values. Use several-second runs. Missing fields, including WDDM process memory restrictions, remain null. No encoder/decoder utilization is substituted for OFA. `ofa_engine_occupancy_pct` is explicitly null.

Torch allocated/reserved peaks exclude allocations made directly by OFA/OpenCV and are not total process VRAM. NVML per-process memory is sampled where supported; board memory includes all applications. The reported peak covers the measured phases after warmup, not the maximum of model loading. Other GPU workloads and the desktop contaminate board utilization/power. Sampled board power divided by resident throughput is only an energy-per-pair estimate; subtracting idle is a rough delta, not isolated OFA power. Monitoring overhead is included and not subtracted.

## Validity and repeatability

Run each important configuration at least three times into fresh directories, record thermal state and other GPU work, compare medians across runs. Default backend order is deterministic, not randomized; repeat with reversed order to investigate thermal-order effects. No outliers are discarded automatically. Full results include parameters, model checkpoint SHA256, platform, Torch/CUDA/driver/GPU UUID, git SHA/dirty status, input hashes and raw samples. CPU test runs are flagged `is_gpu_benchmark=false`.

This project does not claim rotation/scale invariance, global world-map relocalization, a production scheduler, true simultaneous forty-device capture, or direct OFA engine occupancy. Those require separate experiments rather than inferred scores.
