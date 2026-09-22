# OFA workspace context

FACT: user requested an OFA branch in GitrnHub/AI-Bridge and a GPU displacement comparison using previously uploaded OFA.zip.
FACT: the original native Windows OFA V4 source and tester/log were inspected; provenance is in docs/REFERENCE.md.
DECISION: work directly on OFA, keep main unchanged, use Git-native source and the repository's exchange protocol.
DECISION: global translation previous->current, +x right/+y down, image pixels. Ground truth is external to backend inputs. Synthetic pairs disable temporal hints. Retain raw reference code unchanged.
DECISION: compare three OFA variants, FFT phase, masked ZNCC, translation-only pyramidal LK, RAFT Small/Large and optional CUDA Farneback. No silent CPU fallback. Resource fields have explicit scope and unavailable values.
ASSUMPTION: Codex can access a native Windows machine with the user's NVIDIA GPU. Reference history mentions RTX5070; current hardware/environment must be detected, not assumed.
FACT: author runtime has no CUDA GPU; only CPU math/process/report validation is possible here. GPU FPS/accuracy/utilization are not yet established.
