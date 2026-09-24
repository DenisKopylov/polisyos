# R14 value provenance regression map

Status: read-only diagnosis from the four-base P41 broker; no test/native job
was launched for this note. This Appendix-A/B add-on is a newly measured
instance of **R10 / CAS-03**, not a new R14 mechanism.

## P41 evidence

The whole-file denominator is 48 tests from the same tracked test blob
`policy-engine/tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py`
`@97b485b770584bd6b322c151c01e2debf1188fe7` at all four bases. The broker
used the same harness (`sha256:53cbf64242d413dabd49f3d3883d7a6239fa7441bd512b96f5fe3816b90de13f`),
environment policy, and production-data manifest
(`sha256:9e0e0aa0acd3c91f0120a80a2570be358ff16a63218abcd998f4d6f0212b6105`).
The selected tests use temporary CAS roots and generated signer keys; they do
not read production data.

| Base | Whole-file result | JUnit SHA-256 |
| --- | ---: | --- |
| `78187878e` execution base | 48 passed | `fea7da7aca92c3b821c1ff420c4d9444e58aec35f3e451c9e82b3bcb2326e456` |
| `00d946c2b` E02 head | 33 passed, 15 failed | `34beb95987083aa57b5f44856847df755179b956a18f3c083d6c68c94aa5ffca` |
| `5fd3ebcc1` main | 48 passed | `b674ce490f9f29f3c038ca784c0865c2b87afd081e2757c9c3fdc29e5fbeb76f` |
| `73c656744` Phase 0 merge | 33 passed, 15 failed | `2c3202899c1864e12998c2b0f17b350e433690f385ea46498697dee6c2cd2971` |

JUnit XML artifacts are under
`/Users/deniskopylov/.codex/scratch/e02-r2-baselines/p41-pre-repair-20260924T171600Z-23461/cells/{e02_execution_base,e02_head,main,phase0_merge}/test_design_axes_value_choice_provenance-ab5609c83219.junit.xml`.
The corresponding append-only checkpoint rows are currently
`/Users/deniskopylov/.codex/scratch/e02-r2-baselines/p41-pre-repair-20260924T171600Z-23461/checkpoint/progress.jsonl:76-79`.
The broker is still running, so this checkpoint path is mutable; use the final
results/checkpoint digest when the baseline wave closes. The four JUnit hashes
above identify these completed cells independently. The execution-base cell
used the 1800-second alarm; the E02-head, main, and Phase 0 cells used
120-second alarms. All four completed without a timeout, so this difference
does not change the reported outcomes.

The 13 direct signature/admission failures are:

- `test_separate_signed_authorization_produces_persists_resolves_and_projects`
- `test_invalid_authority_keeps_frontier_and_persists_typed_request[missing_schedule-p20_value_schedule_ref_unresolvable]`
- `test_invalid_authority_keeps_frontier_and_persists_typed_request[self_grading-p20_normative_self_grading]`
- `test_invalid_authority_keeps_frontier_and_persists_typed_request[role-p20_normative_authority_scope_mismatch]`
- `test_invalid_authority_keeps_frontier_and_persists_typed_request[purpose-p20_normative_authority_scope_mismatch]`
- `test_invalid_authority_keeps_frontier_and_persists_typed_request[scope-p20_normative_authority_scope_mismatch]`
- `test_invalid_authority_keeps_frontier_and_persists_typed_request[case-p20_normative_authority_scope_mismatch]`
- `test_invalid_authority_keeps_frontier_and_persists_typed_request[stale-p20_normative_authorization_stale]`
- `test_invalid_authority_keeps_frontier_and_persists_typed_request[shadow-p20_resolved_schedule_not_authorized]`
- `test_ranked_persistence_and_projection_recheck_ttl_and_exact_selection`
- `test_admission_cannot_replace_verified_claimant_with_an_asserted_identity`
- `test_schedule_bytes_remain_bound_after_a_valid_signature`
- `test_selection_permission_sets_a_whole_authority_ceiling`

Two more failures, parameterized as
`test_permission_projection_never_grades_candidate_auxiliary_premises[REVIEWER]`
and `[MACHINE]`, are downstream. Their fixture first expects a successful
normative recommendation and takes `archive.normative_admission_ref` into a
projection. Since the signature failure prevents admission, the ref is
absent and projection raises `p20_normative_admission_missing`. Both pass on
the execution base and main. This is the same R10 break in the producer chain,
not a second class.

## Root cause and production caller

**Property.** A valid string artifact reference and its equivalent typed
`ArtifactID` must reach the same signature/integrity verifier. Malformed IDs
must fail closed before storage I/O; a valid signed record must not become
unverified because one consumer supplied its canonical string reference.

In the E02 and Phase 0 source,
`policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`
`@83ec53fefe0cc036480bb3d164ebcb44225a6ed9`,
`NormativeValueScheduleOwner._signed(ref: str, ...)` passes `ref` directly to
`self._store.verify_signature` (lines 662-667). The E02 version of
`policy-engine/src/polisyos/core/artifacts/store.py`
`@775d9811ae8fc3fd075845400b7a0b452600e387` routes verification through
`load_snapshot=self._load_verified_snapshot` (lines 569-585). The loader
expects `ArtifactID` and calls `self._paths(artifact_id)` (line 1170); `_paths`
delegates to `CASPathLayout.paths` (store.py line 224; `_layout.py` line 20),
where `.hex` is read. Thus the relevant boundary is the typed storage path
lookup, not the loader's declaration alone.
`_verify_signature` catches the resulting `AttributeError` and returns
`SignatureVerificationStatus.ERROR`; the E02 JUnit shows
`"str" object has no attribute "hex"`, which the owner maps to
`p20_normative_signature_unverified`.

This is attributable to R10: main's corresponding `store.py`
`@76cc3574f2bbbb102f47111872ac31f131c253fe` and
`_signature_ops.py` `@c6bffa42359f9e8e11748caa84fb64ce04268013` use the
pre-snapshot path through `verify`, `get_signature`, and byte readers, which
normalize string IDs at their storage boundaries. E02 introduced the snapshot
path in `_signature_ops.py`
`@793c4faea145ca25522860836ecab93747a732f5` without normalizing the public
`verify_signature` input first. The source in the Phase 0 merge matches E02
for this path. The small E02 `repo_root` addition to the S8 owner is present,
but it does not explain the string `.hex` exception.

The production caller exists: HTTP `POST /runs/{run_id}/normative-evidence`
in `runtime/http/routes/control.py:443-460`
(`@f1331c7da27c1d65688d484539063bda66b9357b`) invokes
`ControlPlaneService.submit_normative_evidence`. That service calls
`resolve_generation_value_choices` (`run_lifecycle.py:1635-1658`,
`@a3827ed1677df17f09827d479db7510ffdb70e6e`), which builds the normative
owner and produces/replays S8 dispositions through
`runtime/http/services/control/generation_cycle.py`
`@055cca6c9424deac61fa61543143a2a2d2310b1a`. The owner verifies persisted
authorization, schedule, and frontier string refs before it can admit a
ranked value choice. Completed-job readers also revalidate the normative
projection. This is therefore a served production path, not a test-only
mechanism.

**Class / P40.** Fold all 15 into existing **R10 (CAS-03)**. The storage
snapshot transition is the shared mechanism; the direct cases and the two
missing-admission projections are consequences at increasing depth of that
same string-ID boundary. R10's caller census and complete proposed mechanism
are in `R10_SIGNATURE_MAP.md`
`@f39245cea3b66b393263dfa2853d31f14bac0d53`.

## R10 verification probes and write set

- **Removal probe:** at the public `FileSystemCAS.verify_signature` boundary,
  remove only the conversion of a valid string to `ArtifactID` while keeping
  the `ArtifactID | str` API marker and snapshot path. Sign a temporary
  artifact, call with `str(ref.artifact_id)`, and assert the snapshot loader
  receives `ArtifactID` and the result is `VALID` with the expected signer.
  The probe turns red when conversion is removed: the current E02 behavior
  returns `ERROR` from the string `.hex` access.
- **Property-preserving control:** verify the same signed artifact through an
  already typed `ArtifactID` and through its valid canonical string; both must
  retain the same valid signer/integrity result. A malformed string must
  return typed `ERROR` before any CAS read, never gain authority.
- **Smallest owner-first implementation write set:**
  `policy-engine/src/polisyos/core/artifacts/store.py:569-586`, normalize once
  before invoking the snapshot path. Focused owner test:
  `policy-engine/tests/unit/core/phase0/test_store_signing.py`. Keep
  `_signature_ops.py` internal to typed IDs and route consumers through the
  CAS owner; the test file named above supplies the served S8 confirmation.
  This matches the wider R10 caller map and does not require a local cast or a
  second verifier in the S8 owner.

**P38 divergence.** The property is signature verification over the bytes
identified by a canonical artifact reference. The E02 implementation instead
tests a Python representation detail at the newly introduced snapshot loader:
typed `ArtifactID` reaches verification, while an equivalent valid `str`
fails before the signature is checked. The divergent case is the real S8
owner's `ref: str` passed to `FileSystemCAS.verify_signature`; status becomes
`ERROR` even when the artifact, manifest, and signature are valid. P37's ID
syntax can be recomputed with `ArtifactID` validation; signer, signature, and
snapshot integrity remain determined by the existing cryptographic verifier.

## Source and test write-set references

| Role | Path | Base blob | E02 / Phase 0 blob |
| --- | --- | --- | --- |
| Regression file, unchanged across four bases | `policy-engine/tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py` | `97b485b770584bd6b322c151c01e2debf1188fe7` | same |
| Regression mechanism | `policy-engine/src/polisyos/core/artifacts/store.py` | `76cc3574f2bbbb102f47111872ac31f131c253fe` | `775d9811ae8fc3fd075845400b7a0b452600e387` |
| Snapshot verifier change | `policy-engine/src/polisyos/core/artifacts/_signature_ops.py` | `c6bffa42359f9e8e11748caa84fb64ce04268013` | `793c4faea145ca25522860836ecab93747a732f5` |
| String-ID producer/consumer | `policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py` | `96d8dca3e8292d4afbed4647419a238e8a21e4e5` | `83ec53fefe0cc036480bb3d164ebcb44225a6ed9` |

The P41 result is a whole-file behavioral replay with a common tracked test
blob and a direct storage exception, not a stale generated artifact or a
production-data condition. Keep its checkpoint aggregate provisional until
the broker writes the final receipt.
