# GY-DEF19 — ranked-value authority fails closed without an owner resolver

Date: 2026-08-20

Branch: codex/gy-def19-ranked-value-authority

Slice base: 1360b1cb592be6a19c162a3ec3ddb5a2e87986c7

Red-first commit: 288ca1d93

Source freeze: 47d6d62c2

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

Source and scoped companions froze at `47d6d62c2`. Mechanism review rounds remain 0 / 2 pending
independent review; mandated-record findings do not consume them.

## 7. Verification before review

- Four repaired boundary tests: 4 passed in 19.40 s.
- Complete touched S8 unit file plus corrected repo-quality witness: 16 passed in 29.53 s.
- Layer 2 readiness validator through its declared CLI: status `pass`, issues `[]`, in 13.39 s.
- CI-tier diagnostic: neither the removed path nor the actual S8 test path has a violation; 87
  unrelated repository-wide tier gaps remain outside scope.
- Targeted Ruff over the four changed Python files: pass in 0.07 s after normalizing the two touched
  files' pre-existing long import statements.

The non-persisting governed-artifact derivation, independent reviews, final targeted wave, and
GY-DEF19 standing are recorded below after they occur. No governed output is written by this lane.
