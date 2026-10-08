# C09 / B190 sensitivity source review

**Disposition:** prepared/source-ready for independent review; not accepted, not a completed source handoff, and not B190 closure. Review was static; no tests were run.

## Source and ownership

- Candidate `665ea762c107a76cf06024934fb3e176b41ba043` (tree `cb5d23374838763fc9e9a90fd25059905163dbed`) is based directly on G `f00dd7661a8d3329fb1fa1b049decb0d1d2f277b`. It changes only:
  - `src/polisyos/foundry/calibration/identifiability.py`
  - `tests/unit/foundry/calibration/test_identifiability_response_basis.py`
  - `src/polisyos/foundry/calibration/README.md`
  - `release-fragments/unreleased/2026-10-08-c09-sensitivity-response-basis.toml`
  - `docs/research/e02-cloud-test-plan/implementation-handoffs/E/parallel-20261008-c09-sensitivity/minimum-node-adoption-packet.json`
- The changed mechanism and mirrored test fit dispatch C09's original-unit E lease (`foundry/calibration/`, its calibration test selector). This is the separate supplemental sensitivity branch, not the base C09 role's topic. The candidate uses the selected G identifiability blob `aad1abdd89ac8dda43918981bc21f4a9755601a2`; the E-source alternative blob is `712bb1a7c8e0e72f418163a912eb6134bbf07b29`. Dispatch `E_source=8d8e7b319e7eb6b57bc4ab3c4db5ca3070393f8c` is an ancestor of E `7bf53fd0cf69a568b37d8a881e26bfb16c315653`; the packet explicitly rejects copying E's unrelated cumulative carrier.
- Existing `foundry.calibration` facade already exports `identifiability_diagnostic`; this adds its `response_slots` keyword. No public inventory, schema/generator output, `pyproject.toml`, `uv.lock`, or adapter/facade file is changed. The release fragment says the public inventory review is false, and the packet leaves that shared G companion pending.

## Property, evidence, and boundary

The new path replays the actual Foundry execution at finite-difference points, reads registered global scalar state slots, and persists the Jacobian plus a `response_basis` with source/manifest identities, ordered axes, declared units, config, seeds, requests, overrides, and replay refs. `_load_execute_response_matrix` recomputes the expected basis, input roster, replay lineage, Jacobian, weighting, and Fisher matrix from CAS. The tests are substantive: native `income_tax` zero-baseline witness (`y(r)=4r-2`, `J=4`), exact `Fraction` variance arithmetic (`4² × 1/16 = 1`), fresh-reader replay, and changed-unit/source/axis/lineage/matrix refusal cases. They are source evidence only here; I did not execute them.

This is a local numerical finite-difference basis, not Sobol/global variance attribution (the existing Sobol path is in `scientist/methods/doe`). It always records `gate_eligible=false`; it supplies no empirical input law, causal/scientific/Runtime admission, production fiscal suitability, or composed Scientist/uncertainty consumer. The private recomputing reader has no production adapter call site. The packet explicitly leaves composed Node adoption UNRUN and asks the canonical E uncertainty/Scientist Node owner to validate its own source/law/target contract. Thus producer mechanics may be implemented in this candidate, but the capability remains `consumer_missing` for composed adoption; public inventory reconciliation and independent review are also pending. The packet is an adoption dependency note, not a source-qualified completion receipt; it does not claim B190 or all-35 closure.

## ORCH03 admission delta

`9a2cc9dbe0fc2c50ed2371f56cbdde79c05656ff` over `de7b08ebbac72232c98d96ea74c3c0410864a7ba` is metadata-only: it adds `c09-sensitivity-create.json.gz` and `c09-sensitivity-resume.json.gz`, and updates the admission manifest. The manifest pairs match the stored and decoded hashes:

| Receipt | Requested branch / path | Result | Stored SHA-256 / bytes | Decoded SHA-256 / bytes |
|---|---|---|---|---|
| create | `codex/e02-E-c09-sensitivity-20261008` / `/dev/shm/e02-orch03-20261008/c09-sensitivity` | admitted; branch/path absent at create; unresolved inputs empty | `6a18c00f960ab80adbe5bd15beb71dbf486b85b9471892c2312d42d6d00f0b5c` / 13,415 | `1c33cd3a7fb00c331b112372cc6f693b575016fe089851f5bbf686c9edb1cfcc` / 164,979 |
| resume | same pair | admitted; branch exists/path is directory at resume; unresolved inputs empty | `acda0ee9acf269812a041b590baacb83a94ad8be5f1fb329fa212fb40141af31` / 13,899 | `57f910ea7015104dd1e1fb3637e6a01f8255d0f94e60c44d3fc0b2621fc6ea2b` / 171,213 |

The exact remote topic ref resolves to candidate `665ea762…`. The supplement records one additional disjoint original-unit E B190 producer lane with G coordinating the author lease; treat it as supplemental to C09, not as a new dispatch role or a quota. Dispatch capacity is `not_established` and forbids artificial CPU/process quotas. The separate branch/path is admitted, but its broad package overlap with C09's declared source scope still requires single-writer coordination at exact file level.

**Minimum next step:** independent review of the frozen candidate and its actual test receipt; then canonical Node adapter adoption with source/law/target admission and public-inventory reconciliation. Keep production input law and authority out of this local producer claim.
