# Request

Sender: user; implementation/handoff preparation: Web GPT. Receiver for real-machine verification: Codex.

## Goal
Create branch OFA, research/select GPU image-displacement algorithms and implement a reproducible comparison against hardware OFA using the user's prior OFA.zip. Include accuracy, FPS, performance occupancy/resource metrics, Python/dependencies and a self-contained Codex handoff.

## Current facts / decisions / assumptions
See ../../context.md and docs/REFERENCE.md. Source baseline is the main branch from which OFA was created; implementation and final handoff commit IDs are recorded when published. Historical log values are not new measurements. User branch name overrides the standard bridge/... pattern.

## Required changes and contracts
Python test project in workspaces/ofa, preserved original OFA source, deterministic known-GT and real-manifest inputs, shared direction/units, isolated subprocesses, synchronized latency, sustained full-pipeline FPS, CPU/NVML/Torch telemetry, explicit unavailable/error states, report generation and verification instructions. No hidden fallback or GT leakage.

## Constraints and acceptance
Keep main unchanged. No source ZIP as primary handoff, no weights/drivers/private paths committed. Code completion is not hardware verification. Execute the acceptance plan in CODEX_HANDOFF.md; raw predictions, hashes and environment must permit reproduction. Do not compare raw flow FPS to end-to-end displacement latency.

## Test plan / out of scope
CPU mathematical regression + subprocess/report smoke first, then Codex native GPU quick/full/repeat/40-client runs. Global relocalization, rotation/scale, direct OFA engine occupancy and live forty-device capture are out of scope. Real images with unknown truth must not receive accuracy labels.

## Relevant files/artifacts
README.md, CODEX_HANDOFF.md, docs/*, vendor/ofa_v4.py, benchmark.py, ofabench/*, tests/*, configs/*.json. Original ZIP checksum and source checksum in REFERENCE.md; source is directly versioned. Report artifacts follow root bridge/ARTIFACTS.md.
