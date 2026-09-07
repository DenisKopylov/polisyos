# GY grade authority — investigation and local handback

Date: 2026-09-07. Worktree: `/Users/deniskopylov/polisyos/.worktrees/gy`.
Branch: `codex/gy-grade-authority`. Slice base: `f4815387063`.
No push, GitHub tools, stash, history rewrite, or stale-branch mutation is authorized.

## Investigation (recorded before behavioral measurements)

The four requested debt rows were read as specifications, including their closure
signals. Neither the debt register nor LEDGER is a verification oracle; their
checker is excluded. The task's invariant is: **a grade is not issued by the party
whose claim it grades**. Findings beyond that invariant are proposals, not repairs.

### gy-census-decisive-property-unmeasured

The actual debt concerns evidence for task completion, not whether an artifact has
a field named standing. GY §8.5 and Task Q's investigation distinguish a selected
Done-when predicate from all conjuncts of completion. The historical population
must be recovered from the complete plan change, independently cross-checked,
and joined to current task rows by identity. No search-match total proves it.

Hypothesis before testing: a source-bound measurement can refute a task's
completion claim even when its self-written status remains `executed`; conversely,
one passing delegation test cannot establish the independently correct judgments
required by GY-C2. A runtime receipt verifier cannot by itself establish this
Markdown census. The CR5 routing may therefore need narrowing instead of a shared
wrapper. Cheapest honest close: enumerate the exact population, preserve per-
predicate scope and every unmeasured conjunct, and make the owning plan explicit
about which status is and is not established. Test this reading before deciding.

### GY-PA1

The closure asks for the S8 authorization/request and schedule production,
persistence, resolution and ranked-consumer chain, with the no-schedule and
wrong-authority negatives. GY §8.5 subsequently moves its engineering half to
GY-PR1a; the old PA1 scheduling verdict and missing capability are different facts.

Hypothesis before testing: the current S8 factory admits caller-declared
mandate/status/role references while archive creation always rejects a ranked
case with `p20_value_schedule_resolver_absent`. A green unauthorized-schedule
negative behind that unconditional refusal would measure the wrong property.
Cheapest honest close must wire an independent evidence resolver to the existing
ranking boundary and persist an explicit refusal request, without minting a
mandate or manufacturing an N8 receipt. The investigation must locate the exact
engineering/appointment/data boundary before sizing that repair.

### GY-DEF22

The current closure leaves the appointed Foundry catalog/discovery owner's
acceptance of six bounded claims outstanding. It expressly says no engineering
work is owed. The previous review-subagent ACCEPT is not such an appointment.

Hypothesis before testing: the existing non-decisive diagnostic changes its own
result on environment drift while governing N8/N10a/chronology bytes remain
equivalent to diagnostic removal. Removing the actual generic discriminator,
while keeping its DTOs and marker strings, should make its CB-I02 witness fail.
Cheapest honest close: remeasure that property, retain a typed-empty acceptance
slot, and hand the six claims back for an appointed signature. No self-countersign.

The alleged CR5 witness at `dependency_authority.py:3085` is a private success
payload behind a fieldless token. The visible result union also has rejected and
unestablished arms. This is a counter-hypothesis to the register's isolated-Literal
reading, not yet a behavioral verdict. Follow complete issuance/consumption paths.

### adjudication-and-champion-chain-is-forgeable

The row requires an independently appointed evaluator receipt, a non-producing
authenticator, recomputation from bound observations and champion replay before
any publication projection. Shape and matching manifest labels do not meet it.

Hypothesis before testing: `ClaimAdjudicationRuntime.admit_champion` checks
self-written evaluation metrics, guardrails and provenance strings without an
authenticated observation receipt. A coherently fabricated evaluation passes.
Separately, DataForge's `load_admitted_claim_adjudication_batch` admits a fabricated
batch from matching labels and lineage; `materialize_claim_adjudication_result`
can call it without the Scientist runtime. Thus repairing only Scientist's entry
point leaves a sibling emission path. The single intake must be closed at that
loader too. This path lies outside the allowed edit set, which must be verified
as a real row blocker rather than used to justify a symptom-only fix.

## Execution plan and pattern pass

1. Independently investigate PA1, DEF22 and the stale branch while the coordinator
   investigates census membership and the adjudication chain. No concurrent writer
   shares a source or governed artifact.
2. Record hypotheses first; run focused behavioral stations. Enumerate full path
   sets, compare identities in both directions, classify unreadable cases ambiguous.
3. Implement only an established mechanism within the approved paths. Preserve
   negative and unavailable outcomes, leaving institutional signature slots empty.
4. Freeze changes, review the delta, run blast-radius tests and appropriate
   recomputing validators once. Commit clean boundaries after checking attachment;
   read committed files back from the branch. Stop before push.

Relevant patterns: P05/P15 (authority), P29/P32 (behavior/content versus markers),
P31 (single intake/emission), P35/P36 (whole-set and finding-bound evidence),
P37/P38 (predicate provenance/proxy), P40 (same-class finding bucket), P41 (no
unproved inherited-red claims). A second finding of the same class widens the
mechanism or yields a measured bounded residual; it does not start a patch ladder.
Acceptance: actual consumer refusal of self-issued labels, favorable/unfavorable
results through real paths, and at least one property-removal red per measured row.
Missing capability labels are assigned after tracing, not inferred from prose.

## Stations and environment

- Auxiliary worktrees: none created.
- `git status -sb` after setup: `## codex/gy-grade-authority`.
- `uv sync --offline --frozen --extra lint --extra test --extra runtime` failed
  because the pinned odfpy wheel is not cached. Minimal offline install also lacked
  cached pytest metadata. These are tooling non-receipts, not product findings.
- A local CPython 3.14.3 venv reads the existing main venv's dependency directory
  through local `gy_reused_dependencies.pth`; no sibling file is modified. Tests
  use `PYTHONPATH=src` and local `python -m pytest`, with import origin verified.
- Scratch is under this worktree's `policy-engine/_build/gy-grade-authority/`.
  No shared production data writes or fixed-port/browser stations are planned.

## Measurements, changes, probes and remaining work

### GGA-CENSUS-01 — population and limits

The first whole-commit subtraction found **35**, not 24, new task rows. My first
query was wider than the debt: that commit also added **11 `not_started` future
tasks**. Filtering the complete addition by its recorded standing yields the
original census population, and independently walking the complete original
contiguous census block yields exactly the same identities. This correction was
made before reporting any population as measured. No unreadable row was dropped.

Denominator: one Markdown GY plan, its complete §8.5 table at historical
`73d930f8284682fafc283c2b78c54d64bbecf1dd` and that commit's first parent, and
the complete current table. Original census: **24 = 21
presence-only + three ambiguous** (`GY-D1`, `GY-M2`, `GY-K`). Current table:
**74 = 42 executed + one not_executable + 22 not_started + nine ambiguous**.
The current 21-row subset is **14 executed + seven ambiguous**. Two current-table
parsers agree on the entire identity set, not just its size. The 73-row count in
the task's historical input is not used as today's denominator.

The table below is the complete 21-row set. The Task Q column is a **historical
selected-predicate receipt** from its §3 investigation, not a fresh green claimed
here. All other Done-when conjuncts remain explicitly `not_measured`. That note is
now on **every corresponding row of the owning GY plan**. A favorable author-
written task status does not upgrade the measurement's scope.

| Task | Task Q selected predicate | Full Done when at this station |
| --- | --- | --- |
| GY-M1 | lifecycle scan: fail | not_measured |
| GY-B | non-active operation refusal: pass | not_measured |
| GY-H | terminal precedence: pass | not_measured |
| GY-D2 | connector/source admission: pass | not_measured |
| GY-D3 | adequacy negative and recall, slice0_gate_only: pass | not_measured |
| GY-E | costed acquisition terminal: pass | not_measured |
| GY-C1 | playbook deviation: fail | not_measured |
| GY-C2 | independent real-input judgments: not_measured | not_measured; self-grade falsifier below fails |
| GY-C3 | real Foundry estimate consumption: fail | not_measured |
| GY-I | tool-loop event persistence: pass | not_measured |
| GY-F1 | workflow failure authority recomputation: fail | not_measured |
| GY-F2 | artifact surface safety: pass | not_measured |
| GY-F3 | time/source authority recomputation: pass | not_measured |
| GY-G | feedback without joint grounding: pass | not_measured |
| GY-J | useful-design graded routing: fail | not_measured |
| GY-L | HTTP-triggered outcome run: fail | not_measured |
| GY-S0 | novel registration/versioning: pass | not_measured |
| GY-S1 | L4 world model/simulation: pass | not_measured |
| GY-N-V | timeout yields unknown: pass | not_measured |
| GY-S2 | transported/contested non-point sets: pass | not_measured |
| GY-S3 | every method route covered: fail | not_measured |

Fresh positive-control command (each gate is a sole invocation):

```sh
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/runtime/quality/test_workspace_spine_repair_gates.py::test_governance_tail_verifier_delegates_to_governance_node_owner -q --override-ini addopts=''
```

Result: **exit 0, one passed, 27.15 s**. The actual test calls the real owner but
supplies empty per-judge dictionaries. The owner at
`scientist/nodes/builtins/governance/run_governance.py:1136` checks the set of judge
names, `composite_decision`, warnings and declared completeness. It does not
authenticate or inspect each judgment's substance.

Removal/falsification station:

```sh
PYTHONPATH=src .venv/bin/python -m pytest _build/gy-grade-authority/test_census_judge_station.py -q --override-ini addopts=''
```

**Exit 1, three failed, 27.14 s.** For each judge in the runtime-derived
`_PHASE2_REQUIRED_SIX_JUDGES`, the probe substitutes `{}`, `{"verdict":"reject"}`
or `{"verified":false}` while keeping all judge names, completeness and promote
markers. Every cell returns `applicable`, contradicting the assertion
`status == "repair_required"`. This proves the green delegation receipt is
insufficient; it does not prove the positive real-input Done when. No judge is
silently omitted, and the source's required set supplies the denominator.

**Routing result:** the common principle survives; the proposed shared runtime
implementation does not discharge the documentary census. GY-CR5's witness is
also refuted independently in GGA-DEF22-02. The census therefore returns to its
measurement lane, as the user explicitly permits. The old note-or-measurement
obligation is now complete over its exact population; full task completion and
the broader CR5 all-consumer claim are **not** asserted. Capability grade for the
independent GY-C2 judgment producer remains `verification_missing` at this intake.

### GGA-ADJ-01 — a coherent fabricated chain really publishes

Source paths traced: Scientist `claim_adjudication_runtime.py`, evaluator
`claim_adjudication.py`, `models.py`, `registry.py`; DataForge
`claim_adjudicator.py` and `admitted_claim_adjudications.py`; neutral carrier
`ir/analytics/literature.py`. The input CAS bytes, ordered claim denominator and
manifest lineage were preserved in both negative stations.

The existing Scientist suite is **exit 0, nine passed, 18.38 s**:

```sh
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py -q --override-ini addopts=''
```

Its `_promote_champion` helper constructs a self-stamped passing
`BenchmarkEvaluation` and asserts registry promotion. Reusing that complete
fixture, the new requirement-level negative is **red**: the outcome is
`completed`, with one published claim, where `blocked` is required. The batch
declares `independently_reconciled` despite no appointed evaluator receipt.

```sh
PYTHONPATH=src .venv/bin/python -m pytest _build/gy-grade-authority/test_forged_authority_station.py -q --override-ini addopts=''
```

Initial pair: **exit 1, two failed, 16.24 s**, identities
`test_self_stamped_evaluation_does_not_emit_publishability` and
`test_same_forged_chain_cannot_materialize_without_scientist`.

The second station was then made stronger: it constructs the typed batch and
self-labelled CAS manifest **without ever calling Scientist's runtime**, uses a
zero-valued pointer digest, and invokes DataForge materialization directly.
An authentic evaluator receipt, registry replay and observation recomputation are
all absent; every marker and lineage field stays present. Exact targeted rerun:

```sh
PYTHONPATH=src .venv/bin/python -m pytest _build/gy-grade-authority/test_forged_authority_station.py::test_same_forged_chain_cannot_materialize_without_scientist -q --override-ini addopts=''
```

**Exit 1, one failed, 17.69 s: `DID NOT RAISE ValueError`.** This is the same
authority-intake class at its sibling consumer, not a new repair round. Its
counterexample establishes the genuine file boundary: changing only Scientist
cannot close the row. `data_forge/**` and the neutral IR carrier are outside this
task's allowed source paths. No source repair or owner appointment is claimed.

Cheapest correct mechanism: one independent evaluator-verification owner that
authenticates a deployment-trusted appointed key, resolves and content-binds the
complete observation set, recomputes metrics/guardrails/promotion, and replays the
champion before **both** admission and direct materialization. An independent
public key taken from the claimant's payload is not a trust root. Missing trust
leaves the typed appointment slot empty and the authority output blocked. Current
capability: `verification_missing`; runtime and materializer bridges are present
but admit unverified evidence. The claimant's batch shape is not a credential.

Exact minimal quarantine edit to hand to the DataForge owner, if immediate
containment is chosen before that capability lands (not applied here): at the
start of `load_admitted_claim_adjudication_batch`, before reading a ref or
materializing any output, add
`raise ValueError("claim_adjudication_independent_verifier_missing")`.
This closes that emission path only by an explicit missing-capability refusal;
it is **not** the row's positive closure and must not be reported as one. The full
replacement must route this same loader through the independent owner, and keep
the standalone fabricated-batch test above. A Scientist-only patch, a caller-
supplied verifier callback, or a differently named manifest producer is refused.

### GGA-PA1 — implementation and closure evidence

**GGA-PA1-S8-01 — the bounded schedule capability is built and exercised.**
The existing `value_choice_provenance.py` owner now produces a persisted admission
from a content-bound external `NormativeAuthorizationRecord`, resolves its signed
schedule and frontier, consumes that admission for the recorded selection, and
revalidates it at CAS persistence and projection. `NormativeDecisionRequest` is a
real persisted refusal output. There is no private signing key in the verifier.
The deployment trust slot defaults to empty; candidate payloads cannot populate it.

Cryptographic identity, content hashes, schema/rule version, purpose, decision role,
case, scope, mandate grant and validity interval are checked against configured
trust and bound artifacts. The private admission freezes the identities, key IDs,
input refs, trust epoch and admission time; resolve recomputes the complete record.
Separate configured identities and keys establish cryptographic separation, **not
an institutional appointment or a proof that two real-world organizations are
independent**. No real deployment trust or appointment was supplied in this lane.
The favorable tests use explicit fixture keys and grants. Empirical adequacy,
legal competence, legitimacy, optimality and wider publication authority remain
outside that verified permission and cannot be inferred from it.

The local authorization status composes narrowly: an exact verified selection
has `authorization_status=authorized`; missing, wrong-role, wrong-purpose,
wrong-scope, stale, self-signed, damaged or unresolved evidence yields `blocked`,
zero ranked recommendations, the candidate frontier and a typed request. Changing
only that status in either direction is refused. Candidate alternatives remain
available while their authorization is blocked; no policy publishability status
is promoted by this local result.

**GGA-PA1-S8-02 — the first repair was insufficient at emission.** The first
40-case green suite did not establish the whole property. Independent review
kept genuine separate signatures and a valid ranking admission, then falsified
unsigned mandate/delegation/replay references, tampered an actual disclosure DTO,
and attached broader publication/outcome authority to the signed frontier.
All six cases were red (four in 27.41 s, two in 22.12 s, exit 1). These were the
**same grade-emission class one level deeper**, not six new findings or rounds.
Under P40 the mechanism was widened once: the owner now constructs the entire
authority ceiling and the entire reviewer/machine assessment. Raw candidate
premises cannot produce P12/P15/P20/P22/P26 or integrity `pass`; those remain
`not_established`. Only independently resolved selection permission is `verified`.

One typed intake serves CAS persistence, hash-only persistence and owner projection.
It admits complete `NormativeRankingResult` mappings or standalone canonical
`ValueTradeoffDisclosureRecord` mappings. It refuses arbitrary wrappers, mixed
bundles and other raw S8 DTO families; no field-name detector purports to recognize
an authority vocabulary. The public projection uses the same normalization.
A valid standalone advisory disclosure still persists without an authority owner,
and the regression test mutates **every assessment field derived from the emitted
contract**, requiring refusal. Candidate text, rows and refs may still contain
unverified assertions, under the explicit candidate ceiling; this capability does
not substantiate them. The missing capability for wider grades is the respective
mandate/delegation/replay/evidence owner's substantive verifier, not more S8 flags.

The unchanged original six review falsifiers then passed: **6 passed, 20.61 s,
exit 0**. Delta-only review found no remaining present escape in that bounded
class; no recursive hypothetical-verifier review was added. Implementer final
source/test wave: **54 passed, six observed Pydantic warnings, 21.08 s, exit 0**
(the mirrored file plus the six independent scratch cases). Final coordinator
blast-radius and validator receipts are recorded separately below.

The three actual property-removal controls below each returned **exit 1**. Each
removes only a substantive process-local enforcement function while the DTOs,
source markers, genuine CAS artifacts and cryptographic test fixture remain.
No source file is edited by these commands. The first fails the zero-ranked
assertion with a damaged signature; the second and third fail `DID NOT RAISE`
for a forged assessment and a wrong-role `blocked` → `authorized` status.
Per-command elapsed time is `not_established`: `timeit` exits on the intended
assertion before printing a timing, so partial PTY yields are not substituted.

```sh
PYTHONPATH=src .venv/bin/python -m timeit -n 1 -r 1 -s 'import runpy; from pathlib import Path; from tempfile import TemporaryDirectory; from polisyos.runtime.quality.design_axes import value_choice_provenance as s8; checks = runpy.run_path("tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py"); s8.NormativeValueScheduleOwner._require_signature = staticmethod(lambda signature: None)' 'with TemporaryDirectory(dir="tests") as root: checks["test_invalid_authority_keeps_frontier_and_persists_typed_request"](Path(root), "signature", "p20_normative_signature_unverified")'
```

```sh
PYTHONPATH=src .venv/bin/python -m timeit -n 1 -r 1 -s 'import runpy; from pathlib import Path; from tempfile import TemporaryDirectory; from polisyos.runtime.quality.design_axes import value_choice_provenance as s8; checks = runpy.run_path("tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py"); s8._admit_normative_emission = lambda value, **kwargs: dict(value)' 'with TemporaryDirectory(dir="tests") as root: checks["test_registered_advisory_disclosure_rejects_all_modified_assessment_fields"](Path(root), "REVIEWER")'
```

```sh
PYTHONPATH=src .venv/bin/python -m timeit -n 1 -r 1 -s 'import runpy; from pathlib import Path; from tempfile import TemporaryDirectory; from polisyos.runtime.quality.design_axes import value_choice_provenance as s8; checks = runpy.run_path("tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py"); s8._admit_normative_emission = lambda value, **kwargs: dict(value)' 'with TemporaryDirectory(dir="tests") as root: checks["test_persisted_authorization_status_is_derived_from_the_verified_result"](Path(root), "role")'
```

Capability reality: typed record/request + producer + persisted admission/result
+ local recommendation/consumer bridge + current independent verification +
audience projection + substantive negative/round-trip tests are present. There
is **no production composition-root invocation or configured appointed signer**:
S8 is `implemented_but_not_orchestrated`. API/dashboard deployment is
`surface_out_of_scope` for this bounded source slice (Atlas owns the dashboard);
the callable audience projection is exercised locally. Full PA1 closure is not
asserted, because the separate empirical N8 production chain below remains missing.

**GGA-PA1-N8-01:** the complete tracked source Python set and an independent
filesystem walk (excluding caches) both contain 2,621 files; both directional
path differences and all AST parse failures are empty. Expanded name/attribute/
alias-aware inspection finds **zero production `ValueGateReceipt(...)`
constructors**. Two `ValueGateReceipt.model_validate` consumers do exist, at
`promotion_sequence.py:1530,1590`; calling those producers would be wrong.
The four `value_ready` literals are type/check positions, not emissions.

The live N8 port's successful selection path ends unconditionally at
`treatment_assignment_not_owner_derived`. The owner data profile only represents
`owner_assignment_unresolved`; the existing N7 gap represents unsatisfied routing
and cannot be reinterpreted as positive admission. The production CG2 calibration
store supplies `records=()` / `none_wired_production_freezes`. Neither the
transport solver nor N9's effect verifier produces that missing evidence.

The first targeted station failed because the worktree lacked its data symlink.
That was a setup error, **not a substantive missing-data finding**. The root then
linked the existing filesystem-read-only main `production_data` directory into
this worktree (directory `dr-xr-xr-x`, catalog `-r--r--r--`). No data was modified.
Fresh exact-node rerun:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider tests/unit/runtime/quality/test_value_gate.py::test_value_port_selects_then_routes_missing_owner_assignment_to_acquisition tests/unit/runtime/quality/test_value_gate.py::test_shaped_owner_assignment_attestation_is_not_authority tests/unit/runtime/quality/test_value_gate.py::test_shaped_relation_certificate_cannot_open_missing_value_input_lane -q
```

**Exit 0, three passed**: actual owner data and selected method reach the honest
assignment refusal; fabricated rollout and SKG declarations do not change it;
no value receipt is emitted. The field boundary now rests on a meaningful live
path, rather than a missing local file.

The existing PR1a plan (`docs/superpowers/plans/2026-09-02-gy-pr1a-data-only-promotion.md`,
§ numbered source anchors 311/396/894/1161) places the independent non-institutional
certificate producer in
`src/polisyos/data_forge/domains/academic/knowledge/skg_identity_bridge.py`, which
is absent and outside this task's write set. That is engineering authority;
**no appointment is needed for this alternative**. Older PA1 prose treating every
route as institutional is not used to stop engineering. The source/effect
certificate, production calibration, scoped Foundry dispatch, S10 support and
persisted/read-back N8 receipt must precede a truthful positive observation.
Building a downstream adapter/store shell or signing a fabricated assignment
would preserve the missing producer while making the capability look finished.
N8 remains `producer_missing + artifact_missing + bridge_missing`; its negative
consumer route is real. S8 is built independently below without changing that
empirical standing.

### GGA-DEF22 — current measurement and appointment

**GGA-DEF22-01: the prior five-clause acceptance is not freshly re-attested.**
The initial wave on the slice's unchanged source returns **five failed, zero
skipped, 28.14 s**, before the intended diagnostic assertions. Exact node set:

```sh
PYTHONPATH=src .venv/bin/python -m pytest tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py::test_cb_i01_n8_n10a_and_chronology_share_one_foundry_discriminant tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02_research_profile_names_torch_as_first_generic_case tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02a_label_and_shape_cannot_mask_two_data_generated_incompatibilities tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03_outside_closure_difference_is_diagnostic_irrelevant tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03a_novel_admitted_profile_verifies_from_owner_data -q --override-ini addopts=''
```

CB-I01 stops at `DigestPredicateMismatch`: N8's owner declaration expects
pyproject digest `803cbfb79c7727807db1c98d07413e8ef2f1b2a08929bd99bc2f8e638ee5142d`,
while the currently resolved frozen owner bytes yield
`a25bc559fb92ba39e357babc2961f4e8981b39bb51e599632a8224dcfed52484`.
The other four stop at `selected_lock_graph`; the real inner error is
`uv lock contains an ambiguous package name`. The current complete uv.lock TOML
has 418 package rows, including Pillow 10.4.0/12.3.0 and regex
2024.11.6/2026.9.3. The resolver rejects repeated names before following the
selected dependency closure. The named source property was never reached.

These are recorded station failures, **not a claim of inherited-red exclusion**:
no exact-command isolated P41 replay with a disjoint full input denominator was
produced. The earlier merge's five greens are historical receipts, not substituted
for this failed current wave. Changing toolchain owner artifacts or repairing a
lock-identity resolver is outside the grade invariant and is proposed separately.

A new removal station instead supplies novel two-package owner data directly to
the actual Foundry resolver and diagnostic. Removing only
`_calculate_dependency_distribution_cases` preserves types, rules, schema and
discriminant content identity. It removes the substantive discrimination.

```sh
GY_DEF22_REMOVE_CASES=1 PYTHONPATH=.:src .venv/bin/python -m _build.gy_grade_authority.def22_runtime_removal_probe
```

**Exit 1**: `dependency disagreement was not detected`; actual status
`not_established`, expected diagnostic `fail`. Restored fresh process:

```sh
PYTHONPATH=.:src .venv/bin/python -m _build.gy_grade_authority.def22_runtime_removal_probe
```

**Exit 0**, actual diagnostic `fail`. Both runs retain discriminant hash
`d383aba601fd2edb159bc557b55be744b25a8e5b0d5e566889ea3304a823bace`.
This demonstrates substance beyond marker presence. It does **not** re-establish
all five CB clauses, and it correctly does not turn missing discrimination into
a favorable grade. Scratch is local at `_build/gy_grade_authority/`; the earlier
file-form exploratory invocation is superseded by these module-form gates.

**GGA-DEF22-02: the registered Literal is not a self-grading escape.**
`_VerifiedProductionDataRootAccessPayload.predicate_class` is a private success
payload. `RootAccessAttestationResult` also has `RejectedAuthorityPredicate` and
`UnestablishedAuthorityPredicate` arms. Production `attest` returns unestablished.
The complete module assignment census finds three keyword assignments: line 4712
belongs to a negative mismatch, 5173 to the candidate root observer, 5423 to the
candidate runtime observer. The fourth textual occurrence is the annotation,
not a fourth payload-producing assignment. Those paths cannot be inferred from
adjacency in the file.

The actual public-token intake was exercised:

```sh
PYTHONPATH=.:src .venv/bin/python -m _build.gy_grade_authority.def22_grade_boundary_probe
```

**Exit 0**. A self-written `predicate_class="independently_reconciled"` mapping
and an empty object both fail with `wrong_token_type`; an
`object.__new__(VerifiedProductionDataRootAccess)` forgery fails with
`unminted_token`. Negative and unavailable result arms remain representable.
No success-Literal widening is warranted. This is where the motivating reading
was wrong: it treated one successful branch as the whole result vocabulary.

**GGA-DEF22-03: appointment stays empty.** Required acceptance is still by the
appointed Foundry catalog/discovery owner for exactly these bounded claims:

1. Foundry controls the purpose/profile relation.
2. Identity is dependency-only and excludes machine and production data.
3. Closure and first-case ordering are generic.
4. N8 is the sole producer and consumers share verified bytes.
5. Diagnostics cannot decide admission, gap closure, chronology, publication or promotion.
6. The missing positive authority chain remains missing.

The previous subagent ACCEPT supplies none of that institutional appointment.
This lane leaves the acceptance slot empty and makes no new authority claim.
Cheapest honest disposition: preserve the existing grade boundary, hand back the
appointment and report the current verification prerequisites. No tracked
Foundry implementation was changed.

## Final verification and delivery boundary

The corrected source was frozen before independent delta review and the final
coordinator wave. Source SHA256:
`97483776baca0e398d04270fa5968b6aff0374d5de804c517c6928d334d7b76e`;
mirrored test SHA256:
`df8b6b7abe23cca1d8b36d91264b0cc9293f9304fb64c804fc509dbb6d53331e`.
No source changes followed that review. The complete changed mechanism path set
is the existing S8 owner and its mirrored unit file; plan/journal are mandatory
companions. No forbidden tracked path or stale branch was changed.

Coordinator blast-radius gate, **exit 0, 50 passed, six observed warnings, 23.11 s**:

```sh
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py::test_layer2_s8_ranked_admission_fails_closed_while_schedule_resolver_is_absent tests/repo_quality/tools/test_policy_design_case_layer2_s8_value_choice.py::test_layer2_s8_arrow_disclosure_rows_are_required_for_multi_principal_conflict -q --override-ini addopts=''
```

Readiness validator, **exit 0**; its persisted JSON was read back with `status=pass`
and the complete finding identity set empty:

```sh
PYTHONPATH=.:src .venv/bin/python -m tools.quality.validation.check_policy_design_case_layer2_readiness --repo-root . --json-output _build/gy-grade-authority/layer2-readiness-final.json
```

The existing readiness validator's real S8 runtime subpath was then exercised
with only `build_pareto_archive` refusal removed; all source markers remain.
The before identity set is empty. After removal, **exit 1**, added identity exactly
`layer2_s8_value_schedule_resolver_absence_firewall_failed`, message
`S8 must refuse ranked admission while no value-schedule resolver exists.`;
removed identity set empty. This is a real runtime-property red, not a field-name
or count comparison. Complete station source is preserved below.

```sh
PYTHONPATH=.:src .venv/bin/python -m _build.gy_grade_authority.s8_validator_removal_probe
```

Ruff on the two changed Python paths is **exit 0**. It runs as a module using the
existing dependency runtime; that reads no other worktree's source. Formatting and
`git diff --check` also pass. No directory-wide pytest, backend verify, or CI-parity
wave was run, in accordance with this task's targeted-only requirement.

```sh
/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check src/polisyos/runtime/quality/design_axes/value_choice_provenance.py tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py
```

**GGA-GATE-01 — architecture remains red, not excluded as inherited.** The scoped
architecture gate below returned **exit 1**. Generated OpenAPI/client export waves
are intentionally omitted: they are outside this change's blast radius and the
user requires targeted checks. The readiness owner above is checked separately.
No debt/ledger checker is called, directly or indirectly.

```sh
PYTHONPATH=.:src .venv/bin/python -m tools.cli architecture guardrails check --skip-generated-checks
```

Complete finding set: deep-import baseline drift, plus these three creep edges
from `polisyos.runtime.http.services.acquisition_admission_bundle` at
`src/polisyos/runtime/http/services/acquisition_admission_bundle.py`:

- `polisyos.core.artifacts.manifest`
- `polisyos.core.artifacts.signing`
- `polisyos.core.artifacts.write_contract`

The emitted baseline diff contains those same three edge records. This gate's
input denominator includes source inventory, including our changed source, so a
zero changed-path intersection is not established; no exact slice-base isolation
replay is claimed. **Inheritance is `not_established`**, not inferred from the
foreign source path or matching failure names. These are recorded failures, not
suppressed findings and not a green architecture receipt.

Exact proposed handback to the runtime HTTP owner (outside this lane's allowed
source set): replace its three deep imports with the existing public facade,
which already re-exports these exact symbols:

```python
from polisyos.core.artifacts import (
    ArtifactGovernanceInfo,
    ArtifactManifest,
    ArtifactWriteOptions,
    Ed25519Signer,
    Ed25519Verifier,
    ProducerInfo,
    SchemaInfo,
    SignatureVerificationResult,
    SignatureVerificationStatus,
)
```

This edit is **not applied or test-verified here**. It is a proposed incidental
row `gy-acquisition-admission-deep-import-creep`, proposed owner runtime HTTP.
It requires no architecture baseline acceptance if the facade route suffices.
It does not obstruct the S8 mechanism measured above.

The failure/repair register was reopened before closeout. P31/P32/P37/P38 are
addressed by the bounded independent intake and emission; P01/P02 remain explicit
at the missing N8/production-composition boundary. P35/P36 census bindings were
independently reconciled; P40 governed the single structural review correction;
P41 prevents the architecture and DEF22 failures from becoming invented inherited
exclusions. Debt/register transcription and institutional appointments are left
to the architect. Stop at local commits and branch readback; no push is performed.

## Proposed rows and boundary handbacks

- `gy-foundry-profile-pins-drift-after-toolchain-update` — proposed owner Foundry
  catalog/discovery + GY artifact owner. Reconcile the frozen pyproject/owner pin
  and reissue its governed artifacts before reusing the five-CB receipt. Required
  architecture/tools writes are excluded here.
- `gy-foundry-lock-graph-name-uniqueness-proxy` — proposed owner Foundry
  dependency-profile resolver. Select the applicable uv package identity before
  diagnosing closure; global name uniqueness is the wrong predicate. Keep repeated
  names whose graph coordinates discriminate them as a red/green pair.
- `gy-governance-tail-admits-names-without-verdicts` — proposed owner Scientist
  governance, within GY-C2/CR5 engineering if accepted. The three requirement-level
  reds in GGA-CENSUS-01 are one class. No instance patch for empty dictionaries was
  made; verification must authenticate and consume actual judgments.
- `gy-n8-dormant-proxy-interval-certification` — proposed owner runtime/quality
  value producer. `_value_outer_set_from_foundry_result` invents 10%/0.01 proxy
  interval floors and labels the result certified. It has no source callers;
  activating it unchanged would turn a dormant helper into an authority leak.
- Adjudication DataForge intake edit: GGA-ADJ-01 above. This is a blocker of that
  row's structural repair, not a request to appoint an evaluator and not a reason
  to stop S8 work.

## Census reproducer and readback contract

Run from the worktree root. This walks the complete GY table at each pin, derives
membership from the whole historical addition, reconciles independently with the
original census block, and compares full current identity sets. It reads neither
DEBT-REGISTER nor LEDGER. Unknown status or a malformed row fails rather than
counting as absent. The script emits only recomputed documentary facts.

```python
from collections import Counter
from pathlib import Path
import re
import subprocess

path = "policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md"
historical = "73d930f8284682fafc283c2b78c54d64bbecf1dd"
def git_text(ref):
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True)
def table(text):
    section = text.split("## 8.5 Task standing (authoritative)", 1)[1].split("## 9.", 1)[0]
    expected_cells = len(next(line for line in section.splitlines()
                              if line.startswith("| id | phase | status |")).split("|"))
    rows = {}
    for line in section.splitlines():
        if not line.startswith("| `GY-"):
            continue
        cells = line.split("|")
        assert len(cells) == expected_cells, line
        key, status = cells[1].strip().strip("`"), cells[3].strip().strip("`*")
        assert key not in rows
        assert status in {"executed", "in_flight", "not_executable", "not_started", "ambiguous"}
        rows[key] = (status, line)
    return rows

before = table(git_text(historical + "^"))
after_text = git_text(historical)
after = table(after_text)
added = set(after) - set(before)
census = {key for key in added if after[key][0] != "not_started"}
block = after_text[after_text.index("| `GY-M1` "):]
block = block[:block.index("| `GY-S3` ")] + block[block.index("| `GY-S3` "):].splitlines()[0]
independent_census = set(re.findall(r"^\| `(GY-[^`]+)`", block, re.M))
assert census == independent_census
presence_only = {key for key in census if after[key][0] == "executed"}
current_text = Path(path).read_text()
current = table(current_text)
independent_current = set(re.findall(
    r"^\| `(GY-[^`]+)` \| [^|]+ \| (?:\*\*)?`?(?:executed|not_executable|not_started|ambiguous|in_flight)",
    current_text, re.M))
assert set(current) == independent_current
assert presence_only <= set(current)
assert all("not_measured" in current[key][1] for key in presence_only)
print("historical additions", len(added), Counter(after[k][0] for k in added))
print("census", len(census), "presence-only", len(presence_only))
print("current", len(current), Counter(status for status, _ in current.values()))
print("subset", sorted((key, current[key][0]) for key in presence_only))
```

The staging hook initially refused the investigation commit because the new
worktree lacked Lefthook. `corepack pnpm install --frozen-lockfile` provisioned
its local dependencies (5.2 s); no lockfile or tracked frontend path changed.
Normal hooks then passed/skipped their scoped checks and created investigation
commit `4082cd490`. Its journal was read back with `git show` from the named
branch immediately after commit. No hook bypass or ledger checker was used.

## Durable investigation station sources

The sources below preserve the local investigation stations in the branch.
They are diagnostic falsifiers, not a new passing product suite. Recreate each
at its stated path beneath `policy-engine/` and use the sole-command module
invocations recorded with its finding above. This avoids treating ignored local
scratch as the only copy of a handback's evidence. The adjudication station
reuses the existing test helper at the pinned slice base; its second case never
calls Scientist adjudication.

### `_build/gy-grade-authority/test_census_judge_station.py`

```python
from polisyos.runtime.quality.workspace.spine_repair_gates import GovernanceTailVerifier
from polisyos.scientist.nodes.builtins.governance.run_governance import _PHASE2_REQUIRED_SIX_JUDGES
import pytest

@pytest.mark.parametrize("judgment", [{}, {"verdict":"reject"}, {"verified":False}])
def test_task_c2_named_judges_do_not_issue_their_own_grade(judgment):
    # Derive the complete named-judge denominator from the runtime owner.
    # Keep every judge name, promote marker and declared completeness. Remove
    # the actual favorable verdict or replace it with an unfavorable one.
    verdict=GovernanceTailVerifier().verify(
        workspace_id="grade-station",invocation_id="forged-judge-tail",
        normative_result={"warnings":[],"model_completeness":"declared_complete"},
        judge_verdict={"composite_decision":"promote","per_judge":{
            name:judgment for name in _PHASE2_REQUIRED_SIX_JUDGES}},
    )
    assert verdict.applicability.status=="repair_required", verdict
    assert verdict.blocker is not None
```

### `_build/gy-grade-authority/test_forged_authority_station.py`

```python
from pathlib import Path
import importlib.util
import pytest
from polisyos.core.artifacts import FileSystemCAS
from polisyos.scientist.methods.autotune import ChampionRegistry
from polisyos.scientist.methods.autotune.claim_adjudication_runtime import ClaimAdjudicationRuntime
from polisyos.data_forge.domains.academic.batch.claim_adjudicator import materialize_claim_adjudication_result

spec=importlib.util.spec_from_file_location("gy_claim_helpers",Path(__file__).resolve().parents[2]/"tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py")
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

@pytest.mark.asyncio
async def test_self_stamped_evaluation_does_not_emit_publishability(tmp_path):
    store=FileSystemCAS(tmp_path/"cas")
    registry=ChampionRegistry(root=tmp_path/"registry",store=store)
    _,raw_ref=helper._input_ref(tmp_path,store)
    helper._promote_champion(store,registry)
    client=helper._FakeClient(helper._positive_candidate())
    result=await ClaimAdjudicationRuntime(store=store,registry=registry).adjudicate(raw_ref,client=client,model="candidate")
    assert result.status=="blocked", result
    assert result.result_ref is None
    assert client.calls==0

def test_same_forged_chain_cannot_materialize_without_scientist(tmp_path):
    from polisyos.core.artifacts import ArtifactWriteOptions, InputRef, ProducerInfo, SchemaInfo
    from polisyos.core.canon import CanonSpec
    from polisyos.ir.analytics.literature import AdmittedClaimAdjudicationBatch, ClaimAdjudicationResult
    store=FileSystemCAS(tmp_path/"cas")
    registry=ChampionRegistry(root=tmp_path/"registry",store=store)
    config,raw_ref=helper._input_ref(tmp_path,store)
    candidate_ref,evaluation_ref=helper._promote_champion(store,registry)
    # Construct every claimant-supplied marker, including complete CAS lineage,
    # without ever calling the Scientist adjudication runtime.
    batch=AdmittedClaimAdjudicationBatch(
        raw_input_ref=str(raw_ref.artifact_id),candidate_ref=str(candidate_ref.artifact_id),
        evaluation_ref=str(evaluation_ref.artifact_id),champion_pointer_sha256="0"*64,
        input_claim_ids=["claim-1"],results=[ClaimAdjudicationResult(
            claim_id="claim-1",openalex_id="W1",cause_variable="policy treatment",
            effect_variable="school attendance",**helper._positive_candidate())])
    result_ref=store.put_json(batch,ArtifactWriteOptions(
        kind="scientist.claim_adjudication.admitted_batch",media_type="application/json",
        schema=SchemaInfo(name="polisyos.ir.analytics.literature.AdmittedClaimAdjudicationBatch",version="1.0"),
        producer=ProducerInfo(component="polisyos.scientist.methods.autotune.claim_adjudication_runtime",version="1.0"),
        inputs=[InputRef(artifact_id=raw_ref.artifact_id,role="raw_input"),
                InputRef(artifact_id=candidate_ref.artifact_id,role="candidate"),
                InputRef(artifact_id=evaluation_ref.artifact_id,role="evaluation")]),
        canon_spec=CanonSpec(forbid_floats=False))
    with pytest.raises(ValueError,match="verification|appointment|authority"):
        materialize_claim_adjudication_result(config,result_ref,store=store)
    assert not config.claim_adjudications_path.exists()
```

### `_build/gy_grade_authority/def22_runtime_removal_probe.py`

```python
"""Standalone runtime property-removal witness; no production source is written."""

import json
import os

from polisyos.foundry.methods.catalog import dependency_profile as p
from polisyos.foundry.methods.catalog.dependency_evidence import DigestDomain, domain_digest

pyproject = b'[project]\nname="removal-probe-root"\nversion="1.0.0"\n'
lock = b'''[[package]]
name="removal-probe-root"
version="1.0.0"
source={virtual="."}
optional-dependencies={}
dependencies=[{name="probe-child"}]
[[package]]
name="probe-child"
version="1.0.0"
source={registry="https://example.invalid/simple"}
'''
declaration = p.MethodCatalogDependencyProfileDeclaration(
    schema_version="polisyos.foundry.dependency-profile.v1",
    profile_id="new-owner-data",
    root_distribution="removal-probe-root",
    extras=(),
    python_constraint=">=3.14",
    resolver_name="uv",
    resolver_version="0.9.21",
    pyproject_ref=domain_digest(DigestDomain.PYPROJECT, pyproject),
    lockfile_ref=domain_digest(DigestDomain.UV_LOCK, lock),
)
discriminant = p.resolve_dependency_discriminant(
    declaration,
    pyproject_bytes=pyproject,
    lockfile_bytes=lock,
    marker_environment={},
)
assert isinstance(discriminant, p.DependencyProfileDiscriminant), discriminant
observation = p.AmbientDependencyEnvironmentObservation(
    observation_kind="ambient",
    distributions=tuple(
        p.InstalledDistributionObservation(
            name=row.name,
            version="9999.0" if index == 0 else row.version,
        )
        for index, row in enumerate(discriminant.distributions)
    ),
)
removed = os.environ.get("GY_DEF22_REMOVE_CASES") == "1"
if removed:
    p._calculate_dependency_distribution_cases = lambda **kwargs: ()
result = p.diagnose_dependency_environment(
    discriminant=discriminant,
    observed_distributions=observation,
)
print(json.dumps({
    "source": p.__file__,
    "property_removed": removed,
    "observed_status": result.status,
    "expected_status": "fail",
    "schema_unchanged": discriminant.schema_version,
    "rule_unchanged": discriminant.rule_version,
    "discriminant_ref_unchanged": discriminant.discriminant_ref.value,
}), flush=True)
assert result.status == "fail", "dependency disagreement was not detected"
```

### `_build/gy_grade_authority/def22_grade_boundary_probe.py`

```python
"""Exercise the real Foundry root-access token intake against self-issued claims."""

import json
from typing import get_args

from polisyos.foundry.methods.catalog import dependency_authority as a

results = []
for label, forged in (
    ("self_issued_mapping", {"predicate_class": "independently_reconciled"}),
    ("empty_object", object()),
    ("unminted_exact_type", object.__new__(a.VerifiedProductionDataRootAccess)),
):
    try:
        with a._unwrap_owner_capability(forged, a._ROOT_ACCESS_SPEC):
            raise AssertionError("self-issued root-access evidence was admitted")
    except a.OwnerCapabilityFault as fault:
        results.append({"case": label, "code": fault.code.value})
arms = get_args(a.RootAccessAttestationResult)
assert a.RejectedAuthorityPredicate in arms
assert a.UnestablishedAuthorityPredicate in arms
assert results == [
    {"case": "self_issued_mapping", "code": "wrong_token_type"},
    {"case": "empty_object", "code": "wrong_token_type"},
    {"case": "unminted_exact_type", "code": "unminted_token"},
]
print(json.dumps({"source": a.__file__, "refusals": results,
                  "unfavourable_result_arms_representable": True}), flush=True)
```

### `_build/gy_grade_authority/s8_validator_removal_probe.py`

```python
"""Exercise the existing readiness validator with its real ranked-intake property removed."""
import json
from types import SimpleNamespace
from tools.quality.validation.check_policy_design_case_layer2_readiness import _validate_s8_runtime_negative_firewalls
from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

before = []
_validate_s8_runtime_negative_firewalls(before)
# Remove the ranked-intake refusal while all source DTOs, rules and markers stay.
s8.build_pareto_archive = lambda **payload: SimpleNamespace(**payload)
after = []
_validate_s8_runtime_negative_firewalls(after)
identity = lambda issue: (issue["code"], issue["message"])
before_ids, after_ids = set(map(identity, before)), set(map(identity, after))
print(json.dumps({"before": sorted(before_ids), "after": sorted(after_ids),
                  "added": sorted(after_ids - before_ids),
                  "removed": sorted(before_ids - after_ids)}, indent=2))
raise SystemExit(1 if after else 0)
```

## Continuation — extended DataForge grant

The architect's continuation closes the 21-row census and adopts the previous
investigation. Those settled findings and the stale branch are not remeasured.
The current prompt is the specification; DEBT-REGISTER/LEDGER are neither read nor
used to verify this continuation, and their checker remains prohibited.

Entry branch was clean at `d4ba9901cbcb29e5d27a71dac7b359b28fe1adec`.
Local `main` was `58f8073e44f44519003b5b10c1ccf0d38d7de43a`, one transcription
commit beyond the prompt's `5df4b16e4`; ancestry was verified first. The requested
`git merge main` fast-forwarded the existing branch to that commit. This is the
continuation measurement base, not a retroactive replacement of the original
slice base for P41. No rebase, stash, push or stale-ref change. Auxiliary worktrees:
none added at continuation entry.

### Investigation hypotheses, recorded before new measurements

- **Adjudication:** the previous dual-entry forgery is accepted evidence. With
  DataForge granted, one non-producing verifier can own signed observation-bound
  evaluation and champion replay, with both Scientist and direct DataForge intake
  consuming it. DataForge may not import Scientist; pure arithmetic must be
  extracted to the lower owner and reused, not copied or supplied as a claimant
  callback. Deployment appointment stays typed-empty. Test both entry paths and
  remove substantive verification while keeping receipt markers.
- **PA1 upstream:** a certified SKG bridge is buildable only if available stored
  evidence establishes canonical variables, independently admitted source/effect
  support, target scope and numeric uncertainty. Investigate complete relevant
  local artifact/table populations before choosing implementation or a measured
  input gap. Confidence, a compatible schema or a newly named receipt cannot
  substitute for those predicates. The already tested S8 mechanism is retained.
- **DEF22:** the lock resolver appears to collapse a universal lock by package
  name before edge marker/version/source can select its applicable identity.
  Traverse selected identities and fail on actual unresolved ambiguity; do not
  let out-of-closure duplicates decide the diagnostic. Independently trace the
  frozen owner pin to exact source bytes without weakening digest equality.
  Acceptance here means that the original five tests reach their intended
  assertions; a resulting substantive failure is reported separately.
- **Acquisition facade:** all nine bound objects used by the three offending
  import statements are already exported from `polisyos.core.artifacts`.
  Hypothesis: resolving them through that facade preserves consumer behavior and
  removes the three actual import edges without changing a baseline. A runtime
  rebind probe will substitute the facade exports and reload the real consumer;
  restoring private imports should fail that probe with all symbols still present.
  The architect supplies Atlas's inherited attribution; no new attribution census
  is needed here.

Pattern pass: P31/P32/P37/P38 govern the shared grade intake; P01/P02 distinguish a
working producer from an ungrounded carrier; P35 requires complete input sets;
P40 forbids a per-escape repair ladder; P41 keeps the original slice base for any
new inherited-red assertion. Source ownership is disjoint across adjudication,
academic knowledge/SKG, Foundry dependency-profile, and the coordinator's one HTTP
module. Shared CAS/DuckDB writes and governed artifacts will be serialized if met.
Targeted module-form gates only, with local `.venv/bin` first in PATH for literal
`python3` children. Root integrates, commits clean boundaries and reads back from
the branch. Institutional absence limits output authority, never engineering work.

### GGA-FACADE-02 — inherited import edges repaired through the existing facade

The architect's continuation supplies the inherited attribution from Atlas:
canonical finding identity differences `main_only=[]`, `base_only=[]`, with the
stated 2,626-member denominator and empty changed-path intersection. This is an
accepted handoff, not a new attribution proof invented here.

Fresh scoped source enumeration walks the complete AST of
`runtime/http/services/acquisition_admission_bundle.py` (one Python file): the
three private import statements bind nine symbols. All nine are in the complete
`core/artifacts/__init__.py` `__all__`; missing-export identity set is empty.
The repair resolves that exact symbol set through `polisyos.core.artifacts`.
No baseline or exception is changed.

New regression `test_acquisition_producer_resolves_artifact_dependencies_through_facade`
observes actual Python import requests while loading the real consumer in an
isolated child using `sys.executable`. Before repair: **exit 1, one failed,
25.71 s**, with the complete unexpected set `manifest`, `signing`,
`write_contract` beneath `polisyos.core.artifacts`. After repair, its gate plus
all six existing acquisition admission integration tests: **exit 0, seven
passed, 23.30 s**. Empty signer, wrong purpose/resource, incomplete denominator,
trusted signed readback and untrusted signer behavior are exercised unchanged.

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m pytest tests/unit/runtime/http/test_acquisition_admission_artifact_facade.py tests/integration/core_runtime/test_acquisition_admission_bundle.py -q --override-ini addopts=''
```

Actual removal control replays only this consumer's pre-facade source from the
continuation base in an isolated loader. Its markers, types and business code
remain; no worktree file or branch is reverted. The same runtime probe returns
**exit 1** and the exact three private import identities again. Ruff passes both
changed paths. Whole architecture finding sets will be read at final integration.

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m _build.gy_grade_authority.facade_removal_probe
```

### GGA-DEF22-04 — universal-lock identities, before the pin reissue

Fresh original five-node replay at unchanged continuation source: **five failed,
23.65 s, exit 1**. CB-I01 stops at `DigestPredicateMismatch`; the other four at
`selected_lock_graph`. The lock-file population is 418 complete package rows and
1,140 dependency edges; 16 edges request extras. These are graph coordinates, not
an assumption that package names are unique across a universal lock.

The canonical Foundry reducer now retains all candidates by name and resolves
selected edges by exact version/source plus declared edge/row markers. A selected
edge must resolve uniquely; conflicting selected identities, malformed selected
rows or missing marker inputs refuse. It traverses requested transitive extras
even when their package was previously seen. Out-of-closure alternatives no
longer veto the selected graph. Marker values remain declared, content-bound
inputs; no ambient platform observation is substituted. Digest equality and the
owner's frozen-source equality guard remain intact.

The first novel-lock wave was **eight failed, three passed, 214 deselected,
24.55 s**, before repair. Final focused identity/marker wave: **16 passed,
212 deselected, 24.99 s, exit 0**. Root independently reviewed the complete source
and mirrored-test delta. The mechanism's removal probe erases incoming edge
identity while retaining source SHA, schema and rule markers: **exit 1, two
failed and two passed, 8.57 s**. Restored fresh-process control: **exit 0, four
passed, one observed warning, 7.52 s**.

```sh
PATH="$PWD/.venv/bin:$PATH" GY_DEF22_REMOVE_LOCK_IDENTITY=1 PYTHONPATH=.:src .venv/bin/python -m _build.gy_grade_authority.def22_lock_removal_probe
```

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=.:src .venv/bin/python -m _build.gy_grade_authority.def22_lock_removal_probe
```

Two original CB tests now pass completely; the other two diagnostic tests reach
and pass their torch/profile assertions, then stop at the correctly enforced
uncommitted-source guard before consumer-byte assertions. A source commit is the
next prerequisite. The fifth test still needs the pin repair. This is **not yet
five-test closure** and no appointed acceptance is supplied.

A concrete, owner-decoded surgical pin proposal is prepared at
`_build/gy_grade_authority/def22-owner-pins.proposed.patch`: two current file
hashes in `architecture/production_quality/method_catalog_dependency_profiles.toml`
and two derived declaration identity fields in
`method_catalog_dependency_authority.toml`. Both are outside the prompt's write
list; the coordinator requested explicit extension while other work continues.
No architecture file has been changed at this point. Updating the pins does not
baseline an import finding or appoint an authority.

### GGA-DEF22-05 — source committed; remaining stops are owner pins

Append-only correction to the pre-commit observation above: Foundry source and
its mirrored probes were committed as `057d5f7be7b7c918f25078a89c14c26d2b95c676`
after branch-attachment verification. Both files were reread from the named
branch and matched the independently reviewed bytes. The exact original five
acceptance nodes then returned **exit 1, three failed and two passed, 23.64 s**.
The uncommitted-source guard is no longer the stopping point.

- CB-I01 stops in its producer before consumer assertions at lines 2504–2507.
- CB-I02 passes the torch and diagnostic assertions, then stops before the
  governing comparison at line 7523.
- CB-I02A passes both data-generated incompatibility assertions, then stops
  before the governing comparison and same-label checks at lines 7580–7582.
- CB-I03 and CB-I03A execute their intended assertions completely and pass.

The remaining three stop at `check_layer3_gy_value_gate_contract.py:982`,
`DigestPredicateMismatch`, against the stale owner-declaration pins. This is not
an inherited-red claim and is not five-test closure. The prepared four-value
patch has been decoded and resolved by the real owner in memory. Its application
requires the explicit architecture-file extension requested by the coordinator;
no appointment or digest-equality relaxation is involved.

### GGA-DEF22-06 — authorized pin remeasurement from committed owner inputs

The architect extended the write grant to exactly the two production-quality
TOMLs and prohibited applying the prepared patch. The new station therefore read
all input bytes from git objects at the measured merge base
`58f8073e44f44519003b5b10c1ccf0d38d7de43a`, recomputed the four authored values,
validated the resulting declaration with its owner, and only then opened the
earlier patch as a comparison target. The comparison is exact: **all four values
match; the complete proposal-difference string is empty**. The patch was not
applied or used as the source of any value.

Cause is **upstream dependency change**, not this lane or its acceptance tests.
The architect identified `2021f81d6b8178cfe31f708704b34bbc33a44b6d` and
`753e0458ad41ef362a5dd9e8ee126621c2cd1c1c`: dependency work including the Pillow
CI group, hnswlib extra, regex bump and odfpy source. Both are ancestors of this
station's merge base. At that base, `git log` names `753e0458a` as the last change
to both complete input files. The owner pins had not been remeasured after the
decided dependency changes. Updating them preserves the equality invariant.

The raw input hashes agree with the architect's measurement:

| Committed input | Bytes | Raw SHA-256 |
| --- | ---: | --- |
| `policy-engine/pyproject.toml` at the base above | 11,189 | `b420723ef2454bce7685b01ff11d7cf29399be8f31399366a2559ffae34a9c48` |
| `policy-engine/uv.lock` at the base above | 779,174 | `d409a3d90e1ddbf72ec5c64fd3031a203d3963495fc8ca5079e716b3960c6ffd` |

The two TOML field names do not identify the hash vocabulary. The declaration
decoder gives them the `PYPROJECT` and `UV_LOCK` digest domains. The declared
`dependency_evidence.domain_digest` hashes
`ASCII("polisyos.foundry." + domain + ".v1\\0") || uint64be(len(raw)) || raw`.
Thus the recomputed authored pins are `sha256:a25bc559fb92ba39e357babc2961f4e8981b39bb51e599632a8224dcfed52484`
and `sha256:ed542325c18b409047b5c81bfff3f242ca8ab6c22591b43a135d0e6caa1b4d68`;
they are not alternative raw-file hashes.

`dependency_profile.declaration_ref` canonicalizes the strict updated declaration.
Its raw canonical-byte hash gives
`declaration_artifact_id=sha256:f5f2ab920e1ea44c6c2cbb9bdc3a6da2dd7e2e7e067d23dd0dc1ee91ee000aca`;
the `PROFILE_DECLARATION` framed digest gives
`declaration_semantic_hash=sha256:016d01f2315ac1eabad0cffff17bb45a94fd63883a50eb33929cb6f7f491c56a`.
The station records the named inputs, derivation, comparison and readback in
`_build/gy_grade_authority/def22-pin-recomputation.json`.

All four capability rows are parsed and compared before and after, unchanged at
`absent/unallocated`: `owner_enforced_runtime_subtree_cutoff`,
`owner_resolved_resolution_receipt_store`, `platform_toolchain_admission`,
`production_data_trust_policy`. This lock-identity reducer does not appoint a
runtime cutoff owner, receipt store, platform admission or production trust
policy; no capability-state amendment is established by these changes.

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=.:src .venv/bin/python -m _build.gy_grade_authority.def22_recompute_pins
```

The two TOMLs were written from the computed declaration and read back. The
following test replay will report assertion reachability separately from pass,
and separately from the still-outstanding appointed acceptance.

### GGA-PA1-02 — available evidence cannot support the positive upstream grade

The hypothesis was narrower than “there are no estimates”: a positive DataForge
producer needs independently admitted treatment/outcome and estimand identity,
source-bound effect support, applicable scope and numeric uncertainty. Initial
exploration found enough numeric material to make this a real question. The
complete-set measurements below reject absence of numbers as the explanation;
they do not turn the numbers into causal authority.

Station: the continuation worktree with its existing read-only `production_data`
link; local `.venv/bin` first in PATH. Complete production-data enumeration found
6,562 files, including 27 files with academic/scholar path components (17 JSON,
three JSONL and one academic DuckDB among the other files). All eight production
DuckDB files were readable. The academic holder is 2,390,503,424 bytes and has 27
`ac_` tables; `ac_skg_span_grounded_claims` is absent from the complete table set.
JSON root keys and every JSONL record were walked rather than inferred from an
index. Four additional worktree test DuckDB files are invalid stubs: their
contents are **ambiguous/unreadable**, never four zero-evidence holders.

The separate main `_build` holder enumeration found 59 readable DuckDB files.
Its 13 academic holders have the same byte digest
`9696bc7e129300767ca3f805879ab9a17d691740b34e4c2eef974c485a077d6a`,
five tables with one row each and no span-grounding table. These existing holders
were read only; none was used as independently admitted production evidence.

Complete relational populations, with explicit denominators:

- `ac_parameter_estimates`: 62,248 estimates; 4,106 have both CI endpoints and
  4,032 have nonzero intervals. Of 919 exact UA/Ukraine country rows, 24 have
  nonzero intervals. None of those 24 satisfies the old candidate trust-score
  filter of 0.5; that filter is not adopted as an authority rule.
- `ac_causal_claims`: 7,868 rows; `ac_skg_edges`: 7,607 rows. Every row in these
  two complete tables is candidate material. The edge count also agrees with
  the separately stored `ac_skg_versions.n_edges` value of 7,607.
- `ac_article_extractions`: 137,714 claim subtrees. The complete subtree-key
  walk does not find the current `evidence_strength` axis. A separate exploratory
  nested-span key walk was reported in stdout, but its exact query was not
  retained. No span-population conclusion in this handback depends on that
  unpreserved measurement; the admitted-table and candidate-row measurements
  above are the decisive evidence.
- The L1 catalog has ten tables and 3,708,006 observations spanning 101 canonical
  variables. Exactly 94 variables have numeric UA observations with a period.
  Their exact-name intersection with all 55,176 stored SKG variable names is
  `education_outcomes`, `gdp_growth`, `health_outcomes`, `poverty_rate`,
  `tax_revenue`, `unemployment_rate`. Four are exact edge endpoints. Walking all
  7,607 edges finds two whose endpoints both belong to the 94-variable set:
  unemployment → poverty (null meta-effect) and growth → poverty (0.0
  meta-effect). Both are candidate rows.
- Running the real canonical resolver for all 94 variables yields 35 exact,
  three synonym and 56 embedding resolutions, with 93 approved. This measures
  lexical resolution, not causal identity or source/effect admission.
- The source-owner AST station walked all 2,623 Python files then present under
  `src/polisyos` (including the two new adjudication modules), with zero parse
  errors. Its seven `ValueOuterSet` construction/factory sites are four SKGQuery
  methods, the empty Foundry household result, household measurement and the N8
  proxy helper. This is the carrier's constructor denominator, not a claim that
  the repository contains no other estimator or evidence producer.

The named runtime witness is separate from those population claims. The real
`resolve_grounded_causal_prior` refuses a stored edge with
`confidence_layer_vintage`; its referenced snapshot digest is
`583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.
This was a live exception, not a persisted refusal receipt. The source-bound
intake is doing useful work that a new carrier must not bypass.

One tempting reuse does bypass it. On actual estimate
`00217008765d4f975631a764` (work `W2165913734`, health PTSD, AU/CH/NL,
tier 1, trust 0.51963, CI [4.7, 14.5]),
`SKGQuery.parameter_estimate_value_outer_set` emits `representation_status=
certified` with `assumption_status=declared` from a direct database read. The
substantive falsifier `assert value.representation_status != "certified"`
returned **exit 1** against unchanged data and code. This is an existing-property
violation probe, not a removal run for a repair made in this continuation.
The previous S8 removal evidence remains accepted and is not rerun or relabelled.

**Proposed row `skg-numeric-lowering-certifies-declared-premises`**, proposed owner
DataForge academic/knowledge SKG/value-evidence: a numerical candidate can issue
its own certified grade. This is the same authority class at another producer.
Cheapest honest close is independent resolution and binding of numeric and
identity evidence, or an explicit candidate-only ceiling. This unused alternative
does not obstruct the row's measured conclusion, so it is recorded and not added
to this repair's diff.

The existing ValueOwnerGateway supplies L1 outcome rows and explicitly unresolved
treatment assignment. The Foundry method evidence is
`contract_only_nonproduction` and not production-value eligible. Ukraine receipt
identity, lexical canonicalization and schema identity establish different
properties. Reusing any of them as treatment/estimand/causal support would issue
the grade from the claim it is meant to grade.

**Result:** the positive producer cannot be completed from the admitted inputs
available here. The missing input is source-bound independently admitted
treatment/outcome and estimand support with numeric uncertainty (or owner-issued
treatment assignment and observations), plus target population/unit/time and
measurement mapping with applicable transport/calibration evidence. DataForge
produces that world evidence, N7 admits it, N8 dispatches and persists its value
receipt, and S8 authorizes selection. No institution is appointed by describing
that engineering chain. PA1 remains open with `producer_missing`; the previously
implemented S8 authorization/persistence/ranking/refusal/projection is retained.

Successful original station bodies and the negative witness are preserved below.
The packaged replay artifact was syntax-checked, not rerun; original measurements
were separate `python -m timeit` invocations. Original wall times: inventory
1.12 ms, tables 376 ms, holders 2.02 s, academic files 99.3 ms, numeric 2.87 s,
claims 2.15 s, UA 279 ms, UA edges 64.9 ms, canonical 8.17 s, owners 10.5 s,
runtime 2.47 s. The red exited before timeit emitted a duration.
One optional metadata query attempted a spill beside the read-only holder and
failed; its metadata-key/retained-abstract counts are `not_established` and are
not used above. A first numeric query had an SQL alias parse error; the corrected
complete run is the stated numeric receipt.

### GGA-PA1-03 — independent challenge refutes the stronger impossibility claim

The conclusion in GGA-PA1-02 was too strong. Absence of admitted rows measures the
current chain; it does not prove that the DataForge producer cannot be built.
Independent source review identified existing retained-text and span-grounding
intake seams, and the following new complete source measurement then refuted
absence of usable source text. This is an append-only correction, not a reason
to discard the earlier measurements or redo the accepted S8 work.

The new station used read-only DuckDB connections with its spill directory in
this worktree's scratch. It returned exit 0. Every one of the 4,032 estimates
with a nonzero CI joins a retained work, spanning 1,468 work IDs. Of those 4,032
estimate rows, 4,029 join a nonempty abstract, 1,309 carry candidate raw context,
and 1,080 contexts occur exactly in the retained abstract. Those are complete
join denominators, not a sampled claim of source availability.

Both edges whose endpoints lie in the complete 94-variable UA observation set
come from Indonesian papers, `W2914599766` and `W2992159319`. Both abstracts are
retained; one lacks numeric uncertainty and the other reports a qualitative null
finding. UA transport is not established by that two-edge source set.

A named positive source witness, separate from the census, is `W7124317257`:
its abstract reports IVR anxiety SMD −0.77 with 95% CI [−1.32, −0.22]. Stored
candidate estimate `00f13cb02291b2ba616ebd3f` instead labels the unit `percent`
and the variable `ArtTherapyMentalHealth`. Source availability therefore opens
producer work while independently demonstrating why source-byte matching alone
must not validate the candidate's numerical and identity fields.

The next implementation decision is reuse-first: identify the missing bridge
around the existing `ingest_openalex_span_grounded_claims` and its source/semantic
verifier before adding any carrier. Source-grounded extraction, candidate-specific
causal/estimand validity and target transport remain distinct predicates. This
entry establishes buildable source work and corrects the impossibility claim;
it does not issue a positive N8 grade or claim the producer is already delivered.

### GGA-ADJ-02 — shared verifier, and the premises the first repair missed

The first implementation moved deterministic arithmetic to the lower DataForge
owner and made Scientist execution and direct DataForge materialization share a
non-producing verifier. It authenticated separately signed benchmark and raw-run
observations, recomputed metrics/guardrails/promotion and the complete batch, and
left deployment appointment slots empty. The execution receipt is necessary:
passing a valid benchmark receipt alone cannot certify arbitrarily fabricated
runtime results. CAS reads reuse the existing content-hash verification; the
hypothesis that this needed another hash implementation was rejected on source.

A fieldless, owner-minted row capability then replaced raw mapping admission at
graph/conflict consumers. Actual removal of `verify_batch` while all DTOs, CAS
artifacts and fixture signatures remained made both original negatives red:
Scientist completed with one published claim, and direct DataForge materialized
the forged batch. Each command returned exit 1 on its refusal assertion. These
first removal receipts have no retained complete wall duration; a packaged
station preserves their exact command bodies for the final-source replay.

Independent review exposed two missing premises in that first implementation.
Both were classified in writing as **the same grade-authority/content-binding
class**, rather than counted as a sequence of unrelated flag repairs.

- **Subject binding:** an authentic receipt for `c-1`, work `W1`,
  `tax_rate → employment` was borrowed at graph and conflict joins for another
  work, or `unrelated_budget → unrelated_hospital_access`, while keeping `c-1`.
  Four refusal cells failed and two matching controls passed, **exit 1, 15.68 s**.
  The graph persisted the substituted subject and the conflict artifact marked
  it publishable. No production monkeypatching or signature changes were needed.
  A token proved receipt provenance, not that the current projection was its
  subject. Comparing only the witnessed four fields would repeat this mistake:
  the signed raw input also carries text, direction, effect size, scope and
  supporting evidence that the result DTO does not fully retain.
- **Transition-basis completeness:** the real registry rejected an equal-score
  challenger to a perfect incumbent as `not_better_than_champion`. After replacing
  the mutable current pointer, accurate and genuinely fixture-signed challenger
  observations could omit the optional incumbent context, and replay accepted.
  Two controls passed and the omitted-incumbent refusal failed, **exit 1**;
  complete wall duration was not retained. Supplying the real incumbent's
  observations correctly rejected the challenger. The missing premise was not a
  false observation: this receipt schema did not establish the completeness of
  its transition basis. The existing registry retains no predecessor history.

The scoped consumer census parsed all 2,623 Python files then present beneath
`src/polisyos`, with no parse failures. Its eight named authority APIs had 13
direct calls; the two graph joins and one conflict join were the demonstrated
binding boundary. This is a scoped API-call denominator, not a declaration about
every possible future publication consumer.

The repair decision, before the next measurement: use one complete, source-bound
subject projection shared by both consumers; missing transport cannot be filled
from the trusted original to make a comparison pass. Retain the promotion basis
independently of candidate receipts, require the bound predecessor observations
when it exists, and distinguish explicit first promotion from missing history.
No reconstruction of unrecorded legacy transitions is claimed. These corrections
are batched before the next freeze. This entry records the investigation and
decision, not a claim that the corrected mechanism has passed.

### Durable continuation station sources (completed investigation)

These are exact preserved scratch sources, not fresh run receipts. Restore each Python body at its named ignored path and invoke it with `python -m`; commands and observed outcomes are recorded in the corresponding finding. The pin patch remains a proposal pending permission. No invocation here writes a governing architecture file.

`_build/gy_grade_authority/facade_removal_probe.py` — SHA-256 `cc6218eefe0110bbe8888f487c33bc83d78b49cd3a38ef839634cb7254a80265`

```python
"""Replay only the consumer's pre-facade imports inside the isolated runtime probe."""
import runpy
import subprocess

checks = runpy.run_path("tests/unit/runtime/http/test_acquisition_admission_artifact_facade.py")
real_run = subprocess.run
prefix = """
import importlib.machinery
import subprocess
original_get_code = importlib.machinery.SourceFileLoader.get_code

def pre_facade_code(self, fullname):
    if fullname == "polisyos.runtime.http.services.acquisition_admission_bundle":
        source = subprocess.check_output([
            "git", "show", "58f8073e44f44519003b5b10c1ccf0d38d7de43a:policy-engine/src/polisyos/runtime/http/services/acquisition_admission_bundle.py"
        ])
        return compile(source, self.path, "exec")
    return original_get_code(self, fullname)

importlib.machinery.SourceFileLoader.get_code = pre_facade_code
"""

def removed_facade_run(args, **kwargs):
    assert args[1] == "-c"
    return real_run([*args[:2], prefix + args[2]], **kwargs)

subprocess.run = removed_facade_run
checks["test_acquisition_producer_resolves_artifact_dependencies_through_facade"]()
```

`_build/gy_grade_authority/def22_lock_removal_probe.py` — SHA-256 `719ce7d81d78b575afa9c117f27867e83e3872f68f7012244cfa42474aa0b7c0`

```python
"""Remove exact edge selection in memory while retaining every source marker."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from polisyos.foundry.methods.catalog import dependency_profile as profile

source = Path(profile.__file__)
before = hashlib.sha256(source.read_bytes()).hexdigest()
markers_before = (
    profile.DependencyProfileDiscriminant.model_fields["schema_version"].annotation,
    profile.DependencyProfileDiscriminant.model_fields["rule_version"].annotation,
)
if os.environ.get("GY_DEF22_REMOVE_LOCK_IDENTITY") == "1":
    def first_named_row(edge, packages_by_name, marker_environment, *, used_marker_keys):
        return packages_by_name[profile.canonicalize_name(edge["name"])][0]

    profile._resolve_selected_lock_row = first_named_row
after = hashlib.sha256(source.read_bytes()).hexdigest()
assert before == after
assert markers_before == (
    profile.DependencyProfileDiscriminant.model_fields["schema_version"].annotation,
    profile.DependencyProfileDiscriminant.model_fields["rule_version"].annotation,
)
print(json.dumps({"source_sha256": before, "marker_and_source_bytes_preserved": True}))
raise SystemExit(pytest.main([
    "tests/unit/foundry/methods/test_dependency_profile.py::test_universal_lock_resolves_selected_edge_identity",
    "-q", "--override-ini", "addopts=",
]))
```

`_build/gy_grade_authority/def22_owner_pin_proposal.py` — SHA-256 `6993b1d2d2bb593eccff4066e46a27308a32739abae548be99c52ad0c3a3d337`

```python
"""Prepare a surgical proposal; never write to tracked owner artifacts."""

import difflib
import json
from pathlib import Path

from polisyos.foundry.methods.catalog.dependency_evidence import DigestDomain, domain_digest
from polisyos.foundry.methods.catalog.dependency_profile import (
    declaration_ref,
    load_dependency_profile_registry,
    decode_dependency_profile_registry_toml,
    resolve_profile_declaration_for_purpose,
)

root = Path.cwd()
profile_path = root / "architecture/production_quality/method_catalog_dependency_profiles.toml"
authority_path = root / "architecture/production_quality/method_catalog_dependency_authority.toml"
registry = load_dependency_profile_registry(profile_path)
old_profile_bytes = profile_path.read_bytes()
old_authority_bytes = authority_path.read_bytes()
original = resolve_profile_declaration_for_purpose(
    registry,
    authority_registry_bytes=old_authority_bytes,
    authority_purpose="n8_method_catalog_reconstruction",
)
proposed = original.model_copy(update={
    "pyproject_ref": domain_digest(DigestDomain.PYPROJECT, (root / "pyproject.toml").read_bytes()),
    "lockfile_ref": domain_digest(DigestDomain.UV_LOCK, (root / "uv.lock").read_bytes()),
})
old_ref, new_ref = declaration_ref(original), declaration_ref(proposed)
profile_text = old_profile_bytes.decode()
authority_text = old_authority_bytes.decode()
for field in ("pyproject_ref", "lockfile_ref"):
    old, new = getattr(original, field).value, getattr(proposed, field).value
    assert profile_text.count(old) == 1
    profile_text = profile_text.replace(old, new)
for old, new in (
    (old_ref.artifact_id, new_ref.artifact_id),
    (old_ref.semantic_hash.value, new_ref.semantic_hash.value),
):
    assert authority_text.count(old) == 1
    authority_text = authority_text.replace(old, new)
assert resolve_profile_declaration_for_purpose(
    decode_dependency_profile_registry_toml(profile_text.encode()),
    authority_registry_bytes=authority_text.encode(),
    authority_purpose="n8_method_catalog_reconstruction",
) == proposed
patch = "".join(
    "".join(difflib.unified_diff(
        before.decode().splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile="a/policy-engine/" + str(path.relative_to(root)),
        tofile="b/policy-engine/" + str(path.relative_to(root)),
    ))
    for path, before, after in (
        (profile_path, old_profile_bytes, profile_text),
        (authority_path, old_authority_bytes, authority_text),
    )
)
destination = root / "_build/gy_grade_authority/def22-owner-pins.proposed.patch"
destination.write_text(patch)
assert profile_path.read_bytes() == old_profile_bytes
assert authority_path.read_bytes() == old_authority_bytes
print(json.dumps({
    "proposed_patch": str(destination),
    "tracked_owner_artifacts_unchanged": True,
    "old_declaration_ref": old_ref.model_dump(mode="json"),
    "new_declaration_ref": new_ref.model_dump(mode="json"),
    "pyproject_ref": proposed.pyproject_ref.model_dump(mode="json"),
    "lockfile_ref": proposed.lockfile_ref.model_dump(mode="json"),
}, indent=2))
```

`_build/gy_grade_authority/def22-owner-pins.proposed.patch` — SHA-256 `9bd8b7585700ba08dbabad066108504da5989653cb116857036928a379cc2d6e`

JSON-encoded exact patch bytes (decode this string to reconstruct the patch):

```json
"--- a/policy-engine/architecture/production_quality/method_catalog_dependency_profiles.toml\n+++ b/policy-engine/architecture/production_quality/method_catalog_dependency_profiles.toml\n@@ -8,5 +8,5 @@\n python_constraint = \">=3.14,<3.15\"\n resolver_name = \"uv\"\n resolver_version = \"0.9.21\"\n-pyproject_sha256 = \"sha256:803cbfb79c7727807db1c98d07413e8ef2f1b2a08929bd99bc2f8e638ee5142d\"\n-uv_lock_sha256 = \"sha256:d3ca8737e0ce78b1deade715174576cb5449b443d96180e7029d9999d0584572\"\n+pyproject_sha256 = \"sha256:a25bc559fb92ba39e357babc2961f4e8981b39bb51e599632a8224dcfed52484\"\n+uv_lock_sha256 = \"sha256:ed542325c18b409047b5c81bfff3f242ca8ab6c22591b43a135d0e6caa1b4d68\"\n--- a/policy-engine/architecture/production_quality/method_catalog_dependency_authority.toml\n+++ b/policy-engine/architecture/production_quality/method_catalog_dependency_authority.toml\n@@ -7,8 +7,8 @@\n [[purpose_admissions]]\n authority_purpose = \"n8_method_catalog_reconstruction\"\n profile_id = \"n8-method-catalog-reconstruction-py314-uv0921-v1\"\n-declaration_artifact_id = \"sha256:c8bd2bdcef4791dc06685bbfa919aff2b0ff068f0603edded195e05d001d3e8e\"\n-declaration_semantic_hash = \"sha256:211d8fdd5454db593208abc6a5e88b516509955e0b32059f0864cbf4392bb103\"\n+declaration_artifact_id = \"sha256:f5f2ab920e1ea44c6c2cbb9bdc3a6da2dd7e2e7e067d23dd0dc1ee91ee000aca\"\n+declaration_semantic_hash = \"sha256:016d01f2315ac1eabad0cffff17bb45a94fd63883a50eb33929cb6f7f491c56a\"\n predicate_class = \"recomputed\"\n \n [[capabilities]]\n"
```

`_build/gy_grade_authority/pa1_dataforge_stations.py` — SHA-256 `8f6c9b77652f62861d09442485fb8e12bd41fdd64b8cbdf8ead482de276c027e`

```python
"""Read-only replay bodies for the PA1 DataForge investigation.

The station bodies were originally executed using ``python -m timeit``.
This replay artifact preserves their queries; its creation is not a new run.
Results describe the files present at execution, never a future branch census.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import duckdb


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, default=str))


def academic_path() -> Path:
    return next(Path("production_data").rglob("scholar_knowledge.duckdb"))


def inventory() -> None:
    root = Path("production_data")
    files = sorted(p for p in root.rglob("*") if p.is_file())
    relevant = [p for p in files if any("academic" in part or "scholar" in part for part in p.parts)]
    emit({
        "root": str(root.resolve()), "all_files": len(files),
        "academic_path_files": len(relevant),
        "academic_extensions": dict(Counter(p.suffix for p in relevant)),
        "db_files": [{"path": str(p), "size": p.stat().st_size} for p in files
                     if p.suffix in {".duckdb", ".db", ".sqlite", ".sqlite3"}],
    })


def tables() -> None:
    rows = []
    for path in sorted(Path("production_data").rglob("*.duckdb")):
        con = duckdb.connect(str(path), read_only=True)
        names = con.execute(
            "select table_name from information_schema.tables where table_schema = 'main' order by table_name"
        ).fetchall()
        academic = [name for (name,) in names if name.startswith("ac_")]
        census = []
        for name in academic:
            quoted = '"' + name.replace('"', '""') + '"'
            count = con.execute("select count(*) from " + quoted).fetchone()[0]
            columns = con.execute(
                "select column_name,data_type from information_schema.columns where table_schema='main' and table_name=? order by ordinal_position",
                [name],
            ).fetchall()
            census.append({"table": name, "rows": count, "columns": columns})
        rows.append({"path": str(path), "table_denominator": len(names),
                     "academic_table_denominator": len(academic), "academic": census})
        con.close()
    emit(rows)


def holders() -> None:
    output = []
    for root in (Path("."), Path("/Users/deniskopylov/polisyos/policy-engine/_build")):
        candidates = sorted(p for p in root.rglob("*.duckdb") if not any(part in {".venv", "node_modules", "production_data"} for part in p.parts))
        matches, rejected = [], 0
        for path in candidates:
            try:
                con = duckdb.connect(str(path), read_only=True)
                names = [r[0] for r in con.execute("select table_name from information_schema.tables where table_schema='main' order by table_name").fetchall()]
                if any(name.startswith("ac_") for name in names):
                    counts = {name: con.execute('select count(*) from "' + name.replace('"', '""') + '"').fetchone()[0] for name in names}
                    with path.open("rb") as stream:
                        digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    matches.append({"path": str(path), "sha256": digest, "tables": counts})
                con.close()
            except duckdb.Error:
                rejected += 1
        output.append({"root": str(root.resolve()), "duckdb_file_denominator": len(candidates),
                       "invalid_duckdb_files": rejected, "academic_holders": matches})
    emit(output)


def academic_files() -> None:
    root = Path("production_data")
    files = sorted(p for p in root.rglob("*") if p.is_file() and any("academic" in part or "scholar" in part for part in p.parts))
    rows = []
    for path in files:
        row = {"path": str(path), "size": path.stat().st_size, "suffix": path.suffix}
        if path.suffix == ".json":
            value = json.loads(path.read_text())
            row["root_keys"] = list(value) if isinstance(value, dict) else type(value).__name__
        elif path.suffix == ".jsonl":
            count, keys = 0, set()
            with path.open() as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    count += 1
                    if isinstance(value, dict):
                        keys.update(value)
            row.update(records=count, root_keys=sorted(keys))
        rows.append(row)
    emit({"root": str(root.resolve()), "academic_file_denominator": len(files), "files": rows})


def numeric() -> None:
    path = academic_path()
    con = duckdb.connect(str(path), read_only=True)
    queries = {
        "extraction_root_keys": "select k,count(*) from ac_article_extractions,unnest(json_keys(extraction_json)) x(k) group by k order by k",
        "parameters": "select count(*) total,count(*) filter(where ci_low is not null and ci_high is not null) with_both_ci,count(*) filter(where ci_low < ci_high) with_nonzero_ci,count(*) filter(where estimate is not null) numeric_estimates,count(*) filter(where lower(country) in ('ua','ukraine')) ukraine from ac_parameter_estimates",
        "published_claims": "select candidate_layer,strong_design_evidence,count(*) from ac_causal_claims group by all order by all",
        "edges": "select candidate_layer,evidence_strength,count(*) from ac_skg_edges group by all order by all",
        "adjudications": "select source_basis,support_status,publishable_edge,count(*) from ac_claim_adjudications group by all order by all",
        "transport_targets": "select target_context_id,count(*) from ac_skg_transport_scores group by all order by all",
        "canonization": "select resolution_method,is_approved_canonical,count(*) from ac_skg_variables group by all order by all",
        "simulation_parameter_origins": "select source_layer,uncertainty_source,count(*) from ac_skg_simulation_parameters group by all order by all",
        "version": "select * from ac_skg_versions",
    }
    print("holder", str(path))
    for key, query in queries.items():
        emit({key: con.execute(query).fetchall()})
    con.close()


def claims() -> None:
    con = duckdb.connect(str(academic_path()), read_only=True)
    queries = {
        "claim_subtree_denominator": "select count(*) from ac_article_extractions,json_each(extraction_json,'$.causal_claims')",
        "claim_subtree_keys": "select k,count(*) from ac_article_extractions,json_each(extraction_json,'$.causal_claims') claim,unnest(json_keys(claim.value)) x(k) group by k order by k",
        "claim_source_basis": "select json_extract_string(claim.value,'$.source_basis'),count(*) from ac_article_extractions,json_each(extraction_json,'$.causal_claims') claim group by all order by all",
        "claim_supporting_spans": "select json_type(claim.value,'$.supporting_spans'),count(*) from ac_article_extractions,json_each(extraction_json,'$.causal_claims') claim group by all order by all",
        "parameter_json_keys": "select k,count(*) from ac_skg_parameters,unnest(json_keys(parameter_json)) x(k) group by k order by k",
        "numeric_eligible": "select count(*) from ac_parameter_estimates where ci_low < ci_high and trust_score >= 0.5",
    }
    for key, query in queries.items():
        emit({key: con.execute(query).fetchall()})
    con.close()


def ua() -> None:
    path = next(Path("production_data").glob("datasets_*/dataset_catalog.duckdb"))
    con = duckdb.connect(str(path), read_only=True)
    names = [r[0] for r in con.execute(
        "select table_name from information_schema.tables where table_schema='main' order by table_name"
    ).fetchall()]
    counts, columns = {}, {}
    for name in names:
        counts[name] = con.execute('select count(*) from "' + name + '"').fetchone()[0]
        columns[name] = [r[0] for r in con.execute(
            "select column_name from information_schema.columns where table_name=? order by ordinal_position", [name]
        ).fetchall()]
    variables = con.execute(
        "select canonical_var,count(*) from ds_observations where country_code='UA' and value is not null and coalesce(year,survey_year,wave) is not null group by canonical_var order by canonical_var"
    ).fetchall()
    denominator = con.execute("select count(distinct canonical_var),count(*) from ds_observations").fetchone()
    academic = duckdb.connect(str(academic_path()), read_only=True)
    skg_names = {r[0] for r in academic.execute("select canonical_name from ac_skg_variables").fetchall()}
    edges = academic.execute("select src,dst from ac_skg_edges").fetchall()
    endpoints = {value for edge in edges for value in edge}
    emit({"holder": str(path), "table_denominator": len(names), "tables": counts, "columns": columns,
          "observation_variable_and_row_denominator": denominator,
          "ua_numeric_period_variable_denominator": len(variables), "ua_variables": variables,
          "exact_ua_variable_name_intersection": [(v, n) for v, n in variables if v in skg_names],
          "exact_ua_edge_endpoint_intersection": [v for v, n in variables if v in endpoints]})
    con.close()
    academic.close()


def ua_edges() -> None:
    academic = duckdb.connect(str(academic_path()), read_only=True)
    path = next(Path("production_data").glob("datasets_*/dataset_catalog.duckdb"))
    con = duckdb.connect(str(path), read_only=True)
    variables = {r[0] for r in con.execute(
        "select distinct canonical_var from ds_observations where country_code='UA' and value is not null and coalesce(year,survey_year,wave) is not null"
    ).fetchall()}
    edges = academic.execute("select edge_id,src,dst,meta_effect_size,candidate_layer from ac_skg_edges").fetchall()
    ci = academic.execute("select count(*),count(*) filter(where ci_low<ci_high),count(*) filter(where ci_low<ci_high and trust_score>=0.5) from ac_parameter_estimates where lower(country) in ('ua','ukraine')").fetchone()
    emit({"academic_edge_denominator": len(edges), "ua_numeric_owner_variables": len(variables),
          "both_endpoints_exact_ua_owner_variable": [r for r in edges if r[1] in variables and r[2] in variables],
          "exact_country_UA_estimates_total_ci_candidate_trust": ci})
    academic.close()
    con.close()


def canonical() -> None:
    from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
    path = academic_path()
    con = duckdb.connect(str(next(Path("production_data").glob("datasets_*/dataset_catalog.duckdb"))), read_only=True)
    variables = [r[0] for r in con.execute("select distinct canonical_var from ds_observations where country_code='UA' and value is not null and coalesce(year,survey_year,wave) is not null order by canonical_var").fetchall()]
    query = SKGQuery(path, path.parent.parent)
    results = [asdict(query.resolve_runtime_canonical(v, need_type="causal_edge")) for v in variables]
    emit({"ua_owner_variables_denominator": len(variables),
          "resolution_methods": dict(Counter(r["method"] for r in results)),
          "approved": sum(r["approved"] for r in results),
          "non_similarity_results": [r for r in results if r["method"] in {"exact", "exact_alias", "synonym"}]})
    query.close()
    con.close()


def owners() -> None:
    root = Path("src/polisyos")
    files = sorted(root.rglob("*.py"))
    constructors, bridges, errors = [], [], []
    def dotted(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return dotted(node.value) + "." + node.attr
        return ""
    for path in files:
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeError):
            errors.append(str(path))
            continue
        aliases = {"ValueOuterSet"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for name in node.names:
                    if name.name == "ValueOuterSet":
                        aliases.add(name.asname or name.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                target = dotted(node.func)
                parts = target.split(".")
                if any(name in parts for name in aliases) and parts[-1] in aliases | {"interval_box"}:
                    constructors.append({"path": str(path), "line": node.lineno, "call": target})
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and all(term in node.name.lower() for term in ("skg", "identity")):
                bridges.append({"path": str(path), "line": node.lineno, "name": node.name})
    emit({"source_python_denominator": len(files), "parse_errors": errors,
          "value_outer_set_constructors": constructors, "named_skg_identity_definitions": bridges})


def runtime() -> None:
    from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
    path = academic_path()
    con = duckdb.connect(str(path), read_only=True)
    edge = con.execute("select src,dst from ac_skg_edges order by edge_id limit 1").fetchone()
    estimate = con.execute("select e.id from ac_parameter_estimates e where ci_low < ci_high and trust_score >= 0.5 and exists(select 1 from ac_claim_adjudications a where a.work_id=e.work_id and a.design_quality_tier=1) order by e.id limit 1").fetchone()
    query = SKGQuery(path, path.parent.parent / "index")
    try:
        result = query.resolve_grounded_causal_prior(cause=edge[0], effect=edge[1], estimand="ATE", scope_context_id="UA", required_skg_version_id=1)
        print("grounded_prior", result)
    except ValueError as exc:
        print("grounded_prior_refusal", str(exc))
    if estimate:
        result = query.parameter_estimate_value_outer_set(estimate_id=estimate[0], world_model_record_ref="probe://not-production-wmr", epoch="probe-only")
        emit({"actual_estimate_lowering": {"estimate_id": estimate[0], "representation_status": result.representation_status,
              "assumption_status": result.assumption_status, "coordinates": result.coordinates, "lower": result.lower,
              "upper": result.upper, "calibration_scope": result.calibration_scope, "data_trust": result.data_trust.model_dump(mode="json")}})
    else:
        print("no_qualifying_estimate")
    query.close()
    con.close()


def red() -> None:
    from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
    path = academic_path()
    query = SKGQuery(path, path.parent.parent)
    value = query.parameter_estimate_value_outer_set(estimate_id="00217008765d4f975631a764", world_model_record_ref="probe://not-production-wmr", epoch="probe-only")
    assert value.representation_status != "certified", (value.representation_status, value.assumption_status, value.calibration_scope)


if __name__ == "__main__":
    stations = {function.__name__: function for function in (inventory, tables, holders, academic_files, numeric, claims, ua, ua_edges, canonical, owners, runtime, red)}
    parser = argparse.ArgumentParser()
    parser.add_argument("station", choices=tuple(stations))
    args = parser.parse_args()
    stations[args.station]()
```

### GGA-DEF22-07 — all five intended assertions execute after authorized repinning

The four fresh owner-derived values in GGA-DEF22-06 match the old proposal
exactly; the proposal was compared only after computation and was not applied.
For avoidance of an escape-notation ambiguity in that entry, the domain digest
prefix is `ASCII("polisyos.foundry." + domain + ".v1") || NUL`, followed by
`uint64be(len(raw)) || raw`. The NUL is one zero byte, not printable backslash text.
The pin update follows upstream dependency changes `753e0458a` and `2021f81d6`,
both ancestors of the measured merge base. It repairs the architect's identified
repinning omission; it does not change an invariant to accommodate this lane.

At committed pin station `03555b6e2da49e065a26726a54b6eed1118d9c21`, the exact
five-test acceptance denominator reports **5 passed, exit 0, 40.11 seconds**.
JUnit: `_build/gy_grade_authority/def22-five-after-pins.xml`.

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m pytest tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py::test_cb_i01_n8_n10a_and_chronology_share_one_foundry_discriminant tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02_research_profile_names_torch_as_first_generic_case tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02a_label_and_shape_cannot_mask_two_data_generated_incompatibilities tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03_outside_closure_difference_is_diagnostic_irrelevant tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03a_novel_admitted_profile_verifies_from_owner_data -q --override-ini addopts='' --tb=short --junitxml=_build/gy_grade_authority/def22-five-after-pins.xml
```

These execute their actual assertions: CB-I01 compares the shared N8/N10a/
chronology Foundry discriminant, content reference, profile, root and resolved
distributions; CB-I02 checks torch's diagnostic role without altering governing
bytes; CB-I02A checks two data-generated incompatibilities despite unchanged
labels/shapes; CB-I03 checks outside-closure diagnostic irrelevance; CB-I03A
verifies a novel admitted profile from owner data. The lock-identity removal
probe in GGA-DEF22-04 already goes red while markers remain. The engineering
closure requested in this continuation is met. Appointed acceptance remains
outstanding; neither this green nor the pin updates appoints anyone. All four
authored `absent/unallocated` capability states are unchanged.

### GGA-FACADE-03 — the first facade repair was one boundary too shallow

The complete architecture gate refuted the sufficiency of GGA-FACADE-02:
`polisyos.core.artifacts` is itself outside the declared supported entry points.
The actual supported `polisyos.core` facade already exports `artifacts`, so the
runtime consumer now obtains every artifact symbol through that existing object.
No implementation or baseline exception is introduced. The runtime import
observer was strengthened to require the supported root; restoring the original
consumer with all symbols present gives **exit 1**, listing exactly the three
private import requests alongside the root import. This is the same import
boundary one level deeper, not an unrelated repair.

The restored runtime facade probe plus the six existing acquisition integration
tests report **7 passed, exit 0, 26.09 seconds**; Ruff on the two changed Python
files reports an empty finding set. Commands (each invoked alone):

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m pytest tests/unit/runtime/http/test_acquisition_admission_artifact_facade.py tests/integration/core_runtime/test_acquisition_admission_bundle.py -q --override-ini addopts='' --tb=short
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m _build.gy_grade_authority.facade_removal_probe
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m ruff check src/polisyos/runtime/http/services/acquisition_admission_bundle.py tests/unit/runtime/http/test_acquisition_admission_artifact_facade.py
```

### GGA-ADJ-03 — final behavioral package and explicit gate limitations

The initial combined test collection collided on the two existing mirror test
basenames. Running the identical explicit file set with
`--import-mode=importlib` reaches **143 tests: 142 passed, one failed, exit 1,
26.95 seconds**. Complete file list is
`_build/gy_grade_authority/adjudication_final_gate.json`; JUnit is
`_build/gy_grade_authority/adjudication-final.xml`. The sole failure identity is
`tests/unit/data_forge/mirror_contracts/test_claim_adjudication.py::test_claim_adjudication_source_modules_have_static_contracts`.
It asks a source-tree filename walk for a DataForge module with exact stem
`claim_adjudication.py`, which that tree does not contain. No fake module is
added to satisfy this marker assertion. Attribution is **not_established**:
no exact slice-base replay with a disjoint input denominator has been shown.
Proposed row: `data-forge-adjudication-mirror-requires-absent-module-stem`, proposed
owner DataForge test maintainers. This does not obstruct the behavioral closure.

The frozen 20-Python-file Ruff denominator reports 116 identities, all in
`_resolve_extract_transformers.py`: F401 30, TC001 1, E501 53, F821 29, N806 1,
SIM102 2. The other 19 files have empty finding sets. These are retained in
`_build/gy_grade_authority/adjudication_ruff.json`, not baselined or described as
inherited. Changed-line disjointness is not P41 input-denominator disjointness.
Proposed row: `data-forge-resolve-transformer-lint-findings`, proposed owner
DataForge batch maintainers. Unrelated import/refactor cleanup is outside this
grade-authority diff.

The final architecture gate exposed new invalid subfacade imports in addition to
the already corrected HTTP instance. Root `core` and `data_forge.read_api`
facades offer the needed objects. Eight literature IR types lack a callable
public facade export; the IR schema catalog is descriptive reflection, not a
model resolver. That remaining file boundary is being handed back concretely,
without dynamic import tricks or absorbing findings into a baseline.

### GGA-SURFACE-01 — authorized public-surface expansion and coordination

The architect has authorized eight existing IR types to become supported through
the analytics facade via `polisyos.ir.api`, a declared supported entry point
owned by **team-polisyos**. This is a backward-compatible public-surface expansion,
not internal cleanup. The complete use census is retained in
`_build/gy_grade_authority/ir-exports-before.json`; every proposed type is used by
the shared verifier/policy/subject-replay mechanism. The existing definitions are
frozen by hashes before publication; new definitions or shape changes are not
authorized. The two IR reference pages will be written from the resulting live
facade and compared with the prepared proposal, not patched from its values.

The shared `architecture/public_surface/inventory.json` and
`docs/reference/public-surface.md` are deliberately left untouched. A parallel
lane is changing their inputs; the architect will regenerate once from the
combined merged tree. No `guardrails sync` is run. This semantic surface change
is an input to what those companions should describe; any observed stale-output
consequence is an accepted coordination condition, not a new finding.

**Additional hypothesis, recorded before its measurement:** the current global
inventory implementation may not observe this expansion at all.
`tools/devx/architecture/guardrails.py::_extract_exports` evaluates only literal
`__all__` lists; the IR analytics facade derives its list from a map. If the
read-only renderer reports no change while the runtime gains the eight types,
that would be a distinct proxy-measurement finding, not the expected temporary
companion staleness. I will compare both complete rendered outputs with their
committed versions and reconcile actual runtime exports against the facade map.
The scoped repair continues regardless; the renderer is outside this lane.

### GGA-SURFACE-02 — read-only measurement of the coordinated companions

The hypothesis in GGA-SURFACE-01 is confirmed, with a narrower and different
result than the anticipated stale-output warning. Sole command, **exit 0**:

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=.:src .venv/bin/python -m _build.gy_grade_authority.public_surface_readonly_probe > _build/gy_grade_authority/public-surface-readonly-probe.log 2>&1
```

Both complete global outputs (denominator: exactly the two coordinated companion
files) render byte-identically to the untouched current files. Inventory SHA-256:
`e083af735b7d0a5fc8a79aae5b52f57d0cfbdaf5607cdec9c7fc2884e30132d6`;
global reference-page SHA-256:
`7bbfc047903e053482deca8c6440ff18e88c78a451ba533cb850afc9ef325ac8`.
The live analytics facade has **274 exports**, independently reconciled against
all 274 keys of `ANALYTICS_FACADE_EXPORTS`, with both difference sets empty.
The global inventory records **zero** for that same facade and omits all 274
identities. This zero is the renderer's reported value, not an absence claim.
The complete omitted identity set is in
`_build/gy_grade_authority/public-surface-readonly-reconciliation.json`.

The implementation observes literal `__all__` syntax, while the property is the
callable public facade's actual exports. The eight newly supported types are a
concrete divergent case. Proposed row:
`public-surface-inventory-omits-derived-facade-exports`, proposed owner
**team-polisyos / architecture tooling**, P38. It is not the accepted temporary
staleness consequence and does not obstruct the current row. No renderer repair,
baseline change or synchronization is made. The architect's combined-tree
regeneration coordination remains in force; this observation explains why the
current renderer cannot itself evidence these eight additions.

### GGA-ADJ-04 — shared authentication and replay capability delivered

The shared owner is
`data_forge/domains/academic/batch/claim_adjudication_verifier.py::ClaimAdjudicationVerifier`.
It is non-producing: it holds separately configured evaluator public-key
appointments, CAS and the deployment registry root, and exposes verification,
not a receipt signer. The trusted appointment tuple defaults empty. The verifier
authenticates domain-bound Ed25519 receipts, resolves their complete benchmark
and execution observation sets, recomputes consensus metrics, guardrails and
the canonical promotion policy, and reconstructs every publishability result.
Both Scientist and direct DataForge admission/materialization use that owner.
Negative cases cover both entries with corrupted signatures, unappointed
signers, missing observations, forged champion metrics and declared metric drift.
A missing deployment appointment refuses both entries.

Review showed that the first implementation's quantity was too narrow in two
ways. A grade for claim ID `c-1` could be borrowed by another work or altered
causal subject; the fixed consumer binds the complete **22-field** actual input
schema and the real rich-producer transport, not a hand-maintained subset or
default-filled reconstruction. Graph and conflict consumers share this lookup.
An accurate challenger receipt could also omit its incumbent after replacement
of the public pointer, and an alternate MINIMIZE policy could demote then restore
an equal original champion. The registry now retains a deployment-owned promotion
basis, verifies the incumbent's observations, and admits only the canonical claim
policy. The baseline loader emits a candidate without creating an authority
pointer. These are the same authority-premise class widened coherently, P40.

The complete final call census walks **2,624 `src/**/*.py` files**, including the
new PA1 source module. AST call identities are reconciled against an independent
token-position derivation, with no parse errors, binding ambiguities or identity
differences. Qualified facade calls and local aliases are included. Source and
full identity sets are retained in `adjudication_final_census.py/.json`.

After the public-surface change, the explicit six-file adjudication/IR delta gate
reports **55 passed, exit 0, 31.41 seconds**. The broader preceding 143-test
package's single form-based mirror failure remains recorded in GGA-ADJ-03.
Actual shared-verifier removal was replayed through both entries after the source
batch: Scientist **exit 1**, because the real path completed and published a
claim; DataForge **exit 1**, because the forged batch materialized without the
expected refusal. The signatures, CAS, markers and test assertions were retained.
Station-body times were 0.188766 and 0.155928 seconds respectively; these exclude
imports and are not total gate durations. The separate subject, baseline-loader,
canonical-policy and retained-incumbent removal probes also go red as recorded
in their preserved modules and earlier review receipts.

This completes the capability repair within the configured verifier/CAS/registry
trust boundary. It does not appoint a production evaluator or establish real
production evaluation observations. Rewriting both registry files as a host
administrator or replacing the trusted verifier configuration is outside this
claim. Missing appointments and evidence continue to block authority.

### GGA-SURFACE-03 — actual export expansion, page derivation and removal

The eight existing types are `AdmittedClaimAdjudicationBatch`,
`ClaimAdjudicationInputBatch`, `ClaimAdjudicationInputItem`,
`ClaimAdjudicationResult`, `CausalCredibility`, `ClaimType`, `RiskOfBias` and
`SupportStatus`. Their complete use census covers the three new verifier/policy/
subject consumers; none is unused. All eight definition hashes and the entire
`ir/analytics/literature.py` hash remain unchanged. The analytics facade expands
266 to 274 exports, and its IR catalog's public type population 435 to 443.
Both approved IR pages were derived from the actual changed facade and its owner
catalog, then compared against the prepared pages: **both byte-identical, no
differences**. Measurement: `ir-reference-generation.json`.

The IR export probe resolves actual objects before consulting `__all__`.
Removing actual resolution while preserving the complete manifest and `__all__`
gives **one failure, exit 1, 0.28 seconds**, at `None is AdmittedClaimAdjudicationBatch`.
The existing generator's read-only `--check` passes. No shared global companion,
architecture baseline or type shape is changed.

The page investigation found a generation-provenance gap: the actual owner
`tools/quality/diagnostics/generate_ir_reference_catalog.py::render_ir_schema_catalog`
renders `docs/reference/ir/schema-catalog.md`; its default CLI also writes
`docs/reference/schemas.md`. Only the two approved IR pages were written here,
and `schemas.md` was compared without writing. A complete walk of the one
`architecture/generated_artifacts.toml` registry yields 61 output-bearing
families and no matching output, prefix or glob for the IR schema-catalog page.
Proposed row: `ir-schema-catalog-generator-provenance-unregistered`, proposed
owner **team-polisyos / IR documentation**. This is evidence of an existing
generator without the expected registration, not a reason to stop this row.

### GGA-PA1-04 — source-identity component, with full producer work continuing

The now-built DataForge component resolves an explicitly selected native
numeric→claim→edge-evidence→edge→article→work→version chain against separately
supplied snapshot bytes. It persists complete typed row projections to CAS and
replays them against that same independently selected subject and snapshot.
The supported academic read API exposes producer and audit/replay consumer.
Its positive status means only `source_reference_identity_recomputed`;
source authenticity, numeric semantics, native uncertainty, causal identification,
world binding, target transport and calibration are explicitly `not_established`.
N8 remains `blocked`, and `production_value_eligible` is type-constrained false.

Independent review measured four scalar-fidelity failures: Decimal rounding,
lost timestamp nanoseconds, and int→bool/float substitutions accepted by Python
model equality. A distinct fifth failure used a stored view over mutable external
CSV bytes outside the snapshot hash. The coherent correction encodes each live
native column as typed text, checks its native database round trip, compares the
entire canonical envelope, requires materialized columns in all seven base
relations, refuses an unbound WAL, and disables external reads before queries.
The guarantee is a complete native typed textual projection with a checked
relational round trip and full snapshot hash, not physical SQL-cell byte identity.

The mirrored behavioral gate reports **24 passed, 3.55 seconds**, and independent
delta review reports **5 passed, 4.04 seconds**. Ruff and format pass. Source hash:
`d305e73f8854faf647291ff3ad43215e076a7c774dbd37f7b338213955327603`;
test hash: `18c3f7fe6b26404c90cc6f33840810fbbccaa5ce6d94c35783850d05566d13ae`.
Removing joins gives **6 failed, 2 passed, exit 1, 2.26 seconds**; removing full
replay comparison gives **2 failed, 5 passed, exit 1, 1.54 seconds**; restored
selected controls give **15 passed, exit 0, 1.87 seconds**. Source hashes and
markers remain unchanged in those process-local removals.

The real retained snapshot produces and replays seven rows in **16.116321 seconds**,
persisting 56,506 bytes as
`sha256:e5025109ca9f1f09da335cefd4d05157bb94f9ef5250bbb7416016b4cc43de79`.
This worked source is W1570787406, a goat-feed experiment, with a selected estimate
25 g/day, no native CI/SE and unknown target context. It is a positive reference-
identity witness; it cannot establish a Ukrainian `avg_income` effect. A single
worked source also cannot establish insufficiency of the whole retained corpus.

**This is a clean component boundary, not the PA1 handback.** Independent scope
review rejected another premature inference: `_capture_skg` lives in the allowed
`runtime/quality/acquisition_planner.py`, and the empty production CG2 store lives
in allowed `grounding_bind.py`. Their missing wiring is engineering work, not an
external file boundary. Full-positive producer feasibility remains unestablished.
Work continues on exact-request grounding and complete independent calibration
evidence, rather than treating an empty admitted table or this goat example as a
reason to stop. No owner has been appointed.

### Durable final continuation stations

These are the exact local station modules, preserved because `_build` is ignored. They are invoked with `python -m`; removal stations intentionally return nonzero. No secret values are included. The prior stale-branch analysis remains the final section.

#### `_build/gy_grade_authority/def22_recompute_pins.py`

SHA-256 `ea13ccc6141eefc1c8f7153c6507a1f87acfeae02ff532cd9080e03fca63d963`; 4952 bytes.

````python
"""Recompute authored pins from named committed inputs, then compare proposal."""

import difflib
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

from polisyos.foundry.methods.catalog.dependency_evidence import DigestDomain, domain_digest
from polisyos.foundry.methods.catalog.dependency_profile import (
    declaration_ref,
    decode_dependency_profile_registry_toml,
    resolve_profile_declaration_for_purpose,
)

root = Path.cwd()
repo = root.parent
base = subprocess.check_output(["git", "merge-base", "HEAD", "main"], cwd=repo, text=True).strip()
assert base == "58f8073e44f44519003b5b10c1ccf0d38d7de43a"

def committed(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{base}:policy-engine/{path}"], cwd=repo)

profiles = "architecture/production_quality/method_catalog_dependency_profiles.toml"
authority = "architecture/production_quality/method_catalog_dependency_authority.toml"
before = {name: committed(name) for name in (profiles, authority)}
for name, raw in before.items():
    assert (root / name).read_bytes() == raw, name
inputs = {name: committed(name) for name in ("pyproject.toml", "uv.lock")}
for name, raw in inputs.items():
    assert (root / name).read_bytes() == raw, name
original = resolve_profile_declaration_for_purpose(
    decode_dependency_profile_registry_toml(before[profiles]),
    authority_registry_bytes=before[authority],
    authority_purpose="n8_method_catalog_reconstruction",
)
computed = original.model_copy(update={
    "pyproject_ref": domain_digest(DigestDomain.PYPROJECT, inputs["pyproject.toml"]),
    "lockfile_ref": domain_digest(DigestDomain.UV_LOCK, inputs["uv.lock"]),
})
computed = type(original).model_validate(computed.model_dump(mode="python"))
old_ref, computed_ref = declaration_ref(original), declaration_ref(computed)
after = {name: raw.decode() for name, raw in before.items()}
replacements = (
    (profiles, original.pyproject_ref.value, computed.pyproject_ref.value),
    (profiles, original.lockfile_ref.value, computed.lockfile_ref.value),
    (authority, old_ref.artifact_id, computed_ref.artifact_id),
    (authority, old_ref.semantic_hash.value, computed_ref.semantic_hash.value),
)
for name, old, new in replacements:
    assert after[name].count(old) == 1
    after[name] = after[name].replace(old, new)
assert resolve_profile_declaration_for_purpose(
    decode_dependency_profile_registry_toml(after[profiles].encode()),
    authority_registry_bytes=after[authority].encode(),
    authority_purpose="n8_method_catalog_reconstruction",
) == computed
old_capabilities = tomllib.loads(before[authority].decode())["capabilities"]
assert tomllib.loads(after[authority])["capabilities"] == old_capabilities
fresh_patch = "".join("".join(difflib.unified_diff(
    before[name].decode().splitlines(keepends=True), text.splitlines(keepends=True),
    fromfile="a/policy-engine/" + name, tofile="b/policy-engine/" + name,
)) for name, text in after.items())
# Only now read the earlier proposal, strictly as a comparison target.
proposal = (root / "_build/gy_grade_authority/def22-owner-pins.proposed.patch").read_text()
comparison = "".join(difflib.unified_diff(
    proposal.splitlines(keepends=True), fresh_patch.splitlines(keepends=True),
    fromfile="earlier-proposal", tofile="fresh-committed-input-derivation",
))
input_facts = {}
for name, raw in inputs.items():
    last_change = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", base, "--", "policy-engine/" + name],
        cwd=repo, text=True,
    ).strip()
    input_facts[name] = {"commit": base, "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(), "last_change": last_change}
upstream = {}
for revision in ("753e0458a", "2021f81d6"):
    full = subprocess.check_output(["git", "rev-parse", revision], cwd=repo, text=True).strip()
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", full, base], cwd=repo)
    assert ancestor.returncode in (0, 1)
    upstream[full] = {"ancestor_of_station_base": ancestor.returncode == 0}
receipt = {"base": base, "inputs": input_facts, "upstream_changes_named_by_architect": upstream,
           "pyproject_sha256": computed.pyproject_ref.value,
           "uv_lock_sha256": computed.lockfile_ref.value,
           "declaration_artifact_id": computed_ref.artifact_id,
           "declaration_semantic_hash": computed_ref.semantic_hash.value,
           "matches_earlier_proposal": proposal == fresh_patch,
           "proposal_difference": comparison, "unchanged_capabilities": old_capabilities}
# Write computed text, never apply/read values from the proposal.
for name, text in after.items():
    (root / name).write_text(text)
    assert (root / name).read_text() == text
destination = root / "_build/gy_grade_authority/def22-pin-recomputation.json"
destination.write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
````

#### `_build/gy_grade_authority/pa1_source_sufficiency.py`

SHA-256 `9a7b60d775d413cf296fa1c5387d457260a2e9e8427f714b8570c76bca05b029`; 3760 bytes.

````python
"""Read-only retained-source station with worktree-local DuckDB scratch."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb


def main() -> None:
    root = Path("production_data")
    paths = sorted(root.rglob("scholar_knowledge.duckdb"))
    scratch = Path("_build/gy_grade_authority/duckdb_source_sufficiency")
    scratch.mkdir(parents=True, exist_ok=True)
    if len(paths) != 1:
        raise ValueError(f"academic_holder_ambiguous:{paths}")
    con = duckdb.connect(str(paths[0]), read_only=True)
    con.execute("SET temp_directory = ?", [str(scratch.resolve())])
    con.execute("SET threads = 2")
    names = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    selected = [name for name in names if name in {
        "ac_works", "ac_article_extractions", "ac_skg_articles", "ac_skg_edge_evidence",
        "ac_skg_edges", "ac_parameter_estimates",
    }]
    schema = {name: con.execute(
        "SELECT column_name,data_type FROM information_schema.columns WHERE table_name=? ORDER BY ordinal_position",
        [name],
    ).fetchall() for name in selected}
    relevant = sorted(path for path in root.rglob("*") if path.is_file()
                      and any("academic" in part or "scholar" in part for part in path.parts))
    print(json.dumps({"holder": str(paths[0].resolve()), "table_denominator": len(names),
                      "selected_table_schemas": schema,
                      "academic_file_denominator": len(relevant),
                      "academic_files": [{"path": str(path), "size": path.stat().st_size}
                                         for path in relevant]}, indent=2))
    rows = con.execute("SELECT edge_id,src,dst,article_refs,meta_effect_size FROM ac_skg_edges "
                       "WHERE (src='unemployment_rate' AND dst='poverty_rate') "
                       "OR (src='gdp_growth' AND dst='poverty_rate')").fetchall()
    print(json.dumps({"named_target_edges": rows}, indent=2))
    work_ids = [work for row in rows for work in json.loads(row[3])]
    print(json.dumps({"named_target_sources": con.execute(
        "SELECT id,title,doi,abstract,year,full_text_url FROM ac_works WHERE id IN (SELECT unnest(?))",
        [work_ids],
    ).fetchall()}, indent=2))
    print(json.dumps({"named_target_extractions": con.execute(
        "SELECT extraction_id,work_id,extraction_json FROM ac_article_extractions WHERE work_id IN (SELECT unnest(?))",
        [work_ids],
    ).fetchall()}, indent=2))
    print(json.dumps({"numeric_source_denominator": con.execute(
        "SELECT count(*) estimate_rows,count(DISTINCT p.work_id) source_work_ids,"
        "count(*) FILTER(WHERE w.id IS NOT NULL) matched_source_rows,"
        "count(*) FILTER(WHERE length(trim(coalesce(w.abstract,'')))>0) with_retained_abstract,"
        "count(*) FILTER(WHERE length(trim(coalesce(p.raw_context,'')))>0) with_candidate_context,"
        "count(*) FILTER(WHERE length(trim(coalesce(p.raw_context,'')))>0 AND contains(w.abstract,p.raw_context)) exact_context_in_source "
        "FROM ac_parameter_estimates p LEFT JOIN ac_works w ON p.work_id=w.id WHERE p.ci_low<p.ci_high"
    ).fetchall()}, indent=2))
    print(json.dumps({"candidate_numeric_sources": con.execute(
        "SELECT p.id,p.work_id,p.variable_name,p.estimate,p.ci_low,p.ci_high,p.unit,p.raw_context,w.abstract,w.title "
        "FROM ac_parameter_estimates p JOIN ac_works w ON p.work_id=w.id "
        "WHERE p.ci_low<p.ci_high AND length(trim(coalesce(w.abstract,'')))>0 "
        "ORDER BY CASE WHEN contains(w.abstract,p.raw_context) AND length(trim(coalesce(p.raw_context,'')))>0 THEN 0 ELSE 1 END,p.id LIMIT 4"
    ).fetchall()}, indent=2))
    con.close()


if __name__ == "__main__":
    main()
````

#### `_build/gy_grade_authority/pa1_span_support_witness.py`

SHA-256 `9a9f86f4146444ccf4b68d2e63f5a7c2edf98aef5fcec2fc9a37f0cd41ee093a`; 3562 bytes.

````python
"""Exercise the real span-support owner against retained academic source bytes."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import duckdb

from polisyos.ir.analytics.literature import (
    CausalClaim, EvidenceSpan, OpenAlexWorkText, validate_causal_claim_span_grounding,
)


def main() -> None:
    owner_config = "--owner-config" in sys.argv
    if owner_config:
        env_path = Path("/Users/deniskopylov/polisyos/policy-engine/.env")
        for raw in env_path.read_text().splitlines():
            if not raw.strip() or raw.lstrip().startswith("#") or "=" not in raw:
                continue
            name, value = raw.split("=", 1)
            if name.strip() in {"POLISYOS_LLM_GATEWAY_API_KEY", "POLISYOS_LLM_GATEWAY_BASE_URL",
                                "POLISYOS_LLM_GATEWAY_MODEL", "POLISYOS_LLM_GATEWAY_SPAN_SUPPORT_MODEL"}:
                os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))
        os.environ["POLISYOS_LLM_GATEWAY_TIMEOUT_S"] = "25"
        os.environ["POLISYOS_LLM_GATEWAY_MAX_RETRIES"] = "0"
    holder = next(Path("production_data").rglob("scholar_knowledge.duckdb"))
    con = duckdb.connect(str(holder), read_only=True)
    row = con.execute(
        "SELECT id,title,abstract FROM ac_works WHERE id=?",
        ["https://openalex.org/W7124317257"],
    ).fetchone()
    con.close()
    assert row is not None
    work_id, title, abstract = row
    source = title + "\n" + abstract
    digest = hashlib.sha256(source.encode()).hexdigest()
    sentence = abstract[abstract.index("Data pooling suggested"):abstract.index(" Synthesis without")]
    start = source.index(sentence)
    work = OpenAlexWorkText(openalex_id=work_id, title=title, abstract_text=abstract,
                            source_text=source, content_sha256=digest)
    claim = CausalClaim(
        claim_id="retained-ivr-anxiety-source-witness",
        cause_variable="IVR psychological intervention", effect_variable="anxiety symptoms",
        direction="negative", claim_text="The cited review reports reduced anxiety after IVR interventions, with SMD -0.77 and 95% CI (-1.32, -0.22).",
        claim_type="causal_assertion", claim_explicitness="explicit",
        design_family_hint="rct", source_basis="abstract_only", effect_size=-0.77,
        supporting_spans=[EvidenceSpan(span_id="retained-results", section="abstract",
                                      text=sentence, source_ref=work_id,
                                      start_char=start, end_char=start+len(sentence),
                                      content_sha256=digest)],
    )
    result = validate_causal_claim_span_grounding(work, claim)
    assert source[start:start + len(sentence)] == sentence
    output = {"source_holder": str(holder.resolve()), "work_id": work_id,
              "existing_owner_config_loaded_in_process": owner_config,
              "source_sha256": digest, "span": sentence, "exact_span_dereference": True,
              "candidate_claim": claim.model_dump(mode="json"),
              "real_default_verifier_result": result.model_dump(mode="json"),
              "scope": "paper statement support only; causal validity and UA transport not established"}
    text = json.dumps(output, indent=2)
    output_name = "pa1-span-support-owner-config-output.json" if owner_config else "pa1-span-support-witness-output.json"
    Path("_build/gy_grade_authority", output_name).write_text(text+"\n")
    print(text)


if __name__ == "__main__":
    main()
````

#### `_build/gy_grade_authority/pa1_identity_real_replay.py`

SHA-256 `7497e3a61e43e0354d96f63596362b187049b626a26fc8537b67e78f13bf8540`; 1831 bytes.

````python
"""Exercise the real source-reference producer; never a positive N8 witness."""
import hashlib
import json
import time
from pathlib import Path

from polisyos.core import artifacts
from polisyos.data_forge.read_api import academic


def main():
    start = time.monotonic()
    path = next(Path('production_data').rglob('scholar_knowledge.duckdb'))
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    source = academic.SourceSnapshot(path=path, reference=str(path.resolve()), sha256=digest)
    selection = academic.SourceIdentitySelection(numeric_id='001fc1ad7237830ccb273e58',
        work_id='https://openalex.org/W1570787406', claim_id='7fd2b1e8b7ee42f5d1f21c7d',
        edge_id='66a2297da6ab82980a09e735', skg_version=1)
    scratch = Path('_build/gy_grade_authority/pa1_identity_real')
    store = artifacts.FileSystemCAS(scratch / 'cas')
    ref = academic.produce_source_identity_bundle(source=source, selection=selection,
        store=store, scratch=scratch / 'spill')
    result = academic.replay_source_identity_bundle(ref=ref, source=source, selection=selection,
        store=store, scratch=scratch / 'spill')
    output = {'artifact_ref':ref.model_dump(mode='json'), 'bundle':result.model_dump(mode='json'),
        'bundle_bytes':len(store.get_bytes(ref.artifact_id)), 'source_bytes':path.stat().st_size,
        'elapsed_seconds':time.monotonic()-start}
    Path('_build/gy_grade_authority/pa1-identity-real-replay-v2-output.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({key:value for key,value in output.items() if key!='bundle'}))
    print(json.dumps({'status':result.status, 'reasons':result.refusal_reasons,
        'n8_admission':result.n8_admission, 'row_count':len(result.rows)}))


if __name__ == '__main__':
    main()
````

#### `_build/gy_grade_authority/pa1_identity_removal.py`

SHA-256 `5a4f4872712d73eadeba3eefd61767a1e272b0aa8821cc50b0833caf8f140e84`; 1268 bytes.

````python
"""Remove runtime identity checks in memory, retaining every source marker."""
import hashlib
import os
from pathlib import Path

import pytest

from polisyos.data_forge.domains.academic.knowledge import skg_identity_bridge as bridge


def main():
    path = Path(bridge.__file__)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    mutation = os.environ.get('GY_PA1_REMOVE', '')
    if mutation == 'joins':
        bridge._require_joins = lambda rows, selection: None
    elif mutation == 'replay':
        bridge._require_same_bundle = lambda persisted, current: None
    print({'mutation': mutation or 'restored', 'source_sha256': before}, flush=True)
    result = pytest.main([
        'tests/unit/data_forge/domains/academic/knowledge/test_skg_identity_bridge.py',
        '-q', '--override-ini', 'addopts=',
        '-k', ('source_join_mismatch' if mutation == 'joins' else
               'new_valid_cas_object' if mutation == 'replay' else
               'source_join_mismatch or new_valid_cas_object'),
    ])
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    print({'source_unchanged': before == after, 'source_sha256': after}, flush=True)
    assert before == after
    raise SystemExit(result)


if __name__ == '__main__':
    main()
````

#### `_build/gy_grade_authority/test_skg_identity_scalar_review.py`

SHA-256 `a92edfa325fb545d8ae58659b246ad74a0fa6634385bd90052fc94f323912bff`; 3335 bytes.

````python
"""Independent exact-source projection and replay witnesses."""

from __future__ import annotations

import json

import duckdb
import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS, ProducerInfo, SchemaInfo
from polisyos.data_forge.domains.academic.knowledge import skg_identity_bridge as bridge
from tests.unit.data_forge.domains.academic.knowledge.test_skg_identity_bridge import (
    _owner,
    source,
)


@pytest.mark.parametrize("kind", ["decimal", "timestamp_ns"])
def test_native_scalar_is_exact_or_refused(source, tmp_path, kind):
    path, selection = source
    with duckdb.connect(str(path)) as con:
        if kind == "decimal":
            con.execute("ALTER TABLE ac_works ADD COLUMN exact_measure DECIMAL(21,20)")
            con.execute("UPDATE ac_works SET exact_measure=CAST('1.12345678901234567890' AS DECIMAL(21,20))")
            expected = {"1.12345678901234567890"}
        else:
            con.execute("ALTER TABLE ac_works ADD COLUMN exact_measure TIMESTAMP_NS")
            con.execute("UPDATE ac_works SET exact_measure=CAST('2026-09-07 01:02:03.123456789' AS TIMESTAMP_NS)")
            expected = {"2026-09-07 01:02:03.123456789", "2026-09-07T01:02:03.123456789"}
    store = FileSystemCAS(tmp_path / "cas")
    ref = bridge.produce_source_identity_bundle(source=_owner(path), selection=selection,
                                               store=store, scratch=tmp_path / "spill")
    result = bridge.replay_source_identity_bundle(ref=ref, source=_owner(path), selection=selection,
                                                 store=store, scratch=tmp_path / "spill")
    if result.status == "refused":
        assert result.refusal_reasons
        return
    row = next(row for row in result.rows if row.table == "ac_works")
    cell = next(cell for cell in row.cells if cell.name == "exact_measure")
    assert cell.value in expected, (kind, cell.database_type, cell.value)


@pytest.mark.parametrize("changed", [True, 1.0])
def test_replay_rejects_scalar_type_substitution_even_if_python_compares_equal(source, tmp_path, changed):
    path, selection = source
    store = FileSystemCAS(tmp_path / "cas")
    ref = bridge.produce_source_identity_bundle(source=_owner(path), selection=selection,
                                               store=store, scratch=tmp_path / "spill")
    payload = json.loads(store.get_bytes(ref.artifact_id))
    row = next(row for row in payload["rows"] if row["table"] == "ac_skg_versions")
    cell = next(cell for cell in row["cells"] if cell["name"] == "version_id")
    assert type(cell["value"]) is int
    assert cell["value"] == changed
    cell["value"] = changed
    # Keep the real row hash and all grade/scope markers; only its typed value changes.
    forged = store.put_bytes(json.dumps(payload).encode(), ArtifactWriteOptions(
        kind="academic.source_reference_identity", media_type="application/json",
        schema=SchemaInfo(name="academic.source_reference_identity", version="1.0"),
        producer=ProducerInfo(component="candidate", version="1")))
    with pytest.raises(ValueError, match="replay_mismatch"):
        bridge.replay_source_identity_bundle(ref=forged, source=_owner(path), selection=selection,
                                             store=store, scratch=tmp_path / "spill")
````

#### `_build/gy_grade_authority/test_skg_identity_snapshot_review.py`

SHA-256 `60427b8b8c1876afa7b2ce24469712aa5733bcacc9c0d59fb24ece950b732d6c`; 1965 bytes.

````python
"""Source identity cannot silently acquire unpinned external query inputs."""

from __future__ import annotations

import duckdb

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_forge.domains.academic.knowledge import skg_identity_bridge as bridge
from tests.unit.data_forge.domains.academic.knowledge.test_skg_identity_bridge import _owner, source


def test_snapshot_only_claim_refuses_unbound_external_relation(source, tmp_path):
    path, selection = source
    external = tmp_path / "unbound_work.csv"
    external.write_text("id,abstract\nW1,First unbound text\n")
    with duckdb.connect(str(path)) as con:
        con.execute("DROP TABLE ac_works")
        quoted = str(external).replace("'", "''")
        con.execute("CREATE VIEW ac_works AS SELECT * FROM read_csv('" + quoted + "', header=true)")
    owner = _owner(path)
    store = FileSystemCAS(tmp_path / "cas")
    first_ref = bridge.produce_source_identity_bundle(source=owner, selection=selection,
                                                     store=store, scratch=tmp_path / "spill")
    first = bridge.replay_source_identity_bundle(ref=first_ref, source=owner, selection=selection,
                                                 store=store, scratch=tmp_path / "spill")
    if first.status == "refused":
        assert first.refusal_reasons
        return
    external.write_text("id,abstract\nW1,Second unbound text\n")
    assert _owner(path).sha256 == owner.sha256
    second_ref = bridge.produce_source_identity_bundle(source=owner, selection=selection,
                                                      store=store, scratch=tmp_path / "spill")
    second = bridge.replay_source_identity_bundle(ref=second_ref, source=owner, selection=selection,
                                                  store=store, scratch=tmp_path / "spill")
    assert first.rows != second.rows
    assert second.status == "refused", (first.status, second.status, owner.sha256)
````

#### `_build/gy_grade_authority/adjudication_final_census.py`

SHA-256 `646a87bb7724057714018799951570fd9610b1e0adac0e9b588beadc9bcd84c7`; 4828 bytes.

````python
"""Complete Python census with bound facade routes and independent token call check."""
from __future__ import annotations
import ast
import io
import json
import tokenize
from collections import defaultdict
from pathlib import Path

TARGETS = {
    'load_admitted_claim_adjudication_batch', 'load_verified_claim_adjudication_rows',
    'materialize_claim_adjudication_result', 'resolve_current_claim_adjudication',
    'aggregate_claim_rows', 'claim_metrics', 'claim_guardrails', 'claim_promotion_policy',
    'metric_is_improved', 'claim_policy_publishable', 'read_claim_promotion_predecessor',
}
files = sorted(p for p in Path('src').rglob('*.py') if '__pycache__' not in p.parts)
hits = {target: [] for target in TARGETS}
errors, ambiguities, mismatches = [], [], []
for file in files:
    source = file.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        errors.append([str(file), str(exc)])
        continue
    parts = list(file.with_suffix('').parts[1:])
    module = '.'.join(parts[:-1] if parts[-1] == '__init__' else parts)
    package = parts[:-1]
    bindings = defaultdict(set)
    nodes = list(ast.walk(tree))
    for node in nodes:
        if isinstance(node, ast.ImportFrom):
            owner = '.'.join(package[:len(package)-node.level+1]) if node.level else ''
            owner = '.'.join(part for part in (owner,node.module) if part)
            for alias in node.names:
                bindings[alias.asname or alias.name].add(f'{owner}.{alias.name}')
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split('.')[0]].add(alias.name if alias.asname else alias.name.split('.')[0])
        elif isinstance(node, (ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            bindings[node.name].add(f'{module}.{node.name}')
    def resolve(node):
        if isinstance(node, ast.Name):
            return bindings.get(node.id,set())
        if isinstance(node, ast.Attribute):
            return {f'{owner}.{node.attr}' for owner in resolve(node.value)}
        return set()
    for _ in range(len(nodes)):
        changed = False
        for node in nodes:
            if isinstance(node, ast.Assign):
                values = resolve(node.value)
                for target in node.targets:
                    if isinstance(target, ast.Name) and not values <= bindings[target.id]:
                        bindings[target.id].update(values)
                        changed = True
        if not changed:
            break
    ast_positions = set()
    for node in nodes:
        if not isinstance(node,ast.Call) or not isinstance(node.func,(ast.Name,ast.Attribute)):
            continue
        leaf = node.func.id if isinstance(node.func,ast.Name) else node.func.attr
        resolutions = resolve(node.func)
        relevant = {value.rsplit('.',1)[-1] for value in resolutions} & TARGETS
        if leaf in TARGETS:
            relevant.add(leaf)
        if not relevant:
            continue
        position = (node.func.lineno, node.func.col_offset if isinstance(node.func,ast.Name)
                    else node.func.end_col_offset-len(leaf))
        ast_positions.add(position)
        item = {'file':str(file),'line':node.lineno,'call':ast.unparse(node.func),
                'bound_routes':sorted(resolutions)}
        if len(resolutions)!=1 or len(relevant)!=1:
            ambiguities.append(item)
        for target in relevant:
            hits[target].append(item)
    # A separate lexical walk settles whether the AST call filter omitted a
    # named or qualified spelling; strings/comments are not code call sites.
    spellings = TARGETS | {name for name,values in bindings.items()
                          if any(value.rsplit('.',1)[-1] in TARGETS for value in values)}
    tokens = [token for token in tokenize.generate_tokens(io.StringIO(source).readline)
              if token.type not in {tokenize.NL,tokenize.NEWLINE,tokenize.INDENT,
                                    tokenize.DEDENT,tokenize.COMMENT}]
    token_positions = {token.start for index,token in enumerate(tokens[:-1])
        if token.type==tokenize.NAME and token.string in spellings
        and tokens[index+1].string=='('
        and (index==0 or tokens[index-1].string not in {'def','class'})}
    if ast_positions != token_positions:
        mismatches.append({'file':str(file),'ast_only':sorted(ast_positions-token_positions),
                           'token_only':sorted(token_positions-ast_positions)})
result = {'denominator_file_type':'src/**/*.py excluding __pycache__',
          'denominator_count':len(files),'parse_errors':errors,'binding_ambiguities':ambiguities,
          'independent_token_mismatches':mismatches,'identity_set':hits}
print(json.dumps(result,indent=2))
````

#### `_build/gy_grade_authority/adjudication_removal_stations.py`

SHA-256 `bca6ac95a2c197ffdd1454c10c69e71469a1bf47155b9c5927ff4d83256a5e41`; 3845 bytes.

````python
"""Frozen marker-preserving adjudication removal controls.

Run from policy-engine with the local Python and PYTHONPATH=.:src:
  .venv/bin/python -m _build.gy_grade_authority.adjudication_removal_stations scientist
  .venv/bin/python -m _build.gy_grade_authority.adjudication_removal_stations data_forge

Both original timeit commands below were observed before this preservation.
The frozen module was replayed after the source batch; see REPLAY_OBSERVED.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

ORIGINAL_COMMANDS = {
    "scientist": '''PYTHONPATH=.:src .venv/bin/python -m timeit -n 1 -r 1 -s 'import asyncio; from pathlib import Path; from tempfile import TemporaryDirectory; from tests.unit.data_forge.domains.academic.batch import test_claim_adjudication_verifier as checks; from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import ClaimAdjudicationVerifier; ClaimAdjudicationVerifier.verify_batch = lambda *args, **kwargs: None' 'with TemporaryDirectory(dir="tests") as root: asyncio.run(checks.test_valid_champion_does_not_authorize_fabricated_run_result(Path(root), "scientist"))' ''',
    "data_forge": '''PYTHONPATH=.:src .venv/bin/python -m timeit -n 1 -r 1 -s 'import asyncio; from pathlib import Path; from tempfile import TemporaryDirectory; from tests.unit.data_forge.domains.academic.batch import test_claim_adjudication_verifier as checks; from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import ClaimAdjudicationVerifier; ClaimAdjudicationVerifier.verify_batch = lambda *args, **kwargs: None' 'with TemporaryDirectory(dir="tests") as root: asyncio.run(checks.test_valid_champion_does_not_authorize_fabricated_run_result(Path(root), "data_forge"))' ''',
}
OBSERVED = {
    "scientist": {
        "exit": 1,
        "duration": "not_established: timeit assertion exited before timing was printed",
        "output": "AssertionError: expected blocked; actual status='completed', input_claims=1, published_claims=1; result_ref present",
    },
    "data_forge": {
        "exit": 1,
        "duration": "not_established: timeit assertion exited before timing was printed",
        "output": "Failed: DID NOT RAISE <class 'ValueError'>; forged batch materialized",
    },
}


REPLAY_OBSERVED = {
    "scientist": {"exit": 1, "station_body_seconds": 0.036385417042765766,
                  "output": "AssertionError: completed, result_ref present, published_claims=1"},
    "data_forge": {"exit": 1, "station_body_seconds": 0.0357904169941321,
                   "output": "Failed: DID NOT RAISE ValueError; forged batch materialized"},
}
# Station timing excludes import/setup before the timer; full process duration not_established.


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("station", choices=tuple(OBSERVED))
    args = parser.parse_args()
    from tests.unit.data_forge.domains.academic.batch import test_claim_adjudication_verifier as checks
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import ClaimAdjudicationVerifier
    # The actual shared replay is removed; genuine signatures, CAS, schemas,
    # owner names, enums, receipt refs and the full assertion remain unchanged.
    ClaimAdjudicationVerifier.verify_batch = lambda *args, **kwargs: None
    started = perf_counter()
    try:
        with TemporaryDirectory(dir="tests") as root:
            asyncio.run(checks.test_valid_champion_does_not_authorize_fabricated_run_result(
                Path(root), args.station,
            ))
    finally:
        print(json.dumps({"station": args.station, "elapsed_seconds": perf_counter() - started}), flush=True)


if __name__ == "__main__":
    main()
````

#### `_build/gy_grade_authority/test_adjudication_final_removals.py`

SHA-256 `638eaedbd1201f2c3e5fe29b7675f4d0e75ed137ed40e200b9033c3b93db8e78`; 2459 bytes.

````python
"""Intentional red stations: remove runtime properties while keeping evidence/markers."""
from __future__ import annotations

import ast
import inspect
import textwrap

from tests.unit.data_forge.domains.academic.batch import (
    test_claim_adjudication_autotune as autotune_checks,
    test_claim_adjudication_subject_binding as subject_checks,
    test_claim_adjudication_verifier as intake_checks,
)


def test_subject_property_removed(tmp_path, monkeypatch):
    from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import VerifiedClaimAdjudicationRows
    # Actual signed rows are retained. Only current-subject comparison is removed.
    monkeypatch.setattr(VerifiedClaimAdjudicationRows, "for_current_subject",
                        lambda self, subject: self._read().get(subject.get("claim_id")))
    subject_checks.test_every_current_input_field_is_required_and_content_bound(tmp_path)


def test_baseline_property_removed(tmp_path, monkeypatch):
    from polisyos.scientist.methods.autotune.claim_adjudication import ClaimAdjudicationRuntimeLoader
    from polisyos.scientist.methods.autotune.runtime import ChampionBackedRuntimeLoader
    # Preserve both classes and all markers; restore the old real seeding behavior.
    monkeypatch.setattr(ClaimAdjudicationRuntimeLoader, "load", ChampionBackedRuntimeLoader.load)
    autotune_checks.test_successful_claim_promotion_changes_runtime_selection(tmp_path)


def test_canonical_policy_property_removed(tmp_path, monkeypatch):
    from polisyos.scientist.methods.autotune import registry
    original = registry.ChampionRegistry.consider_promotion
    source = ast.parse(textwrap.dedent(inspect.getsource(original)))
    removed = 0
    for node in ast.walk(source):
        if isinstance(node, ast.If) and ast.unparse(node.test) == "policy.model_dump(mode='json') != claim_promotion_policy()":
            # Keep the original rejection branch, names and messages, but delete
            # the deciding predicate in this process only.
            node.test = ast.Constant(False)
            removed += 1
    assert removed == 1
    namespace = dict(original.__globals__)
    exec(compile(ast.fix_missing_locations(source), "<policy-property-removal>", "exec"), namespace)
    monkeypatch.setattr(registry.ChampionRegistry, "consider_promotion", namespace[original.__name__])
    intake_checks.test_claim_transition_rejects_alternate_policy_without_changing_basis(tmp_path)
````

#### `_build/gy_grade_authority/test_adjudication_incumbent_delta.py`

SHA-256 `c0b1b10a5a86b6da5643f5bd88a4fc0aea713671ae0c94497e5b32a08d2158d0`; 3991 bytes.

````python
"""Delta review under a fixed deployment-owned verifier/root/appointment."""

from __future__ import annotations

import hashlib
import os

import pytest

from polisyos.core.canon import from_canonical_bytes
from polisyos.data_forge.domains.academic.batch import claim_adjudication_verifier as owner
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    persist_benchmark_evaluation,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.claim_adjudication import (
    ClaimAdjudicationSearchConfig,
    default_claim_adjudication_promotion_policy,
)
from tests.unit.data_forge.domains.academic.batch._claim_evidence import (
    canonical,
    put,
    signed_receipt,
)
from tests.unit.data_forge.domains.academic.batch.test_claim_adjudication_verifier import (
    setup_evidence,
)


def _challenger(f):
    candidate = persist_mutation_artifact(
        f.store, ClaimAdjudicationSearchConfig(passes=1, notes=["second equal-score candidate"])
    )
    evaluation = BenchmarkEvaluation.model_validate(
        from_canonical_bytes(f.store.get_bytes(f.evaluation_ref.artifact_id))
    ).model_copy(update={"candidate_ref": candidate})
    return candidate, persist_benchmark_evaluation(f.store, evaluation)


def test_real_first_promotion_replays(tmp_path):
    _, f = setup_evidence(tmp_path)
    pointer = f.verifier.replay_champion(str(f.evaluation_receipt_ref.artifact_id))
    assert pointer["candidate_ref"]["artifact_id"] == str(f.candidate_ref.artifact_id)


def test_equal_challenger_cannot_change_current_or_basis(tmp_path):
    _, f = setup_evidence(tmp_path)
    basis_path = tmp_path / "registry/claim_adjudication/promotion_basis.json"
    basis_before = basis_path.read_bytes()
    pointer_before = f.registry.get("claim_adjudication")
    candidate, evaluation = _challenger(f)
    decision = f.registry.consider_promotion(
        "claim_adjudication", candidate, evaluation,
        default_claim_adjudication_promotion_policy(),
    )
    assert not decision.promoted
    assert decision.reason == "not_better_than_champion"
    assert f.registry.get("claim_adjudication") == pointer_before
    assert basis_path.read_bytes() == basis_before
    f.verifier.replay_champion(str(f.evaluation_receipt_ref.artifact_id))


def test_legacy_pointer_without_basis_is_not_genesis(tmp_path):
    _, f = setup_evidence(tmp_path)
    # Missing legacy state is a migration condition, not an administrator attack.
    (tmp_path / "registry/claim_adjudication/promotion_basis.json").unlink()
    with pytest.raises(ValueError, match="promotion_basis_missing"):
        f.verifier.replay_champion(str(f.evaluation_receipt_ref.artifact_id))


def test_public_alias_pointer_replacement_cannot_erase_incumbent(tmp_path, monkeypatch):
    _, f = setup_evidence(tmp_path)
    candidate, evaluation = _challenger(f)
    first = f.registry.get("claim_adjudication")
    pointer = first.model_copy(update={"candidate_ref": candidate, "evaluation_ref": evaluation})
    # Ordinary public API in the same fixed root: bypass its lexical loop guard.
    f.registry.write_pointer("claim_adjudication/.", pointer)
    observations_ref = put(f.store, {**f.observations, "candidate_ref": str(candidate.artifact_id)})
    receipt = signed_receipt(f.store, {
        **f.benchmark_payload,
        "candidate_ref": str(candidate.artifact_id),
        "evaluation_ref": str(evaluation.artifact_id),
        "observations_ref": str(observations_ref.artifact_id),
        "champion_pointer_sha256": hashlib.sha256(canonical(pointer.model_dump(mode="json"))).hexdigest(),
    }, f.key)
    if os.environ.get("GY_REVIEW_REMOVE_COMPARATOR") == "1":
        # Delete the semantic admission-state resolution, keep its names/markers.
        monkeypatch.setattr(owner, "read_claim_promotion_predecessor", lambda *_args: None)
    with pytest.raises(ValueError, match="promotion_basis_pointer_mismatch"):
        f.verifier.replay_champion(str(receipt.artifact_id))
````

#### `_build/gy_grade_authority/prepare_ir_exports.py`

SHA-256 `583a827c31e5669d63bf06ca273f10b7a9e14b9c4dce40ac5e31797bcef4f2f8`; 5075 bytes.

````python
"""Build a review-only export patch; never mutate IR source or reference documents."""
from __future__ import annotations
import ast
from dataclasses import replace
import difflib
import json
from pathlib import Path

from polisyos.ir import get_ir_schema_catalog, IRExportInfo, IRPublicStatus
from tools.quality.diagnostics.generate_ir_reference_catalog import render_ir_schema_catalog, render_schema_reference

NAMES = tuple(sorted(('AdmittedClaimAdjudicationBatch','ClaimAdjudicationInputBatch',
    'ClaimAdjudicationInputItem','ClaimAdjudicationResult','CausalCredibility',
    'ClaimType','RiskOfBias','SupportStatus')))
module = 'polisyos.ir.analytics.literature'
p=Path('src/polisyos/ir/api.py'); original=p.read_text(); tree=ast.parse(original)
assignment=next(n for n in tree.body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=='ANALYTICS_FACADE_EXPORTS')
keys=[n.value for n in assignment.value.keys]
assert not set(NAMES)&set(keys)
lines=original.splitlines(keepends=True)
insertions={}
for name in NAMES:
    nextkey=next((key for key in assignment.value.keys if key.value>name),None)
    line=nextkey.lineno-1 if nextkey else assignment.end_lineno-1
    insertions.setdefault(line,[]).append(name)
for line,names in sorted(insertions.items(),reverse=True):
    lines[line:line]=[f'    "{name}": (\n        "{module}",\n        "{name}",\n    ),\n' for name in names]
changes={str(p): ''.join(lines)}
p=Path('tests/unit/ir/test_public_surface.py'); original_test=p.read_text()
changes[str(p)]=original_test+'''\n\ndef test_analytics_facade_exports_existing_adjudication_contracts() -> None:
    """Resolve the actual existing runtime types through the supported facade."""
    from polisyos.ir.analytics import literature

    names = (
'''+''.join(f'        "{name}",\n' for name in NAMES)+'''    )
    for name in names:
        assert getattr(analytics, name) is getattr(literature, name)
        assert name in analytics.__all__
'''
p=Path('docs/reference/ir/public-surface.md'); page=p.read_text()
old=f'| `polisyos.ir.analytics` | {len(keys)} | curated lazy facade |'
new=f'| `polisyos.ir.analytics` | {len(keys)+len(NAMES)} | curated lazy facade |'
assert old in page
changes[str(p)]=page.replace(old,new)
catalog=get_ir_schema_catalog()
fqns={f'{module}.{name}' for name in NAMES}
selected=[entry for entry in catalog.types if entry.fqn in fqns]
assert len(selected)==len(NAMES)
assert all(not entry.exported_from for entry in selected)
modified=replace(catalog,types=tuple(replace(entry,
    public_status=IRPublicStatus.PACKAGE_FACADE,
    exported_from=(f'polisyos.ir.analytics:{entry.name}',)) if entry.fqn in fqns else entry
    for entry in catalog.types), exports=tuple(sorted((*catalog.exports,*[
        IRExportInfo(package='polisyos.ir.analytics', export_name=name,target_fqn=f'{module}.{name}')
        for name in NAMES]),key=lambda entry:(entry.package,entry.export_name))))
# Apply only the owner-rendered changed lines to the current docs, preserving unrelated drift.
def transfer_delta(current, before, after):
    old=before.splitlines(keepends=True);new=after.splitlines(keepends=True)
    result=current
    for tag,i,j,k,l in reversed(difflib.SequenceMatcher(a=old,b=new).get_opcodes()):
        if tag=='equal':continue
        assert tag=='replace'
        context_start=i
        previous=''.join(old[context_start:j])
        while result.count(previous)>1 and context_start>0:
            context_start-=1
            previous=''.join(old[context_start:j])
        desired=''.join(old[context_start:i])+''.join(new[k:l])
        assert result.count(previous)==1,(previous,result.count(previous))
        result=result.replace(previous,desired,1)
    return result
renderers={'docs/reference/ir/schema-catalog.md':render_ir_schema_catalog,
           'docs/reference/schemas.md':render_schema_reference}
render_status={}
for name,render in renderers.items():
    before=render(catalog);after=render(modified);current=Path(name).read_text()
    render_status[name]={'current_matches_owner_render':current==before,
                         'export_delta_changes_render':before!=after}
    if before!=after:changes[name]=transfer_delta(current,before,after)
patch=''
for name,after in changes.items():
    patch+=''.join(difflib.unified_diff(Path(name).read_text().splitlines(keepends=True),
        after.splitlines(keepends=True),fromfile='a/policy-engine/'+name,tofile='b/policy-engine/'+name))
Path('_build/gy_grade_authority/ir-adjudication-exports-proposal.patch').write_text(patch)
result={'changed_paths':list(changes),'changed_path_count':len(changes),'new_exports':NAMES,
        'analytics_exports_before':len(keys),'analytics_exports_after':len(keys)+len(NAMES),
        'public_types_before':len(catalog.public_types),'public_types_after':len(modified.public_types),
        'render_status':render_status,'ir_source_written':False}
Path('_build/gy_grade_authority/ir-adjudication-exports-proposal.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
````

#### `_build/gy_grade_authority/public_surface_readonly_probe.py`

SHA-256 `4b23b72c874042387b8d7591819cd3fdd356f95fe6425dbcc690943a928c1aaf`; 1819 bytes.

````python
"""Read-only complete companion and live IR-facade reconciliation; never sync."""
from pathlib import Path
import hashlib
import json
from tools.devx.architecture import guardrails as g
from polisyos.ir import analytics
from polisyos.ir.api import ANALYTICS_FACADE_EXPORTS

manifest = g.REPO_ROOT / "architecture/public_surface/contract.toml"
policies = g._parse_public_surface(manifest)
inventory = g.build_public_surface_inventory(policies)
families = g._parse_public_generated_artifact_families(manifest)
outputs = {
 "architecture/public_surface/inventory.json": g.render_public_surface_json(inventory, generated_artifact_families=families),
 "docs/reference/public-surface.md": g.render_public_surface_markdown(inventory),
}
result = {"companion_denominator": len(outputs), "outputs": {}}
for name, expected in outputs.items():
 raw = Path(name).read_bytes(); computed = expected.encode()
 result["outputs"][name] = {"matches_current": raw == computed,
  "current_sha256": hashlib.sha256(raw).hexdigest(), "rendered_sha256": hashlib.sha256(computed).hexdigest()}
entry = next(entry for package in inventory for entry in package.entrypoints if entry.module == "polisyos.ir.analytics")
actual = set(analytics.__all__); independently_derived = set(ANALYTICS_FACADE_EXPORTS)
result["analytics_export_reconciliation"] = {
 "runtime_count": len(actual), "map_count": len(independently_derived),
 "runtime_only": sorted(actual - independently_derived), "map_only": sorted(independently_derived - actual),
 "inventory_count": entry.export_count, "omitted_identity_set": sorted(actual - set(entry.exports)),
 "invented_identity_set": sorted(set(entry.exports) - actual),
}
text = json.dumps(result, indent=2) + "\n"
Path("_build/gy_grade_authority/public-surface-readonly-reconciliation.json").write_text(text)
print(text)
````

#### `_build/gy_grade_authority/write_ir_exposure_reference.py`

SHA-256 `d25e2058233288c23a106a0dbd07bd8f58c3370b7bb27d3dd0f236fa35183430`; 2609 bytes.

````python
"""Write only the two granted reference pages from actual facade exposure."""
from __future__ import annotations
import ast
import difflib
import hashlib
import json
from pathlib import Path
import re

import polisyos.ir.analytics as analytics
from polisyos.ir import get_ir_schema_catalog
from polisyos.ir.api import PACKAGE_FACADE_IMPORT_POLICY
from tools.quality.diagnostics.generate_ir_reference_catalog import (
    render_ir_schema_catalog, render_schema_reference,
)

before=json.loads(Path('_build/gy_grade_authority/ir-exports-before.json').read_text())
typefile=Path(before['existing_type_source'])
assert hashlib.sha256(typefile.read_bytes()).hexdigest()==before['source_sha256']
resolved={name:getattr(analytics,name) for name in analytics.__all__}
catalog=get_ir_schema_catalog()
page=Path('docs/reference/ir/public-surface.md')
text=page.read_text()
replacement=f'| `polisyos.ir.analytics` | {len(resolved)} | {PACKAGE_FACADE_IMPORT_POLICY["analytics"]} |'
text,count=re.subn(r'^\| `polisyos\.ir\.analytics` \| \d+ \| [^\n]+$',replacement,text,flags=re.M)
assert count==1
outputs={str(page):text,'docs/reference/ir/schema-catalog.md':render_ir_schema_catalog(catalog)}
report={'existing_types_unchanged':True,'actual_resolved_analytics_export_count':len(resolved),
        'generator_path':'tools/quality/diagnostics/generate_ir_reference_catalog.py',
        'generator_function':'render_ir_schema_catalog(get_ir_schema_catalog())',
        'documented_cli':'PYTHONPATH=src .venv/bin/python -m tools.quality.diagnostics.generate_ir_reference_catalog',
        'cli_write_scope_note':'Default CLI writes schema-catalog.md and schemas.md. This bounded invocation writes only granted schema-catalog.md; schemas.md is compared without writing.',
        'public_surface_derivation':'Actual resolved analytics.__all__ exposure, with PACKAGE_FACADE_IMPORT_POLICY; authored narrative retained.',
        'schemas_md_unchanged':render_schema_reference(catalog)==Path('docs/reference/schemas.md').read_text(),
        'proposal_comparison':{}}
for name,content in outputs.items():
    proposal=Path('_build/gy_grade_authority/proposed-'+Path(name).name).read_text()
    difference=''.join(difflib.unified_diff(proposal.splitlines(keepends=True),content.splitlines(keepends=True),fromfile='prepared/'+name,tofile='actual/'+name))
    report['proposal_comparison'][name]={'identical':proposal==content,'difference':difference}
    Path(name).write_text(content)
Path('_build/gy_grade_authority/ir-reference-generation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
````

#### `_build/gy_grade_authority/test_ir_export_resolution_removal.py`

SHA-256 `4e3a0b41868391ed1e8c0e7e5d3be0b5dc8ac35c4ef8213dfe87496ef86e1467`; 1116 bytes.

````python
"""Intentional red: facade names/manifest remain while actual resolution is removed."""
import polisyos.ir.analytics as analytics
from polisyos.ir.api import ANALYTICS_FACADE_EXPORTS
from tests.unit.ir import test_public_surface as checks


def test_remove_actual_export_resolution_keep_all_markers(monkeypatch):
    names = {
        'AdmittedClaimAdjudicationBatch', 'CausalCredibility',
        'ClaimAdjudicationInputBatch', 'ClaimAdjudicationInputItem',
        'ClaimAdjudicationResult', 'ClaimType', 'RiskOfBias', 'SupportStatus',
    }
    original_names = tuple(analytics.__all__)
    original_manifest = dict(ANALYTICS_FACADE_EXPORTS)
    original_resolver = analytics.__getattr__
    for name in names:
        monkeypatch.delattr(analytics, name, raising=False)
    def unavailable(name):
        return None if name in names else original_resolver(name)
    monkeypatch.setattr(analytics, '__getattr__', unavailable)
    assert tuple(analytics.__all__) == original_names
    assert ANALYTICS_FACADE_EXPORTS == original_manifest
    checks.test_analytics_facade_exports_existing_adjudication_contracts()
````

#### `_build/gy_grade_authority/test_skg_identity_scalar_delta.py`

SHA-256 `7f76fecdbf0c567245af122c73464616b125a8380fda4aa43ebcdd03bc9b1f7b`; 1777 bytes.

````python
"""Original scalar witnesses adapted only to the explicit native-text encoding."""

import json

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS, ProducerInfo, SchemaInfo
from polisyos.data_forge.domains.academic.knowledge import skg_identity_bridge as bridge
from tests.unit.data_forge.domains.academic.knowledge.test_skg_identity_bridge import _owner, source
from _build.gy_grade_authority.test_skg_identity_scalar_review import (
    test_native_scalar_is_exact_or_refused,
)


@pytest.mark.parametrize("changed", [True, 1.0])
def test_replay_rejects_nontext_scalar_substitution(source, tmp_path, changed):
    path, selection = source
    store = FileSystemCAS(tmp_path / "cas")
    ref = bridge.produce_source_identity_bundle(source=_owner(path), selection=selection,
                                               store=store, scratch=tmp_path / "spill")
    payload = json.loads(store.get_bytes(ref.artifact_id))
    row = next(row for row in payload["rows"] if row["table"] == "ac_skg_versions")
    cell = next(cell for cell in row["cells"] if cell["name"] == "version_id")
    assert cell["value"] == "1"
    assert cell["encoding"] == "duckdb_varchar_roundtrip"
    cell["value"] = changed
    forged = store.put_bytes(json.dumps(payload).encode(), ArtifactWriteOptions(
        kind="academic.source_reference_identity", media_type="application/json",
        schema=SchemaInfo(name="academic.source_reference_identity", version="1.0"),
        producer=ProducerInfo(component="candidate", version="1")))
    with pytest.raises(ValueError):
        bridge.replay_source_identity_bundle(ref=forged, source=_owner(path), selection=selection,
                                             store=store, scratch=tmp_path / "spill")
````

#### Exact proposed IR facade handback

SHA-256 `c20a9be78c0ab94a5e23a25933725b00977ee4441982c290da3c7cefda6a03cc`. This is a proposed out-of-scope patch, not authorization to apply it.

````json
"--- a/policy-engine/src/polisyos/ir/api.py\n+++ b/policy-engine/src/polisyos/ir/api.py\n@@ -186,6 +186,10 @@\n \n ANALYTICS_FACADE_EXPORTS: dict[str, tuple[str, str]] = {\n     \"AccessTier\": (\"polisyos.ir.analytics.data_views\", \"AccessTier\"),\n+    \"AdmittedClaimAdjudicationBatch\": (\n+        \"polisyos.ir.analytics.literature\",\n+        \"AdmittedClaimAdjudicationBatch\",\n+    ),\n     \"BacktestReport\": (\"polisyos.ir.analytics.backtest\", \"BacktestReport\"),\n     \"BacktestScenario\": (\"polisyos.ir.analytics.backtest\", \"BacktestScenario\"),\n     \"BiasDirection\": (\"polisyos.ir.analytics.backtest\", \"BiasDirection\"),\n@@ -223,6 +227,10 @@\n     ),\n     \"ABMResult\": (\"polisyos.ir.analytics.phase4_dynamics\", \"ABMResult\"),\n     \"ABMResultRef\": (\"polisyos.ir.registry.refs\", \"ABMResultRef\"),\n+    \"CausalCredibility\": (\n+        \"polisyos.ir.analytics.literature\",\n+        \"CausalCredibility\",\n+    ),\n     \"CausalDiscoveryReport\": (\n         \"polisyos.ir.analytics.causal_discovery\",\n         \"CausalDiscoveryReport\",\n@@ -250,6 +258,22 @@\n     \"CausalEdge\": (\"polisyos.ir.analytics.causal_graph\", \"CausalEdge\"),\n     \"CausalEffectReport\": (\"polisyos.ir.analytics.causal\", \"CausalEffectReport\"),\n     \"CausalGraphModel\": (\"polisyos.ir.analytics.causal_graph\", \"CausalGraphModel\"),\n+    \"ClaimAdjudicationInputBatch\": (\n+        \"polisyos.ir.analytics.literature\",\n+        \"ClaimAdjudicationInputBatch\",\n+    ),\n+    \"ClaimAdjudicationInputItem\": (\n+        \"polisyos.ir.analytics.literature\",\n+        \"ClaimAdjudicationInputItem\",\n+    ),\n+    \"ClaimAdjudicationResult\": (\n+        \"polisyos.ir.analytics.literature\",\n+        \"ClaimAdjudicationResult\",\n+    ),\n+    \"ClaimType\": (\n+        \"polisyos.ir.analytics.literature\",\n+        \"ClaimType\",\n+    ),\n     \"ClaimVocabularyAxisStatus\": (\n         \"polisyos.ir.analytics.literature\",\n         \"ClaimVocabularyAxisStatus\",\n@@ -308,6 +332,10 @@\n         \"polisyos.ir.analytics.dependent_sensitivity\",\n         \"DependentSensitivityResultRef\",\n     ),\n+    \"RiskOfBias\": (\n+        \"polisyos.ir.analytics.literature\",\n+        \"RiskOfBias\",\n+    ),\n     \"SensitivityAnalysisBundle\": (\n         \"polisyos.ir.analytics.sensitivity\",\n         \"SensitivityAnalysisBundle\",\n@@ -317,6 +345,10 @@\n         \"SensitivityAnalysisIndex\",\n     ),\n     \"SourceBasis\": (\"polisyos.ir.analytics.literature\", \"SourceBasis\"),\n+    \"SupportStatus\": (\n+        \"polisyos.ir.analytics.literature\",\n+        \"SupportStatus\",\n+    ),\n     \"load_dependent_sensitivity_result\": (\n         \"polisyos.ir.analytics.dependent_sensitivity\",\n         \"load_dependent_sensitivity_result\",\n--- a/policy-engine/tests/unit/ir/test_public_surface.py\n+++ b/policy-engine/tests/unit/ir/test_public_surface.py\n@@ -225,3 +225,22 @@\n     repo_root = Path(__file__).resolve().parents[3]\n     index_page = repo_root / \"docs\" / \"reference\" / \"ir\" / \"index.md\"\n     assert \"[Public Surface](public-surface.md)\" in index_page.read_text(encoding=\"utf-8\")\n+\n+\n+def test_analytics_facade_exports_existing_adjudication_contracts() -> None:\n+    \"\"\"Resolve the actual existing runtime types through the supported facade.\"\"\"\n+    from polisyos.ir.analytics import literature\n+\n+    names = (\n+        \"AdmittedClaimAdjudicationBatch\",\n+        \"CausalCredibility\",\n+        \"ClaimAdjudicationInputBatch\",\n+        \"ClaimAdjudicationInputItem\",\n+        \"ClaimAdjudicationResult\",\n+        \"ClaimType\",\n+        \"RiskOfBias\",\n+        \"SupportStatus\",\n+    )\n+    for name in names:\n+        assert getattr(analytics, name) is getattr(literature, name)\n+        assert name in analytics.__all__\n--- a/policy-engine/docs/reference/ir/public-surface.md\n+++ b/policy-engine/docs/reference/ir/public-surface.md\n@@ -17,7 +17,7 @@\n \n | Facade | Symbol count | Import policy |\n | --- | --- | --- |\n-| `polisyos.ir.analytics` | 266 | curated lazy facade |\n+| `polisyos.ir.analytics` | 274 | curated lazy facade |\n | `polisyos.ir.kernel` | 52 | full lazy facade |\n | `polisyos.ir.world` | 54 | full lazy facade |\n \n--- a/policy-engine/docs/reference/ir/schema-catalog.md\n+++ b/policy-engine/docs/reference/ir/schema-catalog.md\n@@ -13,14 +13,14 @@\n ## Summary\n \n - Total IR types: `1586`.\n-- Public/root-or-package facade types: `435`.\n+- Public/root-or-package facade types: `443`.\n - ABI snapshot-backed types: `95`.\n - Export enumeration covers these public packages:\n \n | Package | Export count |\n | ------- | ------------ |\n | `polisyos.ir` | 280 |\n-| `polisyos.ir.analytics` | 266 |\n+| `polisyos.ir.analytics` | 274 |\n | `polisyos.ir.kernel` | 52 |\n | `polisyos.ir.world` | 54 |\n \n@@ -28,7 +28,7 @@\n \n | Section | Type count | Public types | Snapshot-backed |\n | ------- | ---------- | ------------ | ---------------- |\n-| `analytics` | 976 | 244 | 37 |\n+| `analytics` | 976 | 252 | 37 |\n | `artifacts` | 25 | 0 | 0 |\n | `governance` | 99 | 21 | 8 |\n | `kernel` | 47 | 38 | 0 |\n@@ -12022,9 +12022,9 @@\n ### `polisyos.ir.analytics.literature.AdmittedClaimAdjudicationBatch` { #polisyos-ir-analytics-literature-admittedclaimadjudicationbatch }\n \n - Kind: `pydantic_model`\n-- Public status: `internal`\n+- Public status: `package_facade`\n - Current version: `1.0`\n-- Exported from: —\n+- Exported from: `polisyos.ir.analytics:AdmittedClaimAdjudicationBatch`\n - ABI snapshot: `—` / `—`\n - Compatibility mode: `—`\n - References: `polisyos.ir.analytics.literature.ClaimAdjudicationResult`\n@@ -12166,9 +12166,9 @@\n ### `polisyos.ir.analytics.literature.CausalCredibility` { #polisyos-ir-analytics-literature-causalcredibility }\n \n - Kind: `enum`\n-- Public status: `internal`\n-- Current version: `—`\n-- Exported from: —\n+- Public status: `package_facade`\n+- Current version: `—`\n+- Exported from: `polisyos.ir.analytics:CausalCredibility`\n - ABI snapshot: `—` / `—`\n - Compatibility mode: `—`\n - References: —\n@@ -12205,9 +12205,9 @@\n ### `polisyos.ir.analytics.literature.ClaimAdjudicationInputBatch` { #polisyos-ir-analytics-literature-claimadjudicationinputbatch }\n \n - Kind: `pydantic_model`\n-- Public status: `internal`\n+- Public status: `package_facade`\n - Current version: `1.0`\n-- Exported from: —\n+- Exported from: `polisyos.ir.analytics:ClaimAdjudicationInputBatch`\n - ABI snapshot: `—` / `—`\n - Compatibility mode: `—`\n - References: `polisyos.ir.analytics.literature.ClaimAdjudicationInputItem`\n@@ -12223,9 +12223,9 @@\n ### `polisyos.ir.analytics.literature.ClaimAdjudicationInputItem` { #polisyos-ir-analytics-literature-claimadjudicationinputitem }\n \n - Kind: `pydantic_model`\n-- Public status: `internal`\n-- Current version: `—`\n-- Exported from: —\n+- Public status: `package_facade`\n+- Current version: `—`\n+- Exported from: `polisyos.ir.analytics:ClaimAdjudicationInputItem`\n - ABI snapshot: `—` / `—`\n - Compatibility mode: `—`\n - References: `polisyos.ir.analytics.literature.CausalDirection`, `polisyos.ir.analytics.literature.ClaimExplicitness`, `polisyos.ir.analytics.literature.ClaimType`, `polisyos.ir.analytics.literature.DesignFamily`, `polisyos.ir.analytics.literature.EvidenceSpan`, `polisyos.ir.analytics.literature.EvidenceStrength`, `polisyos.ir.analytics.literature.SourceBasis`, `polisyos.ir.analytics.literature.TextQuality`\n@@ -12259,9 +12259,9 @@\n ### `polisyos.ir.analytics.literature.ClaimAdjudicationResult` { #polisyos-ir-analytics-literature-claimadjudicationresult }\n \n - Kind: `pydantic_model`\n-- Public status: `internal`\n-- Current version: `—`\n-- Exported from: —\n+- Public status: `package_facade`\n+- Current version: `—`\n+- Exported from: `polisyos.ir.analytics:ClaimAdjudicationResult`\n - ABI snapshot: `—` / `—`\n - Compatibility mode: `—`\n - References: `polisyos.ir.analytics.literature.CausalCredibility`, `polisyos.ir.analytics.literature.ClaimType`, `polisyos.ir.analytics.literature.DesignFamily`, `polisyos.ir.analytics.literature.RiskOfBias`, `polisyos.ir.analytics.literature.SourceBasis`, `polisyos.ir.analytics.literature.SupportStatus`\n@@ -12355,9 +12355,9 @@\n ### `polisyos.ir.analytics.literature.ClaimType` { #polisyos-ir-analytics-literature-claimtype }\n \n - Kind: `enum`\n-- Public status: `internal`\n-- Current version: `—`\n-- Exported from: —\n+- Public status: `package_facade`\n+- Current version: `—`\n+- Exported from: `polisyos.ir.analytics:ClaimType`\n - ABI snapshot: `—` / `—`\n - Compatibility mode: `—`\n - References: —\n@@ -12846,9 +12846,9 @@\n ### `polisyos.ir.analytics.literature.RiskOfBias` { #polisyos-ir-analytics-literature-riskofbias }\n \n - Kind: `enum`\n-- Public status: `internal`\n-- Current version: `—`\n-- Exported from: —\n+- Public status: `package_facade`\n+- Current version: `—`\n+- Exported from: `polisyos.ir.analytics:RiskOfBias`\n - ABI snapshot: `—` / `—`\n - Compatibility mode: `—`\n - References: —\n@@ -12905,9 +12905,9 @@\n ### `polisyos.ir.analytics.literature.SupportStatus` { #polisyos-ir-analytics-literature-supportstatus }\n \n - Kind: `enum`\n-- Public status: `internal`\n-- Current version: `—`\n-- Exported from: —\n+- Public status: `package_facade`\n+- Current version: `—`\n+- Exported from: `polisyos.ir.analytics:SupportStatus`\n - ABI snapshot: `—` / `—`\n - Compatibility mode: `—`\n - References: —\n"
````

### GGA-GATE-02 — verified local boundary, 2026-09-08

The coordinator caught one remaining single-line literature import in
`admitted_claim_adjudications.py` after the initial facade batch and changed it
to the now-supported analytics facade. The final delta gate reports **19 passed,
exit 0, 206.19 seconds**; delta Ruff passes. Its authority checks include full
subject transport, real pipeline, IR resolution, both signed entry paths,
empty appointments, legacy pointers and unminted tokens.

Architecture now reports **exit 0, complete finding identity set empty**:

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=.:src .venv/bin/python -m tools.cli architecture guardrails check --skip-generated-checks > _build/gy_grade_authority/architecture-after-admitted-facade.log 2>&1
```

The saved whole finding-set differences remove the initial ten creep identities
and baseline-drift identity, then the final remaining admitted-row import and
drift identity; no identity is added. The guardrail owner's complete Python
input set and a separate `os.walk` derivation both contain 2,624 paths and have
empty set difference. Recomputed current deep-import creep is empty.
`_build/gy_grade_authority/architecture-finding-identity-diff.json` retains the
full sets. The scratch reconciler's first invocation misspelled the owner's
constant and raised `AttributeError`; after correcting that station error the
complete comparison ran successfully. No crashed output was counted as a zero.

This is the local commit boundary for the shared publication verifier, authorized
IR surface expansion and PA1 source-identity component. It is not a claim that
all repository quality checks pass: the one static mirror failure and transformer
Ruff identities remain recorded without inherited attribution. PA1 exact-request
grounding and calibration work continues. The stale branch, global public-surface
companions and all ungranted architecture files remain untouched; no push occurs.

### GGA-PA1-05 — continued investigation before the exact-request bridge

The preceding verified component boundary is committed as
`d421575d31808796b8a2a66a98c6ca75dfc3f163`. All 28 committed paths were read back
from named branch `codex/gy-grade-authority` and compared byte-for-byte with the
working tree; the tree was clean after readback. No branch publication occurred.

Before the next repair, the mechanism hypothesis is that N7's current SKG
capture measures an empty in-memory schema and routes `table_count` through a
shared wrapper as acquired content. That does not evaluate the exact income
request against retained evidence or CG2's actual premise. The candidate repair
must freeze the request's candidate/problem/world/epoch/outcome/context identity,
enumerate actual retained evidence through the DataForge read API, resolve its
source and independent adjudication lineage, and persist/replay the resulting
request-specific corpus and refusal or verified resolution before N7 consumes it.
Fabric and OpenAlex use the same response wrapper; its shared authority class
must not be declared closed by a per-SKG flag check.

A separate semantic question is being checked before any calibration conversion:
the ratified PR1a source expects independently adjudicated **relation-outcome**
evidence, while the new claim adjudicator grades publication eligibility,
source/design and causal credibility. `publishable` cannot silently become
`correct exact relation` or a CG2 false-binding label. One investigation checks
existing calibration-owner semantics and any accepted mapping; another enumerates
actual retained target and independent CAS evidence. A missing table or empty
CG2 constant is not itself proof that the producer cannot be built. A genuine
missing scientific acceptance decision or empirical premise must be named and
measured before it can become a handback.

### GGA-PA1-06 — a measured scientific acceptance gap, distinct from appointment

The independent owner-contract investigation found no accepted conversion from
the Row 1 grade to CG2 relation-calibration gold. The existing admitted batch is
explicitly authoritative only for `academic_claim_edge_publishability`
(`ir/analytics/literature.py`); `claim_metrics` evaluates `publish_to_graph`, and
the publication predicate uses source, design, support and confidence. CG1's
`exact`/`certified-specialization` judgment concerns a particular proposal and
reference atom across nine critical denotation axes, including do-value, scope,
population and estimand (`runtime/quality/grounding_relation.py`). A study may
remain publishable while a changed proposal binds it to the wrong atom. Thus
publication eligibility cannot distinguish correct from false relation binding.

The existing CG6 `_is_false_bind` mechanism instead requires an independently
derived must-obligation and the actual identifying decision. Its existing
wrong-atom semantic check passes, **one test, exit 0, 42.91 seconds**:

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q -o addopts= tests/unit/runtime/quality/test_grounding_benchmark.py::test_must_negative_wrong_atom_identification_counts_false_bind
```

The complete 2,624-source-Python symbol census locates the existing calibration
owners in `grounding_bind.py` and `grounding_benchmark.py`, and finds no production
relation-observation source/schema implementation. `CalibrationStratumRecord`
has stratum, status, count and hash fields; it has no per-observation relation
gold or false-bind count. Its current status recomputation checks owner, hash,
epoch and count; `_risk_ledger` uses configured bounds. The PR1a plan defines
lineage, observation identity, an exact stratum and at least 20 observations,
but does not define the relation-specific gold or an outcome-sensitive production
calibration acceptance rule.

This is a specific missing scientific acceptance decision, not an appointment
being treated as permission to build. The architect handback must define the
independently adjudicated proposal/reference relation and exact contextual
binding, the accepted adjudicator authority, and how observed correct/incorrect
bindings determine production calibration acceptance. Counting publishable
papers or merely accumulating 20 signed observations would invent that rule.
Proposed row: `cg2-production-relation-gold-acceptance-unspecified`; proposed
owners team-architecture for acceptance semantics and runtime/quality for
execution, with institutional appointment unallocated. Source/CAS projection,
exact-request replay and honest N7 refusal remain buildable and are continuing.

### GGA-PA1-07 — complete local calibration evidence and independent reconciliation

This is a new transparent read-only measurement, not the registered PR1a firstness attempt.
No source, plan, register, ledger or retained-data changes were made. All artifacts below
are ignored scratch. Measurement UTC: 2026-09-07 21:05–21:14 (local date 2026-09-08).

Hypothesis recorded before measurement: retained claims and stored numeric intervals
can support candidate grounding, but an exact-stratum CG2 positive additionally needs
independently appointed relation-outcome evidence with readable, bound CAS lineage.
Candidate publication labels do not supply the relation outcome they would calibrate.

#### Disposition

The currently exercised avg_income test request specifies target/metric avg_income
and average_treatment_effect. Its atom does not specify treatment, amount, eligibility
or timing. Its diversity-key word grant is not an intervention authority. Engineering
can still assemble a concrete candidate and owner-bound treatment/assignment; this
omission is not an external impossibility.

The actual configured retained Academic loader resolves **zero verified rows**. Its six
CAS/registry/input/result/pass/compatibility paths are absent before and after the read.
No independent CG2 relation-outcome observation is currently available through that
configured path. The complete retained production tree has no FileSystemCAS manifest
or blob files. Historical original/remap/backup roots declared by source_lineage.json
are unavailable locally; their contents are not_established, not counted as zero.

Row1 ClaimAdjudicationVerifier authenticates publication/source/design benchmark and
execution results. Its gold schema is item_id, split, publish_to_graph, source_basis,
design_family; precision_publishable uses publish_to_graph. It cannot turn those gold
labels into an exact/specialization relation label. The retained benchmark_suite.json
is a scenario-query suite and the real independent corpus parser refuses it for missing
suite_version/cases and forbidden scenarios. The three retained claim_gold seed rows
have no signed observation/CAS lineage and concern publication, not relation outcomes.

The smallest further engineering component is a relation-outcome evidence producer and
verifier that binds actual source/operator/context/epoch cases to separately established
relation truth and projects their complete distinct population into CG2. Row1's shared
CAS, signed receipt authentication, complete observation binding and recomputation can
be reused, but publication yes/no is not the target label. Its deployment appointment
slot is empty on the actual production default invocation. Deployment-selected trust
configuration and genuine independent relation observations are external inputs; this
task cannot appoint their evaluator or manufacture their labels. Existing raw source
could support subsequent candidate extraction/annotation once an actual operator is
bound. This report makes no global claim that semantic source recovery is impossible.

#### Denominators and source adequacy

- Full retained production tree: 6,562 files, 88 JSON, 6,329 JSONL, 8 DuckDB, 43 Parquet
  plus other enumerated formats. Inventory metadata errors: 0.
- Complete structured authority inspection: all 88 JSON plus all 3 academic/scholar-path
  JSONL; 90 readable, 1 malformed JSON (curated/udf_schema.json at line 49). Other JSONL
  data rows were not rescanned: their presence cannot replace the required absent CAS
  manifest/blob ABI. The malformed schema remains explicitly unreadable.
- All three academic JSONL: 3 publication seed examples, 45 acquisition backlog records,
  7,607 heuristic transport-score records. Nine metadata files carry artifact_id keys;
  they are Ukraine simulation bundle/build manifests, not claim independent evaluation
  receipts. No key-presence check was used to admit authority.
- Complete production-source constructor audit at measurement time: 2,624 Python files,
  0 unreadable/parse errors, one terminal-symbol ClaimAdjudicationVerifier constructor
  in the DataForge loader, which passes no appointments; no ClaimEvaluatorAppointment
  constructor. This bounds current source invocation, not external deployment history
  or an arbitrary caller's ability to inject configured objects.
- Previous complete retained-source station, reread from its saved bytes: 4,032 stored
  nonzero-CI parameters, 1,468 works, 4,032 work joins, 4,029 retained abstracts, 1,309
  nonempty raw contexts, 1,080 literal raw-context-in-abstract matches. These figures
  are source availability, not causal validity or independently certified native CIs.
- New one-query missing-field supplement exports all 4,032 rows, with raw context,
  source title/abstract, units, country and periods. A separate full name aggregation
  covers all 62,248 parameters and 45,707 distinct names. No literal avg_income name.
  The lexical income/earnings/wage/salary subset has 27 rows from 12 works; all 12
  retained abstracts were read. No row in that named subset has exact country UA.
  All 24 exact-country-UA nonzero-CI rows are retained in the summary. These exhaustive
  named subsets do not exhaust multilingual or other semantic relevance.
- Relevant source candidates are real: US SNAP spending propensity, Paraguay wage
  decomposition, terrorism and county total earnings, and income as a covariate in
  health/nutrition studies. They do not by themselves bind a chosen policy to UA
  average-income ATE, its unit conversion, target transport, or CG2 relation truth.
  Stored intervals are not uniformly native confidence intervals: the UA shadow
  economy record's 18–46 bounds come from a range across estimation methods in its
  retained text. A producer must verify the source meaning before using CI fields.

#### Commands and receipts

All commands run from `/Users/deniskopylov/polisyos/.worktrees/gy/policy-engine` and are
sole module-form commands:

```
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m _build.gy_grade_authority.pa1_calibration_evidence_census saved
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m _build.gy_grade_authority.pa1_calibration_evidence_census inventory
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m _build.gy_grade_authority.pa1_calibration_evidence_census calls
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m _build.gy_grade_authority.pa1_calibration_evidence_census metadata
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m _build.gy_grade_authority.pa1_calibration_evidence_census runtime
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m _build.gy_grade_authority.pa1_calibration_evidence_census native
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m _build.gy_grade_authority.pa1_calibration_evidence_census summary
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m _build.gy_grade_authority.pa1_calibration_evidence_census income_sources
```

All final station executions exited 0. Recorded times: saved .110 s, inventory .623 s,
metadata 6.652 s, final runtime .980 s, native query/export 1.102 s (internal timer),
summary .172 s. Constructor census total process duration was not retained. A first
runtime attempt exited 1 because AcademicBatchConfig initializes stage directories and
the retained source refused academic/raw creation. The final station initializes that
mutable config in scratch and then sets its public snapshot_root to the existing
retained holder; it invokes the real owner read and confirms no artifact path appeared.
This is a harness failure/correction, not a product refusal or a semantic removal red.

No new semantic source gate was implemented in this census lane, so no new property
removal control is claimed. Earlier accepted Row1/identity behavioral removal evidence
is unchanged; DEF22 owns tests for the new exact-request/CG2 producer mechanism.

Artifacts (all relative to `_build/gy_grade_authority/`):

| Artifact | SHA-256 |
| --- | --- |
| pa1-calibration-saved-output.json | 49ba9f977f4c012b46073cd0f047a7114787cfa3ad4869bd6261cb1a9c0479c9 |
| pa1-calibration-inventory-output.json | 479fd227a388bd35cb49187b11372763217c2b85889772844c4cab089f0806b7 |
| pa1-calibration-calls-output.json | a6264bc1db6fb24b84f1cb8c5ae33906e5297ccbb6cc1e9e4ad022e67d478308 |
| pa1-calibration-metadata-output.json | b601d39959a477f4d9a89a3006ca2fe687d4b212950e6a4d7d55e505281c5e0e |
| pa1-calibration-runtime-output.json | 410254a05dcee8fcc5961e9e5f8d226fdfaa9211672ebc1c553545b08d63a32a |
| pa1-calibration-native-output.json | 0df67f563ea2d9d69049507015553bb913a61ab2617c881c0efb86d155513a6a |
| pa1-calibration-native-population.jsonl | c395cbca101c606d59be01aac1ff71aa9c850a321622ebf2f5603ca47a0cff59 |
| pa1-calibration-summary-output.json | bc656d3551b791d3278d78393ad2d610521503b1d0b1a6cbc29dc11b2d6708fb |
| pa1-calibration-income-sources-output.json | 3d12e1e307cda7f0ff822208fa261e94873cb8c816523ac8facebbe68d20d975 |

Full artifact bytes, not truncated stdout, are the count receipts. The census script
contains exact queries and selection rules. The native station does not use the old
registered selector or narrow the population by successful outcome.

Independent reconciliation subsequently completed: **exit 0, 2.066643 seconds**. All eight complete identity/multiset comparisons have empty missing/extra sets, and all ten count crosschecks agree. A separate `os.walk` derives the full inventory and metadata frame; SQL derives complete numeric/name/subset identity sets independently of the saved Python projections. Reconciler source SHA-256 `f55173b958bb73e51d12a7647a6cf60ae37699d3a1c61b4a04218a91a5782acc`; output SHA-256 `cf3a4516c6cc745428cfed610597a82e55725a93e2009569bf7256b614722647`.

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src .venv/bin/python -m _build.gy_grade_authority.pa1_calibration_census_reconcile
```

### Durable calibration investigation stations

The relation-owner inspection is pinned to committed source `d421575d31808796b8a2a66a98c6ca75dfc3f163`. Its initial census was a filesystem walk; no retrospective all-file hash snapshot is claimed. The pinned owner inspection preserves complete DTO fields and decision bodies separately from token absence.

#### `_build/gy_grade_authority/pa1_calibration_evidence_census.py`

SHA-256 `7877efe464184021a2da2118018c3cdb7bf68fcce175a2fff59f63634579b9b4`; 18437 bytes.

````python
"""Transparent read-only census of retained PA1 evidence, not PR1a selection."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from time import perf_counter

BASE = Path('_build/gy_grade_authority')


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def emit(name: str, value: object) -> None:
    out = BASE / ('pa1-calibration-' + name + '-output.json')
    out.write_text(json.dumps(value, indent=2, default=str) + '\n')
    print(json.dumps({'artifact': str(out), 'sha256': digest(out), 'result': value}, indent=2, default=str))


def saved() -> None:
    path = BASE / 'pa1-identity-inputs-output.json'
    data = json.loads(path.read_text())
    rows = data['numeric_claim_join_rows']
    terms = re.compile(r'income|earning|wage|salary|poverty|employment|unemployment|gdp|cash|grant|transfer', re.I)
    relevant = [r for r in rows if any(terms.search(str(r[i] or '')) for i in (2, 9, 10))]
    exact = [r for r in rows if 'avg_income' in (r[2], r[9], r[10])]
    stream_path = BASE / 'pa1-source-sufficiency-output.json.txt'
    text = stream_path.read_text()
    decoder = json.JSONDecoder()
    objects = []
    offset = 0
    while offset < len(text):
        while offset < len(text) and text[offset].isspace():
            offset += 1
        if offset == len(text):
            break
        value, offset = decoder.raw_decode(text, offset)
        objects.append(value)
    summary = {k: value for obj in objects for k, value in obj.items()
               if k not in ('named_target_extractions', 'candidate_numeric_sources')}
    emit('saved', {
        'measured_at': datetime.now(UTC).isoformat(),
        'inputs': {str(path): digest(path), str(stream_path): digest(stream_path)},
        'join_query_source': str(BASE / 'pa1_identity_inputs.py'),
        'join_is': 'native nonzero CI parameter estimate matched to same-work extraction claim by numeric effect_size equality; NOT an admitted lineage or a semantic match',
        'columns': ['numeric_id', 'work_id', 'variable_name', 'point', 'ci_low', 'ci_high', 'unit', 'extraction_id', 'claim_id', 'cause', 'effect', 'direction'],
        'rows': len(rows), 'reported_rows_crosscheck': data['numeric_claim_join_count'],
        'distinct_numeric_ids': len({r[0] for r in rows}),
        'distinct_work_ids': len({r[1] for r in rows}),
        'exact_avg_income_rows': exact,
        'relevance_filter': terms.pattern,
        'complete_lexical_relevant_rows': relevant,
        'lexical_relevant_count': len(relevant),
        'prior_source_sufficiency_summary': summary,
    })


def inventory() -> None:
    root = Path('production_data')
    files = []
    errors = []
    for path in sorted(root.rglob('*')):
        try:
            if path.is_file():
                files.append({'path': str(path), 'size': path.stat().st_size, 'suffix': path.suffix})
        except OSError as exc:
            errors.append({'path': str(path), 'error': repr(exc)})
    out = {
        'measured_at': datetime.now(UTC).isoformat(), 'root': str(root.resolve()),
        'file_denominator': len(files), 'extensions': dict(Counter(r['suffix'] for r in files)),
        'structured_bytes': sum(r['size'] for r in files if r['suffix'] in ('.json', '.jsonl')),
        'files': files, 'unreadable_metadata': errors,
    }
    path = BASE / 'pa1-calibration-inventory-output.json'
    path.write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps({**{k: v for k, v in out.items() if k != 'files'},
                      'artifact': str(path), 'sha256': digest(path),
                      'adjudication_named_files': [r for r in files if 'adjudicat' in r['path'].lower()],
                      'manifest_files': [r for r in files if r['path'].endswith('.manifest.json')]}, indent=2))


def calls() -> None:
    files = sorted(Path('src/polisyos').rglob('*.py'))
    matches = []
    errors = []
    for path in files:
        try:
            tree = ast.parse(path.read_text())
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append({'path': str(path), 'error': repr(exc)})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                if name.split('.')[-1] in ('ClaimAdjudicationVerifier', 'ClaimEvaluatorAppointment'):
                    matches.append({'path': str(path), 'sha256': digest(path), 'line': node.lineno,
                                    'call': ast.unparse(node)})
    emit('calls', {'measured_at': datetime.now(UTC).isoformat(),
                   'root': 'src/polisyos', 'file_type': '.py', 'source_denominator': len(files),
                   'all_constructor_calls': matches, 'unreadable': errors,
                   'scope': 'production source calls by terminal symbol; no test fixture appointments, no claim about external deployments'})


def metadata() -> None:
    inventory_path = BASE / 'pa1-calibration-inventory-output.json'
    inventory = json.loads(inventory_path.read_text())
    selected = [r for r in inventory['files'] if r['suffix'] == '.json' or
                (r['suffix'] == '.jsonl' and any('academic' in part or 'scholar' in part
                                               for part in Path(r['path']).parts))]
    files = []
    errors = []
    authority_keys = {'artifact_id', 'evaluator_id', 'key_id', 'signature_hex', 'observations_ref',
                      'benchmark_ref', 'candidate_ref', 'evaluation_ref', 'execution_receipt',
                      'evaluation_receipt', 'result_artifact_id', 'relation_type', 'reference_epoch'}
    for row in selected:
        path = Path(row['path'])
        try:
            values = ([json.loads(path.read_text())] if path.suffix == '.json' else
                      [json.loads(line) for line in path.read_text().splitlines() if line.strip()])
            keys = Counter()
            root_keys = set()
            markers = []
            def walk(value: object, location: str) -> None:
                if isinstance(value, dict):
                    for key, child in value.items():
                        keys[key] += 1
                        if key in authority_keys:
                            markers.append({'location': location + '.' + key,
                                            'value_type': type(child).__name__})
                        walk(child, location + '.' + key)
                elif isinstance(value, list):
                    for index, child in enumerate(value):
                        walk(child, location + '[' + str(index) + ']')
            for index, value in enumerate(values):
                if isinstance(value, dict):
                    root_keys.update(value)
                walk(value, str(index))
            files.append({**row, 'sha256': digest(path), 'records': len(values),
                          'root_keys': sorted(root_keys), 'complete_nested_key_counts': dict(keys),
                          'authority_marker_locations_not_verification': markers})
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append({**row, 'error': repr(exc)})
    lineage = Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/meta/source_lineage.json')
    data = json.loads(lineage.read_text())
    remote = [{'source': source, 'role': role, 'declared_path': value,
               'locally_readable': Path(value).is_file() or Path(value).is_dir()}
              for source, values in data['sources'].items() for role, value in values.items() if value]
    out = {'measured_at': datetime.now(UTC).isoformat(), 'inventory_input': str(inventory_path),
           'inventory_sha256': digest(inventory_path),
           'selected_denominator': len(selected), 'file_types': dict(Counter(r['suffix'] for r in selected)),
           'selection': 'ALL production .json metadata plus ALL academic/scholar-path .jsonl, complete nested keywalk; other JSONL rows not reread because admitted CAS ABI requires independently present manifest/blob files',
           'files': files, 'unreadable': errors, 'declared_source_locations': remote,
           'scope': 'Markers inventory only. Authority still requires real admitted CAS verifier; missing original remote locations are unavailable, not zero observations there.'}
    path = BASE / 'pa1-calibration-metadata-output.json'
    path.write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'files'} | {
        'artifact': str(path), 'sha256': digest(path),
        'readable_files': len(files), 'authority_marker_files': [r['path'] for r in files if r['authority_marker_locations_not_verification']],
        'academic_jsonl': [{k: v for k, v in r.items() if k not in ('complete_nested_key_counts', 'authority_marker_locations_not_verification')} for r in files if r['suffix'] == '.jsonl'],
    }, indent=2))


def runtime() -> None:
    from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import load_verified_claim_adjudication_rows
    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import _Corpus, _GoldCase
    from pydantic import ValidationError
    snapshot = Path('production_data/policyos_academic_runtime_slim_20260411T112032Z')
    assert (snapshot / 'academic').is_dir()
    # The public initializer mkdirs stage folders. Initialize in our scratch,
    # then configure the existing read-only holder through its mutable field.
    config = AcademicBatchConfig(snapshot_root=BASE / 'pa1_calibration_runtime_config')
    config.snapshot_root = snapshot
    paths = {key: getattr(config, key) for key in (
        'claim_adjudication_cas_root', 'claim_adjudication_registry_root',
        'claim_adjudication_result_ref_path', 'claim_adjudication_input_ref_path',
        'claim_adjudications_path', 'claim_adjudication_passes_path')}
    before = {key: value.exists() for key, value in paths.items()}
    capability = load_verified_claim_adjudication_rows(config)
    complete_verified_rows = capability._read()
    # Empty current production receipt set takes the actual no-match branch before
    # current-subject validation. This is absence evidence, not a fabricated subject.
    observation = capability.for_current_subject({'claim_id': 'd276db167d011acdff858c28'})
    after = {key: value.exists() for key, value in paths.items()}
    assert before == after
    benchmark = snapshot / 'academic/benchmark_suite.json'
    benchmark_error = None
    try:
        _Corpus.model_validate_json(benchmark.read_bytes())
    except ValidationError as exc:
        benchmark_error = [{'type': err['type'], 'loc': err['loc']} for err in exc.errors()]
    emit('runtime', {
        'measured_at': datetime.now(UTC).isoformat(), 'configured_snapshot': str(snapshot.resolve()),
        'configuration_note': 'Constructor was initialized in worktree scratch before setting its public snapshot_root field to the retained holder; direct production initialization previously refused an attempted academic/raw mkdir with PermissionError. No retained-data writes.',
        'paths': {key: str(value) for key, value in paths.items()},
        'before_exists': before, 'after_exists': after,
        'real_loader': 'load_verified_claim_adjudication_rows(config).for_current_subject',
        'existing_income_claim_id': 'd276db167d011acdff858c28',
        'actual_consumer_result': observation,
        'complete_owner_row_read': 'VerifiedClaimAdjudicationRows._read()',
        'verified_current_row_count': len(complete_verified_rows),
        'production_benchmark_path': str(benchmark), 'production_benchmark_sha256': digest(benchmark),
        'independent_benchmark_schema_refusal': benchmark_error,
        'gold_case_schema_fields': list(_GoldCase.model_fields),
        'ceiling': 'Publication eligibility labels cannot establish CG2 relation-outcome labels. No claim about unavailable remote source roots.',
    })


def native() -> None:
    import duckdb
    start = perf_counter()
    source = Path('production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb')
    before = source.stat()
    con = duckdb.connect(str(source), read_only=True)
    scratch = BASE / 'pa1_calibration_duckdb'
    scratch.mkdir(parents=True, exist_ok=True)
    con.execute('SET temp_directory = ?', [str(scratch.resolve())])
    con.execute('SET threads = 2')
    query = '''SELECT p.id AS numeric_id,p.work_id,p.variable_name,p.estimate,p.ci_low,p.ci_high,
        p.std_error,p.unit,p.study_design,p.sample_size,p.country,p.period_start,p.period_end,
        p.trust_score,p.raw_context,w.title,w.abstract,w.year,w.is_retracted,w.full_text_url
        FROM ac_parameter_estimates p LEFT JOIN ac_works w ON p.work_id=w.id
        WHERE p.ci_low < p.ci_high ORDER BY p.id'''
    cursor = con.execute(query)
    columns = [item[0] for item in cursor.description]
    rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    names = con.execute('SELECT variable_name,count(*) FROM ac_parameter_estimates GROUP BY variable_name ORDER BY variable_name').fetchall()
    con.close()
    after = source.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    artifact = BASE / 'pa1-calibration-native-population.jsonl'
    artifact.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
    terms = re.compile(r'(?:^|[._\s])(income|earnings?|wages?|salary|poverty|employment|unemployment|gdp|cash|grants?|transfers?)(?:$|[._\s])', re.I)
    lexical = [row for row in rows if terms.search(row['variable_name'] or '')]
    emit('native', {
        'measured_at': datetime.now(UTC).isoformat(), 'elapsed_seconds': perf_counter() - start,
        'source': str(source.resolve()), 'source_size': before.st_size,
        'source_mtime_ns': before.st_mtime_ns, 'source_stat_unchanged': True,
        'query': query, 'columns': columns, 'complete_native_ci_rows': len(rows),
        'distinct_works': len({r['work_id'] for r in rows}),
        'full_population_artifact': str(artifact), 'full_population_sha256': digest(artifact),
        'all_parameter_row_count': sum(n for _, n in names),
        'all_parameter_distinct_variable_count': len(names),
        'all_parameter_variable_counts': names,
        'lexical_filter_only': terms.pattern,
        'lexical_native_ci_count': len(lexical),
        'complete_lexical_native_ci_rows': lexical,
        'scope': 'Raw extraction evidence. Numeric interval existence and lexical relevance do not prove native source support, causal effect, transport or independent relation labels.',
    })


def summary() -> None:
    path = BASE / 'pa1-calibration-native-output.json'
    data = json.loads(path.read_text())
    rows = [json.loads(line) for line in (BASE / 'pa1-calibration-native-population.jsonl').read_text().splitlines()]
    income_pattern = re.compile(r'(?:^|[._\s])(income|earnings?|wages?|salary)(?:$|[._\s])', re.I)
    income = [r for r in rows if income_pattern.search(r['variable_name'] or '')]
    ua = [r for r in rows if str(r['country']).lower() in ('ua', 'ukraine')]
    def compact(row: dict) -> dict:
        return {key: value for key, value in row.items() if key not in ('abstract', 'full_text_url', 'study_design')}
    out = {
        'input': str(path), 'input_sha256': digest(path),
        'complete_native_ci_rows': len(rows), 'all_parameter_rows': data['all_parameter_row_count'],
        'all_parameter_distinct_names': data['all_parameter_distinct_variable_count'],
        'all_parameter_exact_avg_income_names': [row for row in data['all_parameter_variable_counts'] if row[0] == 'avg_income'],
        'native_ci_exact_avg_income_rows': [compact(r) for r in rows if r['variable_name'] == 'avg_income'],
        'native_ci_income_name_filter': income_pattern.pattern, 'native_ci_income_name_rows': len(income),
        'native_ci_income_name_works': len({r['work_id'] for r in income}),
        'complete_income_name_rows': [compact(r) for r in income],
        'native_ci_exact_country_UA_rows': len(ua), 'complete_exact_country_UA_rows': [compact(r) for r in ua],
        'native_ci_income_name_and_UA_rows': [compact(r) for r in income if str(r['country']).lower() in ('ua','ukraine')],
        'ceiling': 'Name filters exhaust named subsets, not semantic potential of every paper or future source recovery.',
    }
    emit('summary', out)


def income_sources() -> None:
    summary = json.loads((BASE / 'pa1-calibration-summary-output.json').read_text())
    work_ids = {row['work_id'] for row in summary['complete_income_name_rows']}
    all_rows = [json.loads(line) for line in (BASE / 'pa1-calibration-native-population.jsonl').read_text().splitlines()]
    works = {}
    for row in all_rows:
        if row['work_id'] in work_ids:
            works[row['work_id']] = {key: row[key] for key in ('work_id', 'title', 'abstract', 'country', 'year', 'study_design')}
    emit('income-sources', {'complete_named_income_work_count': len(works),
                            'works': [works[key] for key in sorted(works)],
                            'scope': 'Entire lexical income-name native-CI work subset, not all semantically relevant sources'})


def receipts() -> None:
    report = BASE / 'pa1-calibration-evidence-handback.md'
    rows = re.findall(r'^\| ([^|]+) \| ([0-9a-f]{64}) \|$', report.read_text(), re.M)
    actual = {name: digest(BASE / name) for name, _ in rows}
    assert all(actual[name] == expected for name, expected in rows)
    print(json.dumps({'report': str(report), 'report_sha256': digest(report),
                      'script': __file__, 'script_sha256': digest(Path(__file__)),
                      'artifact_table_rows_verified': len(rows), 'artifact_hashes': actual}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('station', choices=('saved', 'inventory', 'calls', 'metadata', 'runtime', 'native', 'summary', 'income_sources', 'receipts'))
    args = parser.parse_args()
    globals()[args.station]()
````

#### `_build/gy_grade_authority/pa1_calibration_census_reconcile.py`

SHA-256 `f55173b958bb73e51d12a7647a6cf60ae37699d3a1c61b4a04218a91a5782acc`; 9515 bytes.

````python
"""Independent os.walk and SQL reconciliation of the saved PA1 census."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

import duckdb

BASE = Path('_build/gy_grade_authority')


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def compare(label: str, first: list[object], second: list[object]) -> dict:
    left = Counter(canonical(item) for item in first)
    right = Counter(canonical(item) for item in second)
    return {
        'label': label,
        'saved_count': sum(left.values()), 'independent_count': sum(right.values()),
        'saved_distinct': len(left), 'independent_distinct': len(right),
        'saved_multiset_sha256': hashlib.sha256(canonical(sorted(left.items())).encode()).hexdigest(),
        'independent_multiset_sha256': hashlib.sha256(canonical(sorted(right.items())).encode()).hexdigest(),
        'missing_from_independent': list((left - right).elements()),
        'extra_in_independent': list((right - left).elements()),
        'equal': left == right,
    }


def main() -> None:
    start = perf_counter()
    inputs = {name: BASE / name for name in (
        'pa1-calibration-inventory-output.json', 'pa1-calibration-metadata-output.json',
        'pa1-calibration-native-output.json', 'pa1-calibration-native-population.jsonl',
        'pa1-calibration-summary-output.json', 'pa1-calibration-saved-output.json',
    )}
    inventory = json.loads(inputs['pa1-calibration-inventory-output.json'].read_text())
    metadata = json.loads(inputs['pa1-calibration-metadata-output.json'].read_text())
    numeric = json.loads(inputs['pa1-calibration-native-output.json'].read_text())
    summary = json.loads(inputs['pa1-calibration-summary-output.json'].read_text())
    saved = json.loads(inputs['pa1-calibration-saved-output.json'].read_text())
    rows = [json.loads(line) for line in inputs['pa1-calibration-native-population.jsonl'].read_text().splitlines()]

    errors = []
    walked = []
    def walk_error(exc: OSError) -> None:
        errors.append({'path': exc.filename, 'error': repr(exc)})
    for directory, _, names in os.walk('production_data', followlinks=False, onerror=walk_error):
        for name in names:
            path = os.path.join(directory, name)
            try:
                if os.path.isfile(path):
                    walked.append({'path': path, 'size': os.stat(path).st_size,
                                   'suffix': os.path.splitext(name)[1]})
            except OSError as exc:
                walk_error(exc)
    frame = []
    for row in walked:
        components = os.path.normpath(row['path']).split(os.sep)
        if row['suffix'] == '.json' or (row['suffix'] == '.jsonl' and
                any('academic' in part or 'scholar' in part for part in components)):
            frame.append(row)
    comparisons = [
        compare('complete production path/size/type multiset: rglob vs os.walk', inventory['files'], walked),
        compare('complete metadata frame including unreadable member',
                [{key: row[key] for key in ('path', 'size', 'suffix')} for row in metadata['files'] + metadata['unreadable']], frame),
    ]
    source = Path(numeric['source'])
    before = source.stat()
    con = duckdb.connect(str(source), read_only=True)
    scratch = BASE / 'pa1_calibration_reconcile_duckdb'
    scratch.mkdir(parents=True, exist_ok=True)
    con.execute('SET temp_directory = ?', [str(scratch.resolve())])
    con.execute('SET threads = 2')
    regex = r'(?i)(^|[._\s])(income|earnings?|wages?|salary)($|[._\s])'
    queries = {
        'counts': '''SELECT count(*) AS all_parameters,
            count(DISTINCT variable_name) AS distinct_nonnull_names,
            count(*) FILTER(WHERE variable_name IS NULL) AS null_name_rows,
            count(*) FILTER(WHERE ci_low < ci_high) AS stored_nonzero_ci,
            count(DISTINCT work_id) FILTER(WHERE ci_low < ci_high) AS native_ci_works,
            count(*) FILTER(WHERE ci_low < ci_high AND regexp_matches(variable_name, ?)) AS income_rows,
            count(DISTINCT work_id) FILTER(WHERE ci_low < ci_high AND regexp_matches(variable_name, ?)) AS income_works,
            count(*) FILTER(WHERE ci_low < ci_high AND lower(country) IN ('ua','ukraine')) AS ua_rows,
            count(*) FILTER(WHERE variable_name='avg_income') AS exact_avg_income_rows
            FROM ac_parameter_estimates''',
        'native_identity': '''SELECT id,work_id,variable_name,country,
            coalesce(regexp_matches(variable_name, ?),false) AS income,
            coalesce(lower(country) IN ('ua','ukraine'),false) AS ua
            FROM ac_parameter_estimates WHERE ci_low < ci_high ORDER BY id''',
        'all_names': 'SELECT variable_name,count(*) FROM ac_parameter_estimates GROUP BY variable_name ORDER BY variable_name',
    }
    cursor = con.execute(queries['counts'], [regex, regex])
    counts = dict(zip([r[0] for r in cursor.description], cursor.fetchone(), strict=True))
    native = con.execute(queries['native_identity'], [regex]).fetchall()
    name_rows = con.execute(queries['all_names']).fetchall()
    con.close()
    after = source.stat()
    comparisons.extend([
        compare('native-CI full identity occurrences',
                [[r['numeric_id'], r['work_id'], r['variable_name'], r['country']] for r in rows],
                [list(r[:4]) for r in native]),
        compare('all variable names plus exact multiplicities', numeric['all_parameter_variable_counts'], [list(r) for r in name_rows]),
        compare('native-CI work ID set', sorted({r['work_id'] for r in rows}), sorted({r[1] for r in native})),
        compare('income native-CI exact numeric ID set',
                [r['numeric_id'] for r in summary['complete_income_name_rows']], [r[0] for r in native if r[4]]),
        compare('income native-CI exact work ID set',
                sorted({r['work_id'] for r in summary['complete_income_name_rows']}), sorted({r[1] for r in native if r[4]})),
        compare('UA native-CI exact numeric ID set',
                [r['numeric_id'] for r in summary['complete_exact_country_UA_rows']], [r[0] for r in native if r[5]]),
    ])
    prior_join_count = saved['prior_source_sufficiency_summary']['numeric_source_denominator'][0][0]
    count_checks = {
        'file_count_equals_walk_and_extensions_sum': inventory['file_denominator'] == len(walked) == sum(Counter(r['suffix'] for r in walked).values()),
        'metadata_88_json_plus_3_jsonl_equals_90_readable_plus_1_unreadable': len(frame) == 91 == len(metadata['files']) + len(metadata['unreadable']) and Counter(r['suffix'] for r in frame) == {'.json': 88, '.jsonl': 3},
        'all_parameters_count_equals_group_sum': counts['all_parameters'] == numeric['all_parameter_row_count'] == sum(n for _, n in name_rows),
        'distinct_names_count_equals_group_population': counts['distinct_nonnull_names'] + int(counts['null_name_rows'] > 0) == len(name_rows) == numeric['all_parameter_distinct_variable_count'],
        'stored_ci_count_equals_export_and_prior_independent_work_join': counts['stored_nonzero_ci'] == len(rows) == prior_join_count,
        'native_ci_works_count_equals_export': counts['native_ci_works'] == len({r['work_id'] for r in rows}),
        'income_count_equals_saved_population': counts['income_rows'] == len(summary['complete_income_name_rows']),
        'income_works_count_equals_saved_population': counts['income_works'] == len({r['work_id'] for r in summary['complete_income_name_rows']}),
        'ua_count_equals_saved_population': counts['ua_rows'] == len(summary['complete_exact_country_UA_rows']),
        'exact_avg_income_count_equals_saved_name_aggregation': counts['exact_avg_income_rows'] == sum(n for name, n in numeric['all_parameter_variable_counts'] if name == 'avg_income'),
    }
    result = {
        'measured_at': datetime.now(UTC).isoformat(), 'elapsed_seconds': perf_counter() - start,
        'script_sha256': sha(Path(__file__)), 'input_sha256': {str(p): sha(p) for p in inputs.values()},
        'inventory_root': inventory['root'], 'independent_inventory_mechanism': 'os.walk, os.stat, os.path.splitext',
        'walk_file_count': len(walked), 'walk_extensions': dict(Counter(r['suffix'] for r in walked)),
        'walk_errors': errors, 'metadata_frame_count': len(frame),
        'source': str(source), 'source_stat_unchanged': (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
        'sql_queries': queries, 'sql_income_regex': regex, 'sql_counts': counts,
        'complete_identity_multiset_comparisons': comparisons, 'independent_count_crosschecks': count_checks,
        'scope': 'No abstract/source-text SQL columns read. Exact complete identity and count reconciliation, not semantic selection or authority admission.',
    }
    out = BASE / 'pa1-calibration-reconciliation-output.json'
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'artifact': str(out), 'sha256': sha(out), 'result': result}, indent=2))
    assert not errors and result['source_stat_unchanged']
    assert all(check['equal'] for check in comparisons) and all(count_checks.values())


if __name__ == '__main__':
    main()
````

#### `_build/gy_grade_authority/pa1_cg2_relation_mapping_census.py`

SHA-256 `ebbe922ea0a60ef6fa524f24974b820a133773b9fbd4d91c0f9f6bb701d3665e`; 1713 bytes.

````python
import ast,json,re
from pathlib import Path
files=sorted(p for p in Path('src').rglob('*.py') if '__pycache__' not in p.parts)
requested={'ProductionCG2CalibrationSource','ProductionCalibrationObservation','ProductionCalibrationCorpus','ProductionCalibrationResolution'}
occurrences=[]
errors=[]
owners={}
for path in files:
 text=path.read_text()
 if any(word in text for word in ('ProductionCG2','production_calibration_observation','cg2_production_academic','CalibrationStratumRecord','GroundingCalibrationLedger','CalibrationAnchorSet')):
  occurrences.append(str(path))
 for symbol in requested:
  if symbol in text: owners.setdefault(symbol,[]).append(str(path))
print(json.dumps({'file_type':'src/**/*.py excluding __pycache__','count':len(files),'calibration_candidate_paths':occurrences,'requested_production_symbols':owners},indent=2))
for filename in ('grounding_bind.py','grounding_benchmark.py','grounding_relation.py'):
 path=Path('src/polisyos/runtime/quality')/filename
 tree=ast.parse(path.read_text())
 rows=[]
 for node in ast.walk(tree):
  if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and re.search('calibrat|false_bind|promotability|relation_from_axes|^GroundingRelation|^GroundingBenchmarkCase|^GroundingBenchmarkDecision|^LabelDerivation',node.name,re.I):
   rows.append([node.name,node.lineno])
 print(filename, json.dumps(sorted(rows,key=lambda x:x[1])))
path=Path('src/polisyos/ir/analytics/literature.py')
for node in ast.parse(path.read_text()).body:
 if isinstance(node,ast.ClassDef) and node.name in ('ClaimAdjudicationResult','AdmittedClaimAdjudicationBatch'):
  print(node.name,[(x.target.id,x.lineno) for x in node.body if isinstance(x,ast.AnnAssign)])
````

#### `_build/gy_grade_authority/pa1_cg2_relation_mapping_owner_inspection.py`

SHA-256 `3c5a4a319e2b7c5ed62a2f351b8e6d7a51e4986403dbdec5ef08607de112c409`; 2148 bytes.

````python
"""Reproduce the narrow owner-interface inspection from the historical source pin."""
import ast
import hashlib
import json
import subprocess
from pathlib import Path

PIN = 'd421575d31808796b8a2a66a98c6ca75dfc3f163'
OWNERS = {
 'src/polisyos/runtime/quality/grounding_bind.py': (
  'CalibrationStratumRecord', 'GroundingCalibrationLedger',
  '_OwnedCalibrationStore', '_recompute_owned_calibration_status', '_risk_ledger',
  '_owned_calibration_store', '_calibration_evidence_hash'),
 'src/polisyos/runtime/quality/grounding_benchmark.py': (
  'LabelDerivation', 'GroundingBenchmarkCase', 'GroundingBenchmarkDecision',
  'CalibrationAnchorSet', '_is_false_bind'),
 'src/polisyos/runtime/quality/grounding_relation.py': (
  'MechanisticSignature', '_relation_from_axes'),
 'src/polisyos/ir/analytics/literature.py': (
  'ClaimAdjudicationInputItem', 'ClaimAdjudicationResult', 'AdmittedClaimAdjudicationBatch'),
 'src/polisyos/data_forge/domains/academic/batch/claim_adjudication_policy.py': (
  'claim_metrics', 'claim_policy_publishable'),
}
result = {'source_commit': PIN, 'scope': 'five pinned owner Python files; no current-tree census', 'owners': {}}
for path, names in OWNERS.items():
 data = subprocess.run(['git', 'show', f'{PIN}:policy-engine/{path}'], check=True, capture_output=True).stdout
 source = data.decode()
 definitions = []
 for node in ast.walk(ast.parse(source)):
  if not isinstance(node, (ast.ClassDef, ast.FunctionDef)) or node.name not in names:
   continue
  row = {'name': node.name, 'line': node.lineno, 'kind': type(node).__name__}
  if isinstance(node, ast.ClassDef):
   row['complete_annotated_field_set'] = [
    {'name': item.target.id, 'annotation': ast.unparse(item.annotation),
     'default': ast.unparse(item.value) if item.value else None}
    for item in node.body if isinstance(item, ast.AnnAssign)
   ]
  else:
   row['complete_definition'] = ast.get_source_segment(source, node)
  definitions.append(row)
 result['owners'][path] = {'sha256': hashlib.sha256(data).hexdigest(),
                          'definitions': sorted(definitions, key=lambda row: row['line'])}
print(json.dumps(result, indent=2))
````

#### `_build/gy_grade_authority/architecture_identity_diff.py`

SHA-256 `b2fd300ead6104ea0f1dacf10eab3bce8685d7bc2cc969ae350009b98f5f601e`; 1588 bytes.

````python
"""Diff complete gate finding identities, never summary totals."""
import json
import os
from pathlib import Path
from tools.devx.architecture import guardrails as g

logs = ("architecture-final.log", "architecture-after-facades.log", "architecture-after-admitted-facade.log")
sets = {}
for log in logs:
    lines = (Path("_build/gy_grade_authority") / log).read_text().splitlines()
    sets[log] = {line[2:] for line in lines if line.startswith("- ")}
owner_paths = {str(p.relative_to(g.REPO_ROOT)) for p in g._iter_py_files()}
independent_paths = {str(Path(root, name).relative_to(g.REPO_ROOT))
 for root, dirs, files in os.walk(g.SRC_ROOT)
 if "__pycache__" not in Path(root).parts for name in files if name.endswith(".py")}
assert owner_paths == independent_paths
policies = g._parse_public_surface(g.DEFAULT_PUBLIC_MANIFEST)
current = {edge.key: edge for edge in g.collect_deep_import_edges(policies)}
baseline = g._load_deep_import_baseline(g.DEFAULT_DEEP_IMPORT_BASELINE)
result = {"source_file_type": "src/**/*.py excluding __pycache__", "source_denominator": len(owner_paths),
 "independent_source_denominator": len(independent_paths),
 "source_identity_difference": [], "finding_sets": {k: sorted(v) for k,v in sets.items()},
 "diffs": [{"before": a, "after": b, "added": sorted(sets[b]-sets[a]), "removed": sorted(sets[a]-sets[b])}
 for a,b in zip(logs, logs[1:])], "current_deep_import_creep": sorted(set(current)-set(baseline))}
text = json.dumps(result, indent=2) + "\n"
Path("_build/gy_grade_authority/architecture-finding-identity-diff.json").write_text(text)
print(text)
````

## codex/gy-def6-e11 analysis

### Intent, population and later incorporation

Recommendation: **do not recover this as an implementation lane; preserve the
existing branch ref as history**. No unique production mechanism was identified
as a prerequisite of the four grade rows. No stale branch, worktree or history was
mutated, and no test was run from that branch.

At investigation entry, main and the task's slice base were the same full commit
`f481538706316b0d94722fd2a3891b2067779a38`. Merge base with the stale branch:
`e708e8f77dbac35e3f8c164341cc19eed7695998`. The entire commit and changed-path sets
were walked. **82 ahead / 1,666 behind; 22 paths = 14 Python + seven JSON + one
ledger**. Python paths comprise five source, six test and three validator files.
The complete commit classification is **63 ledger-only + ten code/test + nine
artifact reissues = 82**. Author and committer dates run August 8–9, 2026; first
commit `44e01b523`, final `ba5946ebc`. All 21 non-ledger paths exist at the slice
base and have subsequent main history. This is a complete set, not a sampled log.

The work sought content-bound N8 provenance, independent N10a rederivation,
controlled catalog loading, non-consumer Depth-N verification, replay clocks,
complete import closure, and loader-owned callable-slot admission. The decisive
later incorporation is `431bcd7981b571c8c3943bfee55be8ce0bc0aa1f`, “bind cold
closeout inputs and projections”. Normalized ASTs were compared over every
top-level definition in all 14 Python paths and differing hunks were inspected.
At that successor, Depth-N tests match 99/99 definitions, N8 validator 85/85,
N8 tests 75/75, and catalog snapshot 27/27. All 11 production definitions changed
by final WIP `ba5946ebc` match the successor; at the task base ten still match
and the remaining function has gained qualified `.contextmanager` support.
These are code-equivalence findings, **not fresh behavioral test receipts**.

### Commit-specific recovery disposition

| Commit | Intended contribution | Disposition against current base |
| --- | --- | --- |
| d5a3495d0 | N8 provenance identity/recomputation and corruption controls | Incorporated by 431bcd798 and extended later |
| 50412092c | N8 artifact reissue | Historical receipt superseded; recompute, do not transplant |
| c88593cc1 | N10a writer-normalized rederive, no invented routing time | Incorporated and replaced by canonical operational-leaf reconciliation |
| 6d0ac2c18 | N10a trace/gaps/pack reissue | Superseded historical artifact wave |
| 537d8927d | Promotion reissue | Superseded identity-only wave |
| 691ae33f0 | Generation-cycle reissue | Superseded identity-only wave |
| b45911d49 | Controlled builtin Foundry registry and consumers | Incorporated; consumers further bound to module-owned lookup |
| 35279d30c | Delete ambient POLISYOS_PACKS_PATHS in registry test | Unique one-line test isolation choice; present necessity not_established |
| f6b24b0df | Controlled N10a trace reissue | Superseded within branch and on main |
| 16ca22088 | Depth-N/N10a isolated-verification promotion and migration | Incorporated and refined by a75543d2f, 431bcd798 and later admissions |
| a75543d2f | Source admission, predecessor/migration lineage, live-receipt checks | Incorporated and hardened later |
| 821df3115 | Independent N10a corrupt witnesses reaching consumers | Incorporated; successor adds controlled live-bundle input |
| 5b031e262 | N10a dependent artifact wave | Superseded by later main reissues |
| 062cb3f36 | Controlled Depth-N replay clocks | Incorporated and moved to canonical reconciliation |
| f12454c17 | Depth-N authority migration artifact | Authority posture retained; physical receipts superseded |
| b2fb6e52d | Promotion artifact wave | Superseded; current contract has v3 obligations/comparison proofs |
| bcbcf7d79 | Generation artifact wave | Superseded by current comparison projection |
| cfbf863b6 | Complete import closure before capture; missing-member/import-order controls | Production incorporated; old credal_first test variant may be retained as additional coverage |
| ba5946ebc | Loader-owned descriptor/property/contextmanager/cache callable slots | Incorporated despite WIP label; current implementation is further extended |

The **only identified unique recoverable choices** are test details in
`35279d30c` (`monkeypatch.delenv("POLISYOS_PACKS_PATHS", raising=False)`) and
`cfbf863b6` (an additional `credal_first` ordering instead of the successor's
`depth_first`). Neither warrants recovery without a current falsifier. The 63
ledger-only commits retain historical process evidence, not absent production
work; none should be replayed into the current lane.

### Collision with the three named contracts

This task does **not** change any `layer3_gy_*_contract.json`. Those architecture
paths are outside its allowed write set, so its diff has no direct collision.
If the later artifact owner recomputes them after S8, recovery must start from
current main; old stale-branch receipts cannot be merged as current evidence.

Complete recursive JSON walks count scalar leaves and empty containers by
key/index identity (one complete JSON document per row):

| Contract | Fork / stale / base leaves | Stale changed leaf identities | Current disposition |
| --- | --- | --- | --- |
| depth_n_universality | 16,586 / 36,083 / 43,032 | 26,302 | 22,578 changed values retained; real migration posture incorporated |
| generation_cycle | 1,695 / 1,695 / 2,620 | 43 | All changes are sha256 identity strings, all subsequently replaced |
| promotion | 1,873 / 1,873 / 2,915 | 67 | All changes are sha256 identity strings, all subsequently replaced |

The Depth-N changed set partitions into one contract hash, 27 domain-run leaves
and 26,274 proof-recording leaves. Every one of its three domain promotion rows
has the same authority projection in stale and base: `contract_testing`,
`authority_provenance=["verification"]`, all receipts non-consumer,
`verification_n9_sequence_non_consumer`, `not_promoted`, no certified candidates.
Receipt counts are education four, first_vertical three, unseen three.
Current contracts additionally carry comparison projection v2/rule v3; promotion
schema moved from stale v2 to base v3. Transplant would remove later semantics.

**GGA-STALE-COUNT-01 — independent reconciliation caught an absent/null error.**
The stale-branch investigator's first JSON diff reported 22,960 changes and
22,600 retained values. The coordinator independently flattened the complete
JSON documents to tuple key/index paths with an explicit missing-value sentinel;
the investigator replayed that method and a corrected string-path method. Both
now agree with the corrected table above. The initial `.get(path)` conflated
absence with JSON null, omitting 2,908 added-null and 434 removed-null identities
(3,342 changes), and counting 2,930 deleted non-null leaves as retained absence.
Correct retention is `22,600 - 2,930 + 2,908 = 22,578`, and changed identities are
`22,960 + 3,342 = 26,302`. The complete operations partition is 22,861 additions,
3,364 removals and 77 value changes. This corrects the earlier committed journal
by an append-only commit; no old receipt is silently rewritten or treated as
independent proof. Generation and promotion identity sets were unchanged by this
correction. Complete domain-key sets and the entire promotion mapping were also
reconciled, not just selected fields.

### Why it stopped, and what cannot be inferred

The final commit explicitly records: “Unreviewed successor-task work; no E11
admission, replay, or closure claim.” It records focused import-order/rebound
tests as green, but says the full confidence-ledger/importer/artifact wave was
intentionally not run under the GY-DEF6 stop rule. The **exact triggering rule
threshold is `not_established`** from the requested commit messages and ledger;
no procedural cause is invented.

The complete `.e11/gy-def6.ledger` contains **64 records**: one open, ten freezes,
ten review packages, 20 review results, 13 admitted findings and ten resolutions.
All 64 mark `research_only=true`. Its final frozen source is `cfbf863b6`, before
the WIP. Unresolved admitted identities are
`N11-IMPORT-ORDER-IDENTITY-1`, `ARCH-REBOUND-CALLABLE-ADMISSION-1`, and
`QUALITY-REBOUND-CALLABLE-ADMISSION-1`; the latter two are recorded blocking/batch.
There is no close, replay or terminal event in the complete record set.

The 64 records refer to **62 distinct** review/package/checklist/result/resolution
files under `tmp/e11/`; **zero are tracked on the stale branch**. Thus the ledger
establishes recorded declarations and events, not the absent reviews' full
semantic evidence. This limitation survives even where main incorporated code.

### Options, costs and losses

- **Recover the entire branch onto fresh main:** reconcile 82 commits/22 paths
  against 1,666 later commits, revisit superseded authority changes, then review
  and rerun the dependent receipt cascade. No production gain identified.
- **Extract specific choices:** the two named test variants only, after a present
  falsifier establishes value. Small code cost plus focused validation; no JSON
  transplant or historical E11 protocol replay.
- **Register debt:** only a demonstrated current missing behavior. Registering
  this whole branch as implementation debt would double-count incorporated work.
  Historical incomplete review is a provenance limitation, not missing code.
- **Abandon implementation recovery while preserving the ref (recommended):**
  lowest cost, no identified production capability loss, history remains usable.
  Deleting the ref would lose convenient historical evidence and is not authorized.

Readback during work found the external `main` ref advanced once to
`8a0d996fe53d9f689fd28b84fe649ce494030820`: its live distance became 1,667 behind.
Our branch/HEAD remained attached and unchanged by that event. All incorporation
claims and the 1,666 denominator above are deliberately bound to the original
slice base; the stale ref remains `ba5946ebc70bb63f30e4776d0426e19f37dffd31`.
No branch was moved to follow main.

Reproducible read-only starting commands (each invoked separately; use the pinned
base in distance/diff commands to reproduce the numbers above):

```sh
git rev-parse main f48153870 codex/gy-def6-e11
git merge-base f48153870 codex/gy-def6-e11
git rev-list --left-right --count f48153870...codex/gy-def6-e11
git log --reverse --format='%H|%aI|%cI|%s' f48153870..codex/gy-def6-e11
git diff --name-status f48153870...codex/gy-def6-e11
git show codex/gy-def6-e11:.e11/gy-def6.ledger
```

For every enumerated commit, `git diff-tree --no-commit-id --name-only -r COMMIT`
supplies its complete path denominator. Ledger-referenced path availability is
checked with `git cat-file -e REF:PATH`. No GitHub plugin or remote operation was
used, and no decision recorded on that branch is a prerequisite for these rows.
