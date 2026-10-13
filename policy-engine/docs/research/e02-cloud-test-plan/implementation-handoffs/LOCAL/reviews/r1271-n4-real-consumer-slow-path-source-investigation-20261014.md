# R1271 — N4 real-consumer slow-path investigation

Result: the available evidence identifies a missing diagnostic signal, not a proven slow-code root cause. No product or test source was changed and no test/profiler was run while the native slot was active.

## Source and run boundary

The read-only source entry is branch `codex/e02-unified-local-20261009`, HEAD `a746e1b0b1fab1b9ae027c1c4b55eea67f95e02d`, tree `1355896e91789026d21396d2b087c63827ab251b`. Its source frame is `LOCAL/root-author-source-frame-r1267-20261014.json@a5403a64bcbac9d3a3038396d828bc018fcd96f348060f2150e38a89f7405803`.

The reported in-flight node is `tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py::test_actual_n5_writer_removal_keeps_refs_and_fresh_get_limits`. At assignment time, root reported setup passing, this first test still running after five minutes, and no later cases started. The complete pytest stdout/stderr and exact launch command were not included in this investigation input, so there is no pytest result to assert.

## The real path under test

The test uses the unchanged pinned `original_second_capture` (`gy_n4_replay_20260704_095710_425807_7bf5552df372`, content hash `sha256:107f896fb1fd1c37170b74c88726c07169277d05d3ec5459ceb360919e692cb1`) and requests two children. `prepare_generic_n4_served_replay` loads the recordings, builds a selected local SKG source and candidate profiles, runs the actual `N4GenerationPort`, derives and binds the two semantic children, and materializes a root plus two child profiles. The served portion creates the app, posts `/api/v1/control/runs/nl`, dispatches the actual control worker, lets the first child execute, injects the expected second-child failure, removes N5 result bytes at `ArtifactStore.put_json` while retaining the returned ref, then performs a fresh `/api/v1/runs/{run_id}` GET and resolves the missing ref. The expected result preserves the child-profile binding and partial failed-sibling checkpoint while the reader refuses to project a successful N5 observation.

The current test does **not** inject its module's existing `served_worker_phase_probe` fixture. Consequently it calls `prepare_generic_n4_served_replay` and `run_n4_control_worker_and_get` without their optional `phase_callback`; their existing phase events do not run for this case. Adjacent served-consumer tests do pass that fixture. The fixture at line 44 of the test module already writes payload-free stage timing and recurring all-thread Python tracebacks via `faulthandler.dump_traceback_later(30, repeat=True)`.

## Evidence and bounded hypotheses

The retained macOS `sample` report is `LOCAL/raw/r1268-active-first-n4-stack-sample-20261014.txt@26f643e04e2fb54b467266b70d802f18250625343085a3b5fa532498da4231d0`. It sampled Python 3.14 process 35633 at 00:22:47 +0300, about 2m44s after its 00:20:03 launch. The report shows 677 main-thread samples, 227 in CPython's `isinstance` dispatch and 156 in `object_recursive_isinstance`, including ABC instance checks; it also has list extension and dictionary iteration frames. It is a native sample without Python callable names or a test phase marker. Root's supplied status was CPU-active (103→395%), RSS 3.8→4.2 GB, process physical footprint 9.4 GB / 10.6 GB peak, and 43% free memory. This is not evidence of OOM, deadlock, or a particular Python function.

The selected local replay JSON is 1,009,265 bytes with two recordings. The selected capture itself has 10 responses, 154 dictionaries, 69 lists, maximum nested depth 9, 859 keys, and 133,913 bytes of string values. Its raw response bodies are small (largest observed 7,002 bytes). This makes the replay fixture alone an unconvincing explanation for multi-gigabyte growth; it does not bound the expanded typed runtime/profile objects.

There is measurable repeated test-helper work worth timing before changing anything:

- `_load_recordings` parses the whole two-recording file and validates every row; `controlled_candidate_gateway.set_fixture` validates the selected recording again.
- `_seed_controlled_selected_skg_source` captures the local DB identity once. After seeding, the helper performs eight `_validate_controlled_skg_source` observations: once before setup, three times per each of two child profiles (before, inside `_materialize_controlled_world_model_record`, and after), and once after the root profile is rehashed. Each observation hashes the DB before and after, reads its DuckDB schema/version through a read-only connection, and resolves the version through `SKGQuery`. These checks bind the chosen source and cannot be dropped merely to shorten the test.
- Candidate code paths matching the native sample's type-check/ABC shape include the recursive frozen context serializer (`cycle_substrate.py::_serialize_context_job_v1_value` / `_serialize_context_job_v2_value`) used by the design-problem and two child-selection hashes, and the recursive typed comparator in `generic_simulation_admission.py::_same_typed_public_value`. Source shape alone does not establish either as the hot frame.
- The actual `N4GenerationPort`, control-worker dispatch, N5 producer, CAS removal, and fresh GET remain additional possible phases; the current stack cannot distinguish them from profile preparation.

P40 classification: **NEW diagnostic class — slow real-consumer N4/N5 test path**. The symptom occurs in a test invocation whose preparation is test-helper-owned; whether the slow call is confined to this fixture or exposes a systemic shared-runtime path is **not_established**. Shared serializer code is a candidate, not a finding. The available `sample` tool does not provide Python frames; the RemoteUnwinder/taskport attempt was denied and `py-spy` is unavailable. The existing built-in `faulthandler` fixture is the supported discriminating route.

P38 boundary: the property is the complete POST→actual worker/N4→N5 writer-removal→fresh GET behavior above. Elapsed time, CPU, and a native stack are diagnostic signals only. With no completed test output, there is no behavioral PASS/FAIL result and no closure proposal.

## Smallest next check

After the active native run ends, instrument only this test invocation using its existing fixture. Add `served_worker_phase_probe` to this test's fixture parameters; mark fixture preparation start/end and app/TestClient start/ready/shutdown as the neighboring tests do; pass `phase_callback=served_worker_phase_probe` into both helper calls. Run only the same node, unchanged original capture, two children, real writer removal, real dispatch, and fresh GET. Retain complete stdout/stderr, phase JSONL, recurring Python stack file, elapsed time, and peak memory for that one source-bound run. The root's 600-second native budget is the current reported cap; do not shorten the test's meaningful path or turn a timeout into success.

The phase timestamps first locate preparation versus dispatch/GET. The first recurring Python traceback then identifies the callable and owner. If the stack stays in test-helper source preparation, consider consolidating only demonstrated duplicate helper work while preserving exact selected-source identity checkpoints and all real-consumer assertions. If it lands in shared runtime serialization/admission, profile the complete typed value shape and repair that generic mechanism with same-input positive and malformed/removal controls. Until then no code optimization is evidence-backed.

`closure_ids`: `[]`. All runtime/native results remain UNRUN for this investigation; the reported in-flight test has no deciding output here.

## Read-only source pointers

- `policy-engine/tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py@97008f45343b85d2b0fa69cf169929497efb9425c362322a76cae02905ae3068`
- `policy-engine/tests/_helpers/generic_n4_served_replay.py@5ece2481d903e49d2f5a1a3af6582ea76c7ab53d39f2209fbd3dced8ce4013f9`
- `policy-engine/tests/_helpers/controlled_candidate_profile.py@ac3f7ca166f186d2d0347c435da974c6bea734ee49d6bde7f9091efe8c778551`
- `policy-engine/tests/_helpers/control_worker.py@060132f88dc11d72dab9215f2d8245339e013716907fe18da11616d6b097b269`
- `policy-engine/tools/quality/validation/check_layer3_gy_design_generation_contract.py@4f0c280dd84072b7c7573787538e2f63c699f8cc2862b198571e3d4c73090da0`
- `policy-engine/architecture/policy_design_case/layer3_gy_design_generation_replay_recordings.json@db5f892c19412e74ff78683901dd81e49ebb446f75eb394d254cc75d7c74ae71`
- `policy-engine/src/polisyos/runtime/quality/cycle_substrate.py@a567d96c6845c905f3cdeb5f517a2b0c113867ae9d46b981c387b4143c6bc0e2`
- `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@e5bfe3f6a9cabcd62fad36669f8ff6cb2068f30da34ae7d6c9562257f6e84c4a`
- `policy-engine/src/polisyos/runtime/quality/generic_simulation_admission.py@1d5d8a1f61cbb417c1ef4850bad6af4ee86cb54dd2bc2d6be983d80ab79458eb`
- `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py@195e9e5986ef651eb2729e695053eb9b3664dbd274dd8194519a30431c7e1237`
