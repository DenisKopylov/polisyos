# Lesson partial-answer evidence transport

The current `source-inputs.json.gz` supersedes source packaging only. It contains 14 identity-only references to already tracked Git content (full commit SHA, repository path, Git blob ID, raw SHA-256 and byte count), plus the unchanged unique red untracked test body. Resolve a tracked member directly with `git show <source_sha>:<git_path>`; no tracked source body is embedded in this transport.

The original handoff, manifest and payload remain immutable historical evidence at commit `d61e97d1dbab91f0174ba5af8b01a488dc04ee61`. Resolve their original assertions and hashes against that pinned Git tree. The historical manifest's source-payload hash describes its original d61 payload; the corrected current transport is bound by `../lesson-partial-source-transport-correction.json`.

The correction changes neither product source/tests nor the original native 40-test positive and negative runtime evidence. Existing output and actual CAS fixture transports retain their original bytes. This is a packaging correction, not a new backend run or a new closure decision.
