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
