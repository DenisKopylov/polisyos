# R1361 — independent R1289-r5 profiled-resume delta review

**Disposition: GO for root materialization and the focused native review. Runtime acceptance remains UNRUN; this is not closure.** R5 repairs the concrete R1353 blocker without changing production behavior or weakening the resume-owner checks.

## Bound source and candidate

- Current source base: `HEAD 5dbe52f869cb259871bb9df4d84be60b2f3310c2`, tree `75c35b2cf401fd0db1ec7dfe7886ea633cbd8459`.
- Source frame: `root-author-source-frame-r1360-20261014.json` @ `943a69894d574a0c26fbe7f60d5cbf3e4fbbc74b6c6b1673e4fb378476c0ed61`.
- R5 patch: `raw/r1289-prepared-b-run-lifecycle-resume-composed-successor-r5-20261014/proposal.patch` @ `b900b3fd5273610e3f6edc73ba44d71c39c0782030c05b8514761ed522effca8`.
- Manifest @ `91e72a625f9840ce026da03879de5863569f83b1a20a0c041ddd6df14f72ac72`; decision @ `829e7f3475228c99982b8fc7f014e775eeb29b4fdaafc95607d1b9510ac0a1ef`.

I reconstructed the six patch postimages in memory from their exact current source preimages. All six preimages matched the R5 manifest, all six reconstructed postimage SHA-256 values matched, and all six Python files parsed with `ast.parse`. No product source or test file was written, and no pytest, product import, CAS/DB operation, spawn replay, or `git apply --check` was run.

| Candidate path | Current preimage SHA-256 | R5 postimage SHA-256 |
| --- | --- | --- |
| `tests/_helpers/process_run_lifecycle.py` (new) | absent | `fbbcdf853f23a0d8103bc28c13a7b9a9b303580e829da1da113693552d62b58a` |
| `tests/_helpers/run_lifecycle.py` (new) | absent | `d97cdbd4f78f7e3db3aaa3ff41c96a62027afa7297719c1c18dd36e12d9b03bf` |
| `tests/integration/scientist/orchestration/engine/test_skg_prepared_read_cache.py` | `64114b3b330a9fe9f78033de92fa97b1003d787c87f2907a8774001d904a6ec8` | `f12c651390ff99c6ea65f6e8b8bbffbc9f395b1ba4704afa60e7014e9c4b39c2` |
| `tests/unit/scientist/orchestration/engine/test_async_cache_recovery.py` | `3bf81925e005c386889c6df80f48f5319fd741cd95ea0a65bacdd19a5de820ee` | `442cabf574bfe46cb64e5f082b9f131c0a3e1a2ea888b697c135df2e68a6857b` |
| `tests/unit/scientist/orchestration/engine/test_engine_executor_idempotency.py` | `9f87c306b83b8b9e397685e05aedde96291e35b2a846dd5f4161ec94aadc4703` | `ac51ff9d86bb3d14a89ecdc8eccd562ff163f0853ec2457f6a1c6ed69edf9737` |
| `tests/unit/scientist/orchestration/engine/test_native_state_cache_semantics.py` | `3278cd12581863fc133b746b68227ad94e694a18513fba5b2ed17dd25d9571b2` | `1bd4c99f068deea0e4106e990800feaedfa080f1079dbe075296aef3294d0f04` |

## R1353 resolution

The prior independent review (`r1353-lifecycle-presence-shared-run-independent-review-20261014.md` @ `b6c93f380595ed7a08342be5df2ef9b5fae2f3901883f3351d46791d67cfaa42`) blocked R4 because three new resumed native-cache fixtures used `build_default_registry_bundle(store)` and received the legacy profileless registry ref. `RunContext.resume` requires a selected registry profile in the persisted owner snapshot.

R5 differs from R4 in exactly one file and three call expressions. The async ArtifactRef replay, five-variant shared-run, and missing-to-null removal-control fixtures now call `build_default_registry_bundle(store, return_selected_profile=True)` and pass that exact `bundle_ref` to `RunContext.start`. The other five R4 postimages reconstruct byte-for-byte unchanged. The canonical builder’s selected branch calls `put_json(..., return_selected_profile=True)` and raises if the returned `manifest_profile_sha256` is missing. The resume source validates the stored registry ref against CAS, requires that profile, and exact-compares the supplied ref to the persisted `RunManifest.registry_bundle`.

Across the six packet files, the resumed routes use a selected-profile writer on initial or spawned receiver start, or load the exact prior manifest ref through `resume_same_run`; no reader materializes a profile, and no test self-labels a profile. The only profileless builder use in the scoped idempotency test is a standalone rollback fixture with no resume path.

The source-side refusal controls remain intact and were read-only inspected in `tests/unit/core/phase0/test_run_context.py` @ `d19d5909e89a737660b98d60446aea6afd43a51956b9af9887e757ff044a2d1c`:

- `test_run_owner_snapshot_refuses_missing_required_nullable_wire_fields` refuses missing required nullable fields and legacy owner encoding without changing the trace or adding a terminal event.
- `test_incomplete_resume_requires_the_exact_selected_owner_snapshot` includes a profileless registry owner and refuses resume without trace mutation or terminal events. The test uses a broad `run_resume_` match; the source identifies `run_resume_registry_profile_not_established` as the profile-specific reason.
- `test_incomplete_resume_rejects_changed_owner_inputs` supplies a well-shaped but forged replacement registry profile, asserts `run_resume_owner_inputs_mismatch`, and checks no trace mutation or terminal event.
- `test_start_requires_selected_profile_writer_before_creating_run_state` preserves refusal when the store cannot return the selected profile.

P40 remains `SAME_CLASS_DEEPER`: R5 closes the owner-profile prerequisite for the complete resumed-fixture quantity in this packet. Another profileless fixture in this same class is not a reason for per-site repair. This review does not claim any native runtime result or formal closure. The next check is the root-owned focused native command from R1353 after the full source freeze.

`closure_ids=[]`.
