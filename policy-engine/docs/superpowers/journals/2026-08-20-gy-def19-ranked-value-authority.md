# GY-DEF19 — ranked-value authority fails closed without an owner resolver

Date: 2026-08-20

Branch: codex/gy-def19-ranked-value-authority

Slice base: 1360b1cb592be6a19c162a3ec3ddb5a2e87986c7

Red-first commit: 288ca1d93

Source freeze: a2a804bec4e275eebd1c83b06649f55720967184

## 1. Isolation and toolchain baseline

The worktree was attached to the commissioned branch at the slice base with an empty status before
measurement. Every read, write, environment bootstrap, test, and commit used
`/Users/deniskopylov/polisyos/.worktrees/gy-def19-ranked-value-authority`; the parent checkout and
all sibling worktrees remained untouched. Line 7 of the GY plan retained SHA-256
`432e664ec3e5fc8c70688b41084d292b7fa606868a0425501a9d345cc769449f`; this lane assigns no
revision number.

The toolchain gate was declared before tooling evidence: Python 3.14.0 and uv 0.9.21 are supported;
the fresh worktree initially had neither `.venv` nor `node_modules`. No TypeScript scanner was used,
so the `corepack pnpm install --frozen-lockfile` prerequisite was not activated. The first targeted
pytest command provisioned 151 frozen packages into the ignored, worktree-local `.venv`; its first
60 seconds are environment provisioning, not product duration. A later readiness invocation using
an unsupported `--output-format` flag was classified as a loud CLI non-receipt and replayed through
the validator's actual `--repo-root` interface.

## 2. Owner-existence census

The complete pinned denominator is 6,182 tracked files under `src`, `tests`, and `tools`, including
5,379 Python files: `src` 2,771 / 2,561 Python, `tests` 2,894 / 2,394 Python, and `tools` 517 / 424
Python. The census found the `AuthorizedValueSchedule` contract and
`build_authorized_value_schedule` factory but no production caller, no persisted authority owner,
and no schedule resolver. `persist_value_choice_provenance_bundle` also has no caller. Foundry has a
numerical-weight resolver, not a normative-authority owner. `NormativeDecisionRequest` occurs in no
file in the pinned code denominator.

Verdict: the honest capability label is `producer_missing`, with `artifact_missing +
bridge_missing` deficits. Therefore the repair cannot resolve through an owner and must fail closed
on every `ranked_with_authorized_values` admission. It does not invent a registry, resolver
protocol, allowlist, caller-supplied schedule object, or convention over names. The broader inherited
claim that nothing ranks in production was refuted: causal HTE ranking exists; the zero-live-owner
finding is narrow to the S8 ranked-value authority path.

## 3. Two-validator realization measurement

The measurement ran before any tracked write and returned the fixture / negative-control outcome,
not a realized governed authority escape.

- `_validate_s8_runtime_negative_firewalls` contains the only validator call to
  `build_pareto_archive`. It passed a synthetic shadow ref containing both trigger substrings and
  treated any `P20NormativeChoiceError` as success. It was refusal-only and would have become a
  false witness after a universal fail-closed repair.
- `_s8_posture` in the N9 promotion-contract validator never calls `build_pareto_archive`. It
  constructs an unresolved `Layer2S8ValuePostureInput` with `s8://schedule` and `s8://pareto`.
  The committed promotion artifact contains three such posture DTOs and zero objects with the
  `ParetoArchive` producer shape. All three enclosing receipts have `promoted=false`,
  `consumer_promotable=false`, and `non_promotable_reason=verification_only_replay`.

The complete committed-artifact traversal therefore found no ranked archive admitted through the
defeated substring guard. N9's direct acceptance of bare S8 posture refs is part of the missing
producer/resolver chain registered as GY-GAP7, not evidence that this defect was realized in a
governed archive.

## 4. Governed-byte disjointness

Immediately before the first write, `architecture/generated_artifacts.toml` expanded 59 families /
441 output specifications to 714 tracked files. The complete
`architecture/policy_design_case/` set contained 509 tracked files; their intersection was 308 and
their union was 915 files / 47,586,550 bytes. The union path hash was
`sha256:d4895976aba090bde4ea8d3bb6c1e6e13ac4dc516bf04e3e74926bc1c8544b50`; its length-framed
content hash was `sha256:077f9d2251bbfd545381800ab4f749d14630a35a1f4c6bbff11061f547d92ebc`.
The complete nine-path candidate write set intersected that union at zero. This proves byte-level
disjointness only; semantic artifact freshness is measured non-persistingly after source freeze.

## 5. Red first

Four public-boundary tests failed before the mechanism in 117.95 seconds, after environment
provisioning:

1. the factory-built authorized schedule named `shadowless-2026` was refused by its name;
2. the factory-built shadow schedule named `sh4dow-q3` returned a ranked archive;
3. an unresolved neutral reference returned a ranked archive; and
4. a genuine shadow schedule whose UUID-hex name was invented at test time returned a ranked
   archive.

All four failures were behavioral: one wrong refusal and three `DID NOT RAISE` outcomes, with no
collection or fixture failure. They were committed alone at `288ca1d93`. The final first test was
then changed, as approved, to assert resolver-absence refusal: in a deployment with no owner, a
factory-constructed DTO cannot self-attest legitimacy without recreating P37.

## 6. Frozen mechanism and scoped companion repairs

`build_pareto_archive` no longer inspects the reference text. Ranked admission always raises
`P20NormativeChoiceError.code == "p20_value_schedule_resolver_absent"` while the GY-GAP7 owner is
absent. `p20_value_schedule_ref_unresolvable` is a distinct reserved code for the future state in
which an owner-backed resolver exists and fails on one reference. Unranked frontier archives retain
their existing path.

The readiness witness now calls ranked admission with the factory-built authorized ref and requires
the resolver-absence code; it no longer reports an unresolved refusal as proof of shadow-kind
classification. The S8 repo-quality witness makes the same distinction. The stale CI row now points
to `test_design_axes_value_choice_provenance.py`. Of the five stale S8-plan references, the three
pytest commands were gate-bound and corrected; the expected-file inventory and historical create
instruction are navigation prose and remain recorded history.

The initial fail-closed mechanism and scoped companions froze at `47d6d62c2`. Independent review
then found ordinary model-minting seams, each exposed red-first before its mechanism. The final
source freeze is `a2a804bec4e275eebd1c83b06649f55720967184`.

## 7. Verification before review

- Four repaired boundary tests: 4 passed in 19.40 s.
- Complete touched S8 unit file plus corrected repo-quality witness: 16 passed in 29.53 s.
- Layer 2 readiness validator through its declared CLI: status `pass`, issues `[]`, in 13.39 s.
- CI-tier diagnostic: neither the removed path nor the actual S8 test path has a violation; 87
  unrelated repository-wide tier gaps remain outside scope.
- Targeted Ruff over the four changed Python files: pass in 0.07 s after normalizing the two touched
  files' pre-existing long import statements.

## 8. P40 review ledger and bounded residual

Round 1 / 2 was an Important **NEW CLASS** finding against the mechanism: the exported
`ParetoArchive` constructor bypassed the builder-only guard. The direct-construction test failed
behaviorally before the repair, and `ParetoArchive._validate_ranked_admission` then established the
same fail-closed invariant at that model boundary.

Round 2 / 2 was a Blocking **SAME CLASS, one level deeper** finding: Pydantic's supported trusted
minting APIs bypass model validation. The complete Pydantic 2.12.5 surface measurement covered the
6,182-file pinned set, identified 2,675 Pydantic subclasses and zero repository overrides of the
relevant methods, and reduced six spellings to three independent primitives:

- `model_construct`, with deprecated `construct` as its delegate;
- `model_copy`, with `__replace__` and Python 3.14 `copy.replace` as delegates; and
- deprecated `copy`, which independently calls Pydantic's copy internals.

All six spellings minted a ranked archive before the terminating widening; the red run was six
`DID NOT RAISE` failures in 18.73 seconds. `ParetoArchive` now revalidates the complete payload from
all three primitives, so their delegates close by construction. Two independent delta reviews and
the witness review returned GO with no new Blocking or Important mechanism finding. Final rounds:
**2 / 2**.

The post-budget residual audit found a **SAME CLASS worked example**, consuming no new round. An
unbound low-level `BaseModel.model_construct.__func__` can deliberately forge an invalid ranked
instance, and exported `persist_value_choice_provenance_bundle` accepts an arbitrary mapping without
revalidating it. A non-writing capture-store falsifier proved that helper accepts the forged dump,
even though normal `ParetoArchive.model_validate` refuses it. The complete production census was
2,771 tracked `src` files / 2,561 Python / zero parse failures: it found zero production calls to
either `build_pareto_archive` or `persist_value_choice_provenance_bundle`, and no governed
realization through the helper.

The bounded residual is therefore deliberately narrow: the generic persister is accepting but
dormant and unorchestrated, not absent. The bound is falsified by any production caller or governed
artifact passing through that unvalidated helper. The smallest closing capability is GY-GAP7's
owner-backed producer, persistence and resolver plus one mandatory cut line at that persister or its
replacement that revalidates the archive and owner-resolves and content-binds its schedule before
persistence, promotion or surfacing. That capability does not exist in this deployment. P40 forbids
another instance patch after round 2; the residual is recorded rather than hidden.

## 9. Final targeted verification

- Six supported/delegate minting seams: 6 passed; each ranked mutation refused and each safe unranked
  operation remained admitted.
- Complete touched S8 unit file plus the corrected resolver-absence repo witness: 23 passed in
  10.35 seconds.
- Independent witness review: 13 focused cases passed; mechanism reviews separately replayed eight
  and seven focused cases, all green.
- Layer 2 readiness S8 probe: issues `[]`; its refusal witness requires
  `p20_value_schedule_resolver_absent`.
- Targeted Ruff over the changed Python files and `git diff --check`: pass.
- A broader targeted repo-quality invocation completed every data-independent case green but had
  five fixture setup errors because worktrees carry no `production_data/manifest.json`; this is a
  loud fixture non-receipt and supplies no mechanism evidence. No full pytest was run.
- A file-wide mypy invocation is not used as closure evidence: after the new override diagnostics
  were removed, it still reported seven diagnostics outside the added methods, and this lane makes
  no provenance claim about them.

## 10. Artifact provenance replay and zero-delta disposition

The first non-persisting N9 check was current: status `pass`, issues `[]`, validator wall time
63.57474 seconds and process wall time 80.99 seconds. The first generation-cycle check, in the fresh
DEF19 worktree without the admitted read-only `production_data` dependency, reported
`generation_cycle_contract_canonical_bytes_drift`, with
`actual_hash=sha256:848e4c2c63550f7b2ab6b86c6699fe9851403e1bbe2ca4f6f2a0f45ef0fb17bd` and
`expected_hash=sha256:f1554159844babea49f1d4bf3413b8a5c8b798312994a59d3bd027683eede56e`.
That observation was true but its attribution to DEF19 was not established.

### Corrected artifact-custody guard

The first replay harness incorrectly required the moving `main` tip to remain equal to the slice
base. That tested a proxy for the real property: `main` advanced through unrelated DS6 commits while
the DEF19 worktree, immutable merge base, replay base and all three protected artifacts remained
unchanged. The guard stopped cleanly before a tracked or governed write; this is a replay-harness
`P38` companion and consumes no artifact-custody round.

The corrected guard admits a scratch mutation only when all of these facts hold before and after it:

- the resolved worktree is the commissioned DEF19 worktree, attached to
  `codex/gy-def19-ranked-value-authority` at the declared HEAD;
- `git merge-base HEAD refs/heads/main` remains the immutable slice base
  `1360b1cb592be6a19c162a3ec3ddb5a2e87986c7`;
- the independent replay clone is at the declared replay source commit with a clean status; and
- the raw SHA-256 values of generation cycle, N9 and N11 remain respectively
  `2e931ccfcd07141178eb622ec03348a7db3d1f437cc396b5f909eba41ae7136a`,
  `08877f171fb08424896d177dac5aa7f7801dcce4bdc2ce77f9faa3690cc2cd1e`, and
  `dd8f4be3afc8deefade824cb4bb4de0cce0d051fa262abb0c427c157ea770391`.

The current `main` tip value is deliberately neither compared nor hashed. The moving ref is
consulted only to recompute the explicitly commissioned merge-base relation: ordinary descendant
movement leaves that result unchanged, while a changed merge base is the relevant stop event.
Branch/root constrain where the harness may operate; immutable commits, relative paths, rendered
candidate bytes, pointer deltas and protected preimages constrain artifact meaning.

### One-environment, two-source P41 replay

The fixed clone environment initially omitted `production_data`. Base and head both completed red
with the same derived content hash
`sha256:cf4cb58319ab1c8b6618cdb7e507d795b11c8e64cc2529da39c5bc9f5d9f7d43`, so that pair was a
GY-DEF22 worked example, not DEF19 evidence. Its one saved candidate was 183,490 bytes with raw
SHA-256 `b99538981f8bac1dca1b13ef4a6c58b9cd56223a2fcba94a2b10a9747cd7c6c4`.
The controlled diagnostic used the exact DEF19 head before the link was added. Its complete
semantic diff was eight leaves: the two content hashes plus, in each generation cycle, the authority
blocker, world-model error and world-model error code changed from
`world_model_record_unresolved` to `substrate_catalog_missing`. Adding the catalog link was the only
deliberate replay-environment change before the bound head pass, so the substantive divergence was
localized to the missing production-data input rather than inferred from an absolute hash.

The replay clone then received the read-only canonical `production_data` link recorded by GY-DI1.
The final receipts content-bound Python 3.14.0, a 284-distribution profile at
`sha256:b9f47e6f5d67f643bb69ae65bc1e4dd68f63448a58214341f646dd107481f385`,
`pyproject.toml` at `sha256:f73570fc13cf6828407ed7e9b3df341728bf5cd1365655c7f97c39f0237a7d69`,
`uv.lock` at `sha256:3f9dfe227ec3c49747027fefa5d73acba9c9e21ec691c44829fb1066a69b38d1`,
and the production manifest at
`sha256:9e0e0aa0acd3c91f0120a80a2570be358ff16a63218abcd998f4d6f0212b6105` before and after each
run. The exact check returned:

| Source state | `value_choice_provenance.py` SHA-256 | Result | Validator / process wall | Uptime load pair |
| --- | --- | --- | --- | --- |
| requested replay base `0fc36511d30805810ea6e1c3c62adcdf13166a6b` | `a1e0e8c788ca2f2e2c3914d57467d8b580a67ebec5686e848fc09cd60491ae51` | pass | 23.927406 s / 39.99 s | 2.78/2.97/3.05 -> 3.32/3.09/3.09 |
| slice base `1360b1cb592be6a19c162a3ec3ddb5a2e87986c7` | `a1e0e8c788ca2f2e2c3914d57467d8b580a67ebec5686e848fc09cd60491ae51` | pass | 23.642345 s / 39.10 s | 2.97/3.02/3.09 -> 3.27/3.11/3.12 |
| DEF19 head `0f99f740fa4dcb848808b78a502785cfd7b5f2af` | `16e25be0a8c4ce569b5edf259fe31407a9ec211cd3cb196f37039a3fa747566e` | pass | 25.18837 s / 39.68 s | 2.43/2.90/3.04 -> 3.12/3.01/3.07 |

The replay-head source bytes equal the commissioned worktree's source bytes. All three passes
exercise the validator's exact rendered-canonical-byte comparison against the same committed
generation artifact. The requested replay verdict and the direct slice-base P41 verdict are both
**base pass, head pass**: the original drift was an environment confound and is not DEF19's.

### Artifact disposition

The exact rendered-canonical generation-cycle delta is 183,254 bytes to 183,254 bytes, file-byte
SHA-256
`2e931ccfcd07141178eb622ec03348a7db3d1f437cc396b5f909eba41ae7136a` to the same value, zero
changed leaves, and the complete JSON-pointer set is `[]`. Because attribution did not confirm and
the admitted head candidate is byte-current, the condition for an N11 cold derivation was false.
N11 was not spent, no transition declaration or guarded writer was admitted, and the artifact-phase
custody ledger remains **0/2**. This is the valid-old-bytes versus zero-writer-delta distinction:
there was no no-op writer invocation to accept.

The complete governed denominator was independently recomputed at record freeze: 59 families / 441
raw output specs / 6 explicit external scratch specs, 714 tracked registry outputs, 509 tracked PDC
files, intersection 308, union 915 files / 47,586,550 bytes, with the same length-framed content
SHA-256 `077f9d2251bbfd545381800ab4f749d14630a35a1f4c6bbff11061f547d92ebc` before and after the
record edit. Under SHA-256 collision resistance this supplies one complete aggregate commitment to
the governed path-and-byte sequence; it is not described as a per-file writer snapshot receipt.
No rollback was armed or required because no governed writer was admitted.

Measured outcome: the substring authority defect is repaired at the source boundary by exact
fail-closed resolver-absence semantics, with unranked behavior preserved. Clauses one, two and four
of the registered closure signal are satisfied across the supported construction surface; positive
admission under clause three is structurally deferred to GY-GAP7's missing owner chain. No governed
artifact reissue is owed by DEF19.
