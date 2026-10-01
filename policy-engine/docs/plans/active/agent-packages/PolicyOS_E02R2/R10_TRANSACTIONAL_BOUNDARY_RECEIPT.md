# R10 public signature boundary repair

## Discrepancy and property

The R9 transaction decorator parsed identities before entering the public
`FileSystemCAS.verify_signature` handler. A malformed ID therefore raised
`ValidationError` before its typed `ERROR` boundary. This is the existing R10
normalization class reopened by the transaction composition, not a new class.
Valid identities must still pass through tenant/view/pending-intent/snapshot
and signature checks under the CAS transaction lease.

Normalize at the public boundary, then call the existing transactional read
mechanism through `_verify_signature_under_transaction_lease`. No caller API,
identity/profile schema, approval policy or trust authority is changed. The
implementation now tests identity validity before acquiring the lease; it
neither grants owner scope to malformed inputs nor removes valid-input custody.

## Frozen candidate evidence

Candidate `codex/e02-r2-r9-publication@fdac2ae1209e6a80a72f8ab90aa974916624c229`
passed all 47 cases in three complete files: signing 21, protocol 10, CAS-03 16.
Root readback `/Users/deniskopylov/.codex/scratch/R10_TRANSACTIONAL_BOUNDARY_CANDIDATE_RUNTIME_READBACK_20261001.json@sha256:dc7a6f8710e755d6cd5575eaec9477c20456ded40cb10fbc458473d8be820475`;
complete deciding result `/Users/deniskopylov/.codex/scratch/R10_CURRENT_WHOLEFILE_ADAPTER_20261001/runs/r9-cas03-v5-wholefile-20261001T075429579887Z-66377/results.json@sha256:088f6fcfc41942847116ce54e99cd003aa33607d8ed2b2c2af2734f35676ed24`.
Each origin inspection passed over 6,414 frozen tracked Python/config paths;
postflight reported no drift or resource guard. The malformed controls have
no owner scope and forbid CAS reads. The valid-string control uses the real
tenant-bound store and Ed25519 verifier under the retained lease.

The complete caller census walks 5,444 tracked source/test Python files:
50 direct call sites, 18 source and 32 test. Census
`/Users/deniskopylov/.codex/scratch/R10_TRANSACTIONAL_BOUNDARY_REVIEW_20261001/VERIFY_SIGNATURE_BOUNDARY_CENSUS.json@sha256:3d1c93f874be4c13d1f2dab0809acd1a692579d6fad496033a8634faff4c4b1b`.

## Removal and preserving control

Root ran the six exact selected cases at the same frozen candidate. The probe
bypasses only the public catch by calling its real transactional helper;
source markers and helper normalization/custody remain. All five malformed
cases become JUnit call-phase failures with
`pydantic_core._pydantic_core.ValidationError`; the valid-string control passes.
This is an expected-red mutation, not six passing functional tests. Pytest
exit 1 is retained; the probe verdict exits 0. Wall time is 2.120 seconds,
origin inspection passes (63 loaded modules / 6,414 frozen paths), and all
source, candidate, data and process-group postflight checks remain clean.

Deciding verdict `/Users/deniskopylov/.codex/scratch/R10_CATCH_REMOVAL_PROBE_20261001/runs/r9-cas03-v5-wholefile-20261001T083238973054Z-71822/probe_verdict.json@sha256:737205a6cb92759d37fdaf2ddc9ccc43a3a1c99ebacaaa6067a02c56ce2a3778`;
JUnit in that directory at
`cells/r9_candidate/test_store_signing-976d304c570f.junit.xml@sha256:468c387ae98f3827e8fe1975b8e67324070d57aef96b90c89eefbf4259533d95`.
The V2 adapter is retained at
`/Users/deniskopylov/.codex/scratch/R10_CATCH_REMOVAL_PROBE_20261001/run_r10_catch_removal_root_owned_v2.py@sha256:50e7a4764db11d5601235863cc95bb2fee3f19a93c24c33d015204b825ace158`.

## Integration and limits

Root applies the exact two reviewed file bytes from the candidate to
`codex/e02-r2`, after pre-edit commit `749e1d1862009cca200aeb9b5c19074b1bd3b57a`.
Patch `/Users/deniskopylov/.codex/scratch/R10_TRANSACTIONAL_BOUNDARY_PATCH_20261001T072916Z/candidate.patch@sha256:b499beefe7f0b052202769f92b3c1a8b9b32516f837077c8f44f16a184d6a553`;
independent code GO `STATIC_REVIEW.md@sha256:7381c7d9e21c8a23074c31b965c529ce8edfb6275f651c45ab4d5adbb807ec56`
in that directory. Source SHA-256 is
`3e916ac7762dc41b7fece8f71a912e8e7dfdd535bf64dde07a8a325dd7aff4b5`;
signing-test SHA-256 is
`21d210a1d4b9493e3400f64b109e5f820821495c298dfbe3f3017a17bd3abf34`.
Fresh integrated replay remains UNRUN at this source checkpoint. Whole-class
four-base, broader guarded/served consumers and authority closure remain
outside this candidate cohort; no ledger status changes or R10 closure follow.
Production data is cited read-only by canonical path and manifest SHA-256
`9e0e0aa0acd3c91f0120a80a2570be358ff16a63218abcd998f4d6f0212b6105`.
