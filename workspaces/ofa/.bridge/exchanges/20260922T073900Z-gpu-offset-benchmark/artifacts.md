# Artifacts

Original user input: OFA.zip, 1,592,249 bytes; SHA256 d4b1843c78767f42d607fdb7169b444b95658ca0e5508a5f61bcda88d0962f0c. Retrieved from user Library. Source subset ofa.py is versioned at vendor/ofa_v4.py unchanged; checksum and provenance in docs/REFERENCE.md. Original ZIP is not duplicated as source of truth.

Authored source/config/docs/tests: normal Git files, tied to implementation commit and source blob manifest.

RAFT weights: not committed. Explicit downloader uses official torchvision URLs; each benchmark records checkpoint SHA256. Location is target Torch hub checkpoints cache; Codex must record actual size/hash and tested commit in returned artifact evidence.

Run outputs: results/<UTC>/ (ignored), including report.html, report.md, summary.csv, predictions.csv, merged/per-worker JSON, worker.log and telemetry samples. Small evidence may be committed; large exports should use permitted external/Release/Actions artifact storage. Record location, size, SHA256, source commit, producer, purpose and retention. No target-GPU run artifacts exist at authoring time.
