# R1 ArtifactID removal oracle

Verification-only receipt; complete deciding logs are tracked in `verification-baseline-logs/`. No product source or test files were changed.

Base: `c40d4acae1ce58b597267255026d9356565828fd`, branch `codex/e02-A-custody`. The F03 receipt is pinned to source `69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; Git blobs for `cycle_substrate.py`, `test_cycle_substrate.py`, and `run_lifecycle.py` match exactly between that source and this base.

The property is V3 context-job serialization of `ArtifactID` root models: validate the root and emit its canonical string so WMRv2 selected CAS-view refs survive persisted context artifact write and typed readback. The removal empties `_CONTEXT_JOB_V3_ROOT_SCALAR_TYPES`; the real selected-view persistence path then falls through generic `BaseModel` serialization and raises `cycle_substrate_context_job_v3_serializer_model_unregistered: polisyos.core.artifacts.ids.ArtifactID`.

The original assigned test was `tests/unit/runtime/quality/test_cycle_substrate.py::test_cycle_substrate_context_job_v3_artifact_id_scalar_and_strictness`. It only calls the serializer helper and does not read the R1 flag. The correct bounded target is `tests/unit/runtime/quality/test_cycle_substrate.py::test_cycle_substrate_context_job_v3_binds_wmr_v2_selected_views`: it creates selected-view CAS refs, persists a V3 context job, resolves it, reads canonical CAS bytes, and checks the exact serialized ref string and content hash.

Three-mode run used both selectors in each fresh pytest process, cwd `policy-engine`:

```text
normal/restored: .venv/bin/python -m pytest -c pytest.ini -q <selected-view target> <old helper control>
removal:         .venv/bin/python -m pytest -c pytest.ini -q <selected-view target> <old helper control>
```

Environment in all modes: `PYTHONPATH=<absolute policy-engine/src>`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`; R6/R7 controls unset. R1 was unset for normal/restored and `POLISYOS_R1_REMOVE_V3_ARTIFACTID_SCALAR=1` for removal. The pytest output markers were `.. [100%]`, `F. [100%]`, and `.. [100%]`. The removal log names the selected-view test as the failure; the helper control is the passing second call.

A separate `-vv` invocation of the old helper target with R1 set explicitly reports `PASSED`, `1 passed in 20.19s`, exit code 0. This confirms the prior target was misbound. The grouped runner did not retain its three child return codes; the complete pytest stdout is retained in the mode logs.

Source import identity from `source-identity.log`: Python 3.14.3; imported module path is the worktree's `src/polisyos/runtime/quality/cycle_substrate.py`; content SHA-256 `d16440eff59fb66d98a9eabeb9437e120085fe46bbc015538c399d650ce19e74`.

Raw output files: `normal.log`, `removal.log`, `restored.log`, `misbound-helper-removal.log`, and `source-identity.log`.

Pattern pass: P29/P38—the previous selected test was an adjacent helper proxy, while removal was injected only in the actual CAS owner path. The new discriminator is the real selected-view context artifact write, typed owner resolve, byte-level canonical ref equality, and content-hash check under the same removal control. P01/B01-B03 remain partial: this narrow test is not a served ordinary HTTP → recursion/N6/N4/N5 run and does not build an N5 request or produce/read back a numerical result.

To capture per-process return codes on a replay, use the exact commands above as separate invocations and retain each pytest exit status alongside stdout.

Raw output identities:

- `normal.log@d3fcc582c522b7ecfa83c7c40d3e35676805cbc8c8c52f1c22a9181f93368d90`
- `removal.log@41b890fb2b639f24056fc5a63387f2a8c8fdc306b974a3e54373d236a36f2c7b`
- `restored.log@d3fcc582c522b7ecfa83c7c40d3e35676805cbc8c8c52f1c22a9181f93368d90`
- `misbound-helper-removal.log@c7541750a6fb141867e7c71fd2b701ced48e24c0b6b851d340b0bc66b4fc4512`
- `source-identity.log@a90231dd2303a7a60d1ec9c3787b4e76af2fc70dbd85f543f5018262ea5c153a`

## Transport and acceptance

The normal/restored R1 outputs are byte-identical; both refer to tracked `verification-baseline-logs/r1-normal.log`. Removal, old-helper control and source identity are retained separately. Child exit codes for the grouped modes are not established; stdout identifies the expected failure. Do not upgrade this to an exit-status receipt. Independent review by `environment_setup` accepted only the synthetic V3 owner/CAS property.

## SIM-01 current-base replay

At the same c40d base, Python 3.14.3, pytest 9.0.2, one numeric thread and no production data: `tests/unit/remediation/test_sim_01.py` ran five tests, all PASS. Full output: `verification-baseline-logs/sim-01.log`. Wall time 26.57s; pytest 22.49s; peak RSS 948142080 bytes. The existing cache_dir warning is retained.

The live controller tries a supported coupled DES/ABM plan after an unsupported NCM candidate, preserves rejected history, rejects all-incompatible candidates, and rejects a foreign/missing selected trajectory. This receipt establishes the direct-controller fixture behavior only. It does not establish the served N5 multi-plan producer, persisted N8 selection equivalence, or production grounding. B06/B07 remain partial pending the bundle criterion and G acceptance.

## Pattern pass

P29/P38: R1 now removes the runtime serializer property while retaining adjacent helper markers. P32/P40: SIM-01 live-run binding is distinct from persisted loader binding; the latter is an identified same-class deeper boundary and is handled in the N5 readback slice. P35: no subset test pass is generalized to all A findings. P41: historical failed cells are observations, not attributed inherited red.

Code adoption: no product code change; verification-only artifact awaiting G acceptance. Finding closure proposed: none. No B09 equivalence rule or B31 uncertainty ruling is inferred.
