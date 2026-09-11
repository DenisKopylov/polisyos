# Debt nature survey — open workstream

Base `fc823071a7b6f2c9a573172aec3499ad6d138c0f`. The exact denominator is the 27 open
IDs in the reconciled main survey. This document characterizes claims; it changes no
standing. The register and ledger are not evidence about the tree.

Commands run from `policy-engine/`. Borrowed Python is explicitly named in commands;
imports in behavioral receipts bind to this worktree's source. Offline local bootstrap
failed on uncached `jaxlib==0.8.2`; this is an environment nonreceipt. No dependency or
source was altered to make a probe pass. Every count below names its own denominator.
Raw outputs are under `docs/superpowers/journals/debt-survey/open/raw/`; their hashes
and exact commands are retained in the workstream receipt index.

The common AST instrument walks the entire pinned `src/`, `tests/`, `tools/` and
`architecture/` Python sets: Git-tree and independent filesystem identities agree;
`ast.walk` and `NodeVisitor` agree on definitions/classes/calls, including async.
There are 5,686 Python files, of which 2,653 are in `src/`, with no parse ambiguities.
The full path denominator is enumerated in `raw/python-denominator.json`. Calls are
syntactic occurrences; they are not automatically dynamic reachability proof.

## `pyproject-exceeds-its-declared-line-budget`

**Measured:** the actual registered gate returns exit **1 / FAILED**, complete
coverage, **307 physical lines / one `pyproject.toml`**, ceiling 300. The historical
305-line premise is stale. The mechanism now explicitly says it counts comments and
blank lines and does not measure configuration complexity, dependency correctness,
resolver cost or TOML validity. Evidence: `pyproject.toml@fc823071a` and
`tools/quality/validation/repository_structure_phase0.py@fc823071a`.

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m tools.cli validation repository-structure-phase0 gate --gate pyproject_size --json
```

Full output: `raw/pyproject-gate.json`. **Narrower:** the warning is a bounded physical
size fact, not a demonstrated semantic-maintainability defect. **Wider:** no wider
manifest population follows from this single-file gate. **Reduction/class:** no shared
deciding property with dependency correctness, source-schema unreadability or invocation
coverage is established. A shared DevX holder would not make those one debt. Unblocking
an edit and discharging the unchanged size predicate are distinct; neither was done.
**Unestablished:** the maintainability effect of any particular extraction and historical
attribution of the excess; no historical replay is claimed.

## `stale-worktree-registrations-collide-with-new-lane-names`

**Measured, current shared Git state rather than pinned source:** Git porcelain and
independent `.git/worktrees/*/gitdir` records agree on linked-path identities. There are
**78 registrations / the complete current registration set**, including this survey;
**53 paths are absent**. The row's 72 denominator has decayed; the missing-directory
count has not. The supplied pre-survey 77 becomes 78 after this worktree is added.

```sh
python3 docs/superpowers/journals/debt-survey/open/probes.py worktrees
```

Full output: `raw/worktrees.json`. **Narrower:** no loss of branch objects or source is
proved by missing directories. **Wider:** commissioning has two independently checked
names, a branch and a registered path; missing-directory cleanup alone says nothing
about branch-name reuse. **Reduction/class:** allocation failure in other debt rows is
not this shared Git-registration mechanism. Here availability of two names unblocks
commissioning; discharging accumulated registrations and the prompt preflight property
are separate predicates. **Unestablished:** the row's historical 43 merged-branch count
and universal compliance by future prompts. No registration was pruned.

## `calibration-report-fixture-blanket-fields`

**Measured:** the complete exact-kind AST population in
`tests/_helpers/runtime_http.py@fc823071a` has **one calibration-report writer call**,
at line 398, through `_put_json`. Executing the actual helper adds three keys:
`authority_boundary`, `authority_result`, `legacy_path_disposition`. All three are
outside the actual **15-field** `CalibrationReport` model in
`src/polisyos/foundry/calibration/report.py@fc823071a`; its `extra="forbid"` admission
rejects each as `extra_forbidden`. The unmodified payload is accepted when the separate
version-pattern field is omitted from both variants.

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/probes.py calibration
```

Full output: `raw/calibration.json`. **Narrower:** the strict producer does not silently
ignore these fields; the fixture bypasses that strict shape using a generic mapping
writer. **Wider, inferred:** `_with_runtime_fixture_authority` acts on any mapping that
lacks `authority_boundary`, so the mechanism is broader than the one artifact kind.
Which other kinds violate their own schemas is unestablished and is not a new row.
**Reduction/class:** shared fixture decoration is the candidate mechanism; a common
three-key shape is not proof that every decorated artifact is invalid. No pair reduction
is established. Availability of the typed serializer is an enabling fact; discharge
would be the actual persisted fixture agreeing with its producer, not changing a label.
**Unestablished:** full HTTP fixture persistence/replay and every other kind's validity.

## `foundry-requirements-flat-manifest-consumer-unmeasured`

**Measured:** executing the actual Runtime helper with a declared three-input contrast
(absent manifest / flat matching manifest / flat nonmatching construct) yields
`fail / pass / fail`, and the matching case emits `runtime_consistent`, fabricated
`gate://`, `uncertainty:`, `limitation:` and `method-result:` references from the target
name. The complete returned reports are retained. Evidence:
`src/polisyos/runtime/quality/producer_pipeline.py@fc823071a` and
`src/polisyos/foundry/methods/selection/requirements.py@fc823071a`.

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/probes.py requirements
```

Full output: `raw/requirements.json`. The complete 2,653-source-Python census locates
four direct calls to `select_method_candidates_for_requirements`: Foundry's method
report, Runtime's requirement pipeline, G2 method bindings and workspace recomputation.
Only a trace of their supplied arguments establishes manifest consumption; the mere
presence of those calls does not. Replays:

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/inspect_tree.py ast '(^|\.)(select_method_candidates_for_requirements|_method_candidates_from_capabilities|_manifest_rows)$' --source-only
```

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/inspect_tree.py ast '(^|\.)(_foundry_requirement_report|build_g2_method_requirement_bindings|build_foundry_method_report)$' --source-only
```

Full outputs: `raw/requirements-ast.json`, `raw/requirements-callers-ast.json`.
The actual helper's source parent is `run_requirement_spec_producer_pipeline`; this is
a source trace, not a replay of a served request. Existing selection tests also run
exit 0 over their complete four-test-function file:

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/foundry/methods/selection/test_method_requirements.py -q
```

**Narrower:** blanket `mechanism_unmeasured` no longer describes the helper boundary.
**Wider, inferred:** the predicate is manufacture of method-validity-looking evidence
from a manifest declaration, not simply a duplicate parser. **Reduction:** Ukraine's
unselected method contracts concern actual execution consumers; this concerns how a
selection report acquires its asserted evidence, so they are not established as one debt.
**Class:** potential shared input-owner/authority substitution, but common repair and
holder across those consumers are unestablished. A valid route owner could enable
admission; discharge requires the real consuming path to refuse false evidence.
**Unestablished:** full production input arrival, downstream authority effect and
equivalence to an existing canonical owner. No helper result is promoted to that claim.

## `udf-retained-source-schema-is-malformed-and-stays-ambiguous`

**Measured:** this is external retained data, not a malformed tracked source file.
The coordinate is supplied by finding **PR1-SA02** in
`docs/superpowers/journals/gy-phase5-evidence/pr1/stage3-scope-audit.md@fc823071a`;
fresh reading of that actual current file reproduces
`Expecting ',' delimiter: line 49 column 3 (char 1013)`. Its SHA-256 is
`a09bf61d5f4590bf98b7fbee6bf36968d734ce68a180b8c390de50125cf238a0`.

```sh
python3 docs/superpowers/journals/debt-survey/open/probes.py udf
```

Full output: `raw/udf.json`, enumerating the **7 direct `.json` siblings** in
`production_data/canonical/local_data_20260501/policy_engine_data/curated/`, with
glob/independent-iterdir identity equality: 6 readable, 1 ambiguous. Separately,
the complete **2,844 tracked `.json` files** in the product's pinned Git tree all parse;
the independent current-index identity set agrees after excluding only this survey's
added receipts:

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/probes.py json-readability
```

Full output: `raw/json-readability-reconciled.json`. **Narrower:** the location and exact
syntax failure are established; “every source is unreadable” is not. **Wider:** the
affected property is completeness of any *declared* population that includes this file;
its denominator may still be enumerated, but extraction from the unreadable member is
ambiguous. **Reduction/class:** no identity with the Lex API's absent-column defect is
established. They share a data-read prerequisite, not a demonstrated repair or holder.
Readable bytes or an explicit scope exclusion would unblock extraction; successful
full-population extraction is a separate discharge property. **Unestablished:** the
entire retained portfolio extraction, and whether these untracked bytes equal the
historical bytes at the Git base. No historical 6,417-file total is adopted as current.

## `ds18-epoch-history-independent-holder-unappointed`

**Measured, narrower:** the producer has a non-test CLI consumer,
`audit_epoch_custody`, which persists and reopens the exact request and result.
The complete seven-item `test_epoch_custody_audit.py` replay passes (exit 0).
Evidence: `src/polisyos/runtime/quality/epoch_custody_audit.py@fc823071a` and
`src/polisyos/runtime/quality/chronology_custody.py@fc823071a`.
Commands/complete outputs: `epoch-source`, `epoch-factory-body`, `epoch-custody-tests`
in the command appendix and receipt index.

**Wider:** the source production factory installs three fixed empty dependencies:
`NoEpochAnchorAppointmentResolver`, `EmptyEpochAnchorAuthorityRegistry`, and
`UnavailableSignedArtifactEvidenceRepository`. The resolver returns distinct
`acceptance_owner_not_established` and `anchor_holder_not_established` outcomes.
The CLI receipt expressly limits itself to `custody_provider_invocation_only`
and leaves request-reference verification `not_established`. Thus observed provider
invocation and admitted independent custody are different properties. An appointment
arriving as data has no demonstrated production loader in this exact factory.
**Reduction:** no identity with a predicate-policy signer or transition signer is
established: custody independence concerns acceptance/readback, not policy truth or
transition authorization. **Class:** epoch rows share a refusal vocabulary but not
one authority purpose, repair or holder. Appointment intake could unblock custody;
discharge would require independently admitted custody and exact persisted readback.
**Unestablished:** a live positive appointment-to-factory path and external holder
independence. The green negative tests do not establish either.

## `ds15-semantic-epoch-qualification-authority`

**Measured, narrower:** `admit_acquisition_with_production_semantic_epoch` is called
by the non-test `acquisition_epoch_admission.run_admission` CLI. The complete six-item
admission test replay passes (exit 0), including real CLI invocation, isolated owner
stores, exact persisted negative receipt comparison, malformed inputs and receipt
corruption. Evidence: `src/polisyos/runtime/quality/acquisition_executor.py@fc823071a`,
`src/polisyos/runtime/quality/acquisition_epoch_admission.py@fc823071a` and
`tests/unit/runtime/quality/test_acquisition_epoch_admission.py@fc823071a`.
Commands: `semantic-production-body`, `epoch-source`, `semantic-admission-tests`.

**Wider:** this production composition explicitly constructs both qualification
components with `from_unallocated_policy_authority`; it has no authority parameter.
The CLI accepts only the persisted-negative receipt type and raises
`acquisition_epoch_activation_consumer_not_established` for the positive type.
The built bridge therefore discharges negative production observation, not positive
activation. Its current refusal is `policy_admission_missing`, with prepared/admitted
boundary references but no history-append or chronology qualification.
**Reduction, inferred:** the same predicate-policy admission may be the prerequisite
of the DS18 and N12 policy rows; this row additionally owes acquisition-specific
activation and persistence, so the complete debts are not established as identical.
**Class:** a shared empty policy index can unblock several paths; each path owes its
own exact positive and negative result proof. **Unestablished:** a production
appointment loader and a positive CLI activation consumer; no repair is made.

## `ds18-epoch-predicate-policy-signer-unappointed`

**Measured:** the delivered policy-admission refusal is present in the same production
semantic composition above, and `ArtifactEpochValidityAuthorityGate` consumes epoch
policy receipts rather than accepting presence alone. Evidence:
`src/polisyos/runtime/quality/epoch_validity_cascade.py@fc823071a` and the semantic
composition cited above. Commands: `signer-body`, `epoch-source`,
`semantic-production-body`, `semantic-admission-tests`.

**Narrower:** a policy contract and refusal consumer exist; blanket missing-mechanism
language would be false. **Wider:** admissibility of a policy receipt is separate from
providing a signer. The exercised acquisition factory deliberately loads no positive
policy authority. **Reduction, inferred:** candidate duplicate of
`gy-n12-epoch-predicate-policy-authority-unappointed` on the deciding property of
admitting an independently authorized epoch predicate policy. Exact cross-path scope
equivalence remains unestablished; acquisition's positive adapter is an additional
obligation. **Class:** policy authorization does not authorize transition signing,
history custody or a current-decision lineage carrier. Appointment evidence would
unblock receipt admission; each consumer's independently bound policy acceptance and
refusal tests would discharge its engineering claim. **Unestablished:** appointment
validity, policy adequacy and a production positive route. No status inference follows.

## `ds18-epoch-transition-signer-unappointed`

**Measured:** `NoEpochTransitionSigningAuthority.sign_transition` returns the named
`epoch_transition_signer_not_established` nonreceipt. The return algebra also
distinguishes signing-profile mismatch from exact-evidence unavailability. Evidence:
`src/polisyos/runtime/quality/epoch_validity_cascade.py@fc823071a`.
Commands: `signer-body`, `epoch-source`.

**Narrower:** an explicit refusal contract exists. **Wider:** accepting a signer is not
equivalent to producing an admitted transition. The A/C workstream measures the
producer's separate exact-evidence refusal; this open row does not absorb that row's
engineering obligation. **Reduction, inferred:** candidate duplicate of
`gy-n12-epoch-transition-signing-authority-unappointed` only for the purpose-bound
transition signing appointment. The proof must preserve any distinct scope or epoch
population. **Class:** a signing authority can unblock signing; it cannot discharge
the transition producer's evidence, verifier or current-decision application proofs.
**Unestablished:** a live positive appointed signer and exact equivalence of the two
appointment scopes. A typed negative alone does not establish engineering completion.

## `DS11-SCOPE-ADJUDICATION-RECORD`

**Measured, narrower:** the strict `ScopeAdjudicationCandidate` exists, so absence of
all scope artifacts is false. The complete eight-item source contract test replay
passes (exit 0). The artifact fixes `status=candidate_only`, both authority and closure
effects to `none`, an empty `authoritative_for`, and six explicit prohibited uses.
It retains separate `scope_predicate_resolver_unappointed` and
`scope_adjudication_claim_lifecycle_consumer_unappointed` limitations. Evidence:
`src/polisyos/core/contracts/scope_adjudication.py@fc823071a` and
`tests/unit/core/contracts/test_scope_adjudication.py@fc823071a`.
Commands: `scope-source`, `scope-body`, `scope-candidate-tests`.

**Wider:** an authority-grade scope decision and its claim-head admission are distinct
from candidate reasoning. A candidate constructor cannot acquire either purpose by
appointment. **Reduction:** not identical to general claim lifecycle orchestration:
one concerns the admitted predicate and purpose, the other the signed owner-event
append/CAS path. **Class:** shared head machinery would enable carriage; discharging
this row requires that this specific scope decision can be produced, admitted and
refused for its own reasons. **Unestablished:** that authority-grade source producer,
its production caller and a scope decision advancing the actual claim head. The
candidate tests provide no such receipt.

## `DS11-PUBLIC-SIGNATURE-POPULATION`

**Measured, narrower:** the actual vocabulary is
`PublicVerificationRecordPopulationProvider`, not a guessed population-producer name.
Its `resolve` traverses the issuance inventory and verifies reports, but its return
type and every terminal return are `PublicSignaturePopulationNonReceipt`.
Three existing tests pass (3/3 selected items, exit 0): empty issuance, real signed
report inventory with no governed member, and corruption changing the nonreceipt.
Evidence: `src/polisyos/scientist/governance/continuous/published_signature_custody.py@fc823071a`;
commands `population-body`, `population-tests`, `scope-source`.

**Wider:** this is governed-record admission, not merely rendering or signing.
`RuntimeContainer.startup` installs this exact provider from the public report
service; the fixed `promoted_record: Literal[None]` contract cannot carry a governed
member. **Reduction, inferred:** it shares an upstream admitted promoted record with
the public-decision rows, but its deciding property is complete, custody-bound
population enumeration and maintained membership. A page can render one record and
still fail that property. **Class:** a promoted-record producer could unblock all
those consumers; population, publication, verification and maintenance each owe
separate semantic tests. **Unestablished:** any actual governed member and full
deployed worker execution. These report tests cannot supply either.

## `ds15-signed-v2-delegation-mandate-owner-authority`

**Measured, narrower:** the current source has `CurrentMandateOwnerEvidence` and
the gateway's `_resolve_current_mandate_authority`, which reopens signed CAS evidence,
checks owner, purpose, currentness, validity interval, revocation, rule version and
signer identity. Missing owner/ref produces `current_mandate_authority_not_established`.
Evidence: `src/polisyos/runtime/quality/agent_action_authority.py@fc823071a`;
command `ds15-authority-source`, with that exact method as the readable source.
The source census still finds no direct constructor call to `AgentActionAuthorityGateway`
among the complete 2,653 source Python files; this is a bounded static result.

**Wider:** the deployed action service has a real optional
`AcquisitionAuthorityGatewayProvider`, reached by `request_decision`, `execute`
and `handle_job`; `_require_authority_provider` refuses
`acquisition_authority_producer_missing`. `RuntimeContainer.startup` supplies only
the override slot. Thus consumer machinery exists, while evidence production and
its deployment composition remain separate. **Reduction:** not the deterministic
admission-bundle signer: delegation authorizes the mandate/current owner, whereas
the bundle authorizes particular invocation inputs. **Class:** both reach one action
gateway, but require distinct evidence purposes and producers. Admitted delegation
and a provider could unblock the path; exact tenant/run/operation effects and
revocation refusal would discharge it. **Unestablished:** real signed external
delegation, its production provider and a live current-mandate positive run. No
name census is promoted to a repository-wide semantic absence claim.

## `ds15-production-n13b-execution-handshake`

**Measured, narrower:** `WorldBankWDIAcquisitionExecutionPort` exists and is constructed
by `build_production_world_bank_wdi_execution_port`. The actual action service
constructs that factory when no execution override is supplied and binds its
`handle_job` callback to the control service. Thus the historical strict-port
`producer_missing` premise is false. Evidence:
`src/polisyos/runtime/http/services/acquisition_surface_execution.py@fc823071a`,
`src/polisyos/runtime/http/services/acquisition_action_service.py@fc823071a` and
`src/polisyos/runtime/http/container.py@fc823071a`; command `ds15-authority-source`.
The exact retained integration replay is `n13-binding-tests`; its result is recorded
in the command appendix rather than borrowed from a prior lane.

**Wider:** default execution-port installation is distinct from the still-empty
authority provider; request authority and durable worker execution are different
boundaries. Scope is World Bank WDI, not an arbitrary connector population.
**Reduction:** cannot reduce to delegation or semantic qualification: those admit
permission and epoch truth, whereas this row asks for execution and durable handoff.
**Class:** DS15 prefix is not one repair or one holder. A qualified route/authority
unblocks execution; an actual service-to-worker result with persisted readback and
same-case refusal semantics discharges the handshake. **Unestablished:** a positive
production request using real external mandate evidence and an actual external fetch.
Test-port results are not reclassified as that production instance.

## `GY-DEF22`

**Measured, narrower:** the dependency-discriminant producer, Foundry resolver and
N8/N10a/chronology readers exist. The producer is under `tools/`, so a `src/`-only
census would miss it. Evidence:
`tools/quality/validation/check_layer3_gy_value_gate_contract.py@fc823071a`,
`src/polisyos/foundry/methods/catalog/dependency_profile.py@fc823071a`, and
`tools/quality/validation/execute_gy_n12_artifact_transition.py@fc823071a`;
command `def22-source`.

**Measured counterexample to current engineering-complete standing:** the exact
five acceptance nodes return **exit 1: 3 failed / 5, 2 passed / 5** (`def22-tests`).
CB-I01, CB-I02 and CB-I02A stop at the N8 producer's actual Foundry resolution,
which returns `DigestPredicateMismatch`; CB-I03 and CB-I03A pass. The diagnostic
assertions within the second and third tests pass before their governing-byte
comparison fails to obtain a companion. This is not five passing acceptance nodes.
No pin or governed artifact is regenerated. **Wider:** correctness adjudication and
the current ability to regenerate/read the bounded diagnostic are independent.
An appointed reviewer does not remove this mismatch.

**Reduction/class:** not the same debt as promotion admission or the absent positive
Foundry authority capabilities. A diagnostic may remain non-decisive while its own
replay is broken. Source/input pin reconciliation could unblock these three nodes;
their intended acceptance assertions and the separate appointed-correctness receipt
would discharge their respective claims. **Unestablished:** complete P41 input
disjointness and exact slice-base replay, hence no inherited-red attribution;
no claim that the mismatch was introduced by this survey or by a named earlier lane.

## `foundry-ukraine-method-contract-consumer-residual`

**Measured, narrower:** the producer is built. AST enumeration of `contract_specs`
agrees on exact identity with the independent set asserted by the real owner test:
**13/13 keys**, all enumerated below. Four targeted owner/materialization tests pass
(4/4 items, exit 0), including full persisted input validation, corrupted stage
refusal, FQN mismatch and deterministic roundtrip. Evidence:
`src/polisyos/foundry/data_plane/bindings.py@fc823071a`,
`tests/unit/foundry/data_plane/test_bindings_multiscale.py@fc823071a`,
`tests/unit/foundry/data_plane/test_method_contract_materialization.py@fc823071a`;
commands `ukraine-key-reconciliation`, `ukraine-tests`, `ukraine-source`.

The denominator is `d1_multiplex_network`, `d1_trade_network`,
`d1_trade_network_causal`, `d1_distress_network`, `d1_distress_network_causal`,
`d1_public_service_network`, `d1_public_service_network_causal`,
`d2_panel_observational`, `d2_dynamic_treatment`, `d2_microsim_survey`,
`d2_survival`, `d2_panel_econometric`, `d3_microsim_survey`.

**Wider:** `BindFoundryInputsNode` provides the observed panel selection bridge;
other existing dynamic-treatment or survival consumers do not establish that those
Ukraine bundle selections reach them. The producer's `consumer_missing` annotations
are not independent absence evidence. **Reduction:** distinct from flat-manifest
selection, which manufactures method-evidence references; this concerns execution of
particular persisted method inputs. **Class, inferred:** shared selected-input bridge
may provide common plumbing, but the non-panel keys have different method contracts
and owe their own execution/negative proofs. A Scientist workflow consumer can unblock
a selected input; correct persisted results and invalid-input refusal discharge it.
**Unestablished:** actual production requests for the twelve non-panel keys and their
full independent consumer enumeration. This survey does not convert one panel witness
into thirteen execution receipts.

## `int-r2-ceiling-vocabulary-owners`

**Measured, narrower:** all **8/8 declared comparison relations** have a software
owner in `src/polisyos/fabric/evidence/ceiling_vocabulary.json@fc823071a`:
population, jurisdiction, purpose_audience, source_target_context, evidence_class,
maintained_assumptions, maximum_claim_strength, maximum_commitment_stage.
The separate **5/5 semantic vocabulary rulings** in
`docs/reference/canonical-vocabulary-crosswalk.v1.json@fc823071a` have
`semantic_owner=null` and empty `registered_terms`: relation_claim_strength,
capacity_stages, estimand_binding_strength, legal_normative_write_operations,
assurance_levels. Those are different denominators. Commands:
`vocabulary-distribution`, `vocabulary-semantic-source`, `ceiling-demand`.

**Measured distribution, not ownership by word count:** across all **2,653 source
Python files**, estimand occurs in 176 files: Foundry 105, IR 36, Runtime 19,
Scientist 12, DataForge 2, Fabric 2. Normative occurs in 141 files across **13 packages**:
Runtime 38, DataForge 36, Scientist 35, Lex 9, Core 6, IR 6, Evidence/Fabric/Foundry/PDC
2 each, DataRequirement/LegalRequirement/PolicyGrammar 1 each. `write_operation`
and `assurance_level` each occur in 0/2,653 files. These literal file counts include
prose. AST definitions and callers establish real `NormativeModelCompleteness` and
`NormativeAuditStatus` in `ir/analytics/normative_arbitration.py`, plus its governance
node/pass consumers. Therefore dispersed naming does not mean only an adjective.

**Wider:** comparator, semantic authorization and registered terms are three
different obligations. The complete 683-file demand corpus includes assurance-level
requirements in the published crosswalk and INT-R2 handoff, independently of source
name absence. **Reduction:** estimand ordering is a candidate constituent reduction
with the separately named estimand row, not grounds to fold every vocabulary.
**Class refuted:** the eight comparison fields are not one semantic vocabulary or
one authoritative holder. Accepted definitions and purposes could unblock each
comparison; unknown/incomparable refusal and purpose-specific validity would discharge
its distinct proof. **Unestablished:** whether any existing normative owner supplies
the exact requested ceiling relation and who can authorize/register each value.

## `estimand-binding-strength-terms-unregistered`

**Measured, narrower:** the delivered estimand AST, normalizer and compiler exist;
they are not the missing ordering. The crosswalk's exact
`estimand_binding_strength` entry has no mapped relation, no semantic owner and no
registered terms. Evidence: `src/polisyos/ir/analytics/estimand.py@fc823071a`,
`src/polisyos/foundry/methods/catalog/causal/estimand_compiler.py@fc823071a` and
the crosswalk above; commands `vocabulary-distribution`, `vocabulary-semantic-source`.
**Wider:** structural estimand normalization cannot prove an ordering of binding
strength that preserves population, contrast, outcome, horizon, intercurrent events
and regime. **Reduction, inferred:** this is the estimand-specific conjunct of the
ceiling row; shared deciding property is a registered purpose-valid partial order,
including declared incomparability. The broader row has four other vocabulary
subjects and distinct authorization questions. **Class:** an ordering engine could
be shared, but justified edges and binding identity require the estimand owner.
Registered semantics could unblock comparison; horizon/regime-only changes refusing
false equality would discharge the specific negative property. **Unestablished:**
equivalence of an existing delivered ordering under another vocabulary; no universal
absence is inferred merely from the crosswalk's empty entry.

## `corr-wave-unowned-destinations`

**Measured, narrower:** the five routed subjects separate into two minting acts
(CORR-B1 legal-subject identity; CORR-B2 external causal evidence), two purpose-specific
appointments (CORR-I2/I3), and CORR-I1 qualification. The source legal comparator
exists and explicitly does not establish legal authority; that does not decide who
may mint its inputs. Evidence:
`src/polisyos/foundry/validation/legal_correspondence.py@fc823071a`;
commands `correspondence-source`, `identity-authority-boundary`, `ceiling-demand`.

**Measured authority-reading correction:** the cited identity decision's frontmatter
forbids `jurisdiction_specific_legal_conclusion` and `capability_claim` use. Its §9
item 6 operational boundary retains minting with an appointed owner and explicitly
uses **GY-O0 inside PolicyOS** as its worked example. It does not imply permanently
external minting. Evidence:
`docs/system-design-decisions/policyos-identity-and-custody-boundary.md@fc823071a`,
§5 and §9 item 6, read through the operational conclusion. This survey applies it
only to the claimed authority's scope, not to decide a legal conclusion.

**Wider:** the deciding property for B1/B2 is the particular act's §5 classification,
not the comparator's package owner or the phrase “not a court.” **Reduction:** B1
enables legal correspondence and B2 may enable causal correspondence; those debts
have additional admission/consumer proofs. I2/I3 share procedure, not competence or
purpose. **Class refuted:** these five destinations are not one appointment or one
repair. A supported scope/allocation act could unblock ownership; correctly sourced
and admitted identities/evidence would discharge their consumer obligations.
**Unestablished:** specific §5 classifications of B1/B2, valid appointer identities
and whether any external source can meet the required semantic evidence contract.

## `s3-r12-legal-knowledge-store-selects-an-unavailable-version`

**Measured correction:** this is an unavailable SQL **column**, not evidence that
a particular version value is absent. The actual
`LegalKnowledgeStore.load_provisions_by_anchor` call against the current canonical
read-only database raises `BinderException: Referenced column "version_id" not found`.
`DESCRIBE` and `PRAGMA table_info` independently agree on the complete **31-column**
`lex_provisions` schema. Evidence: `src/polisyos/lex/knowledge/store.py@fc823071a`;
command `lex-schema`, which names the actual external database and selected anchor.

**Narrower:** no missing law/version content follows from that binder error.
**Wider, inferred from the SQL:** every nonempty document/anchor request through
this method reaches the same invalid SELECT before row filtering. This is a method
and deployed-schema compatibility boundary, not one bad statute. **Reduction/class:**
not the law-to-lever correspondence debt; readable source content does not establish
semantic correspondence. Compatible owner/schema selection could unblock retrieval;
correct version/anchor semantics and readback would discharge it. **Unestablished:**
the complete call-site population's dynamic exposure, other deployed database schemas,
and these untracked database bytes at the historical Git base.

## `gy-builder-mechanisms-have-no-production-caller`

**Measured, narrower:** the complete registered Python invocation check exits **0**,
but explicitly reports **partial coverage**, `runtime_invocation_established=false`.
Its 5,674-file source/tools/tests denominator differs from this survey's 5,686 only
by the twelve architecture Python files. Both source sets contain 2,653 files.
The full output is retained, with its compact exact-family selection and hash in
`invocation-selection`; the expensive replay is `production-invocation`.
Evidence: `src/polisyos/runtime/quality/production_invocation.py@fc823071a`.

The delivered AQ path is `acquisition_assurance.run_corpus` to
`check_gy_acquisition_assurance`; CR has its module entry plus
`constrained_response`/`response_corpus_evaluator` to `tools.check_response_corpus`.
Locale catalogue reading also reaches `check_multilingual_locale_census`; it is no
longer only a private module CLI. Receiver/deferred calls unresolved by the checker
remain unresolved, not absent. CB's `run_instrument`/`read_instrument_result` and
ML's `run_assurance`/`read_assurance_result`/`run_source_content`/`read_source_content`
still have no resolved non-test callers in this complete static model. Independent
AST occurrences and the actual caller bodies bound that interpretation.

**Wider:** runtime invocation, command discovery and task allocation are three
different quantities. The independently enumerated 683-file demand corpus contains
actual `GY-CB2` and `GY-ML2` rows in the active GY plan, naming these consumers and
their persistence/readback obligations; their existence is allocation evidence,
not proof of a built bridge (`builder-demand`, `demand-independent`).
**Reduction/class:** not one repair: operator trials, multilingual renditions,
adaptation decisions and non-data acquisition have different evidence and holders.
One invocation checker can observe regressions, not build or discharge them all.
Real consumers unblock use; each existing producer's persisted/reopened result and
unchanged negative must prove its own invocation. **Unestablished:** dynamic callback
and receiver routes outside the static model, and real operator/rendition production
runs. No `uninvoked` string alone establishes universal source absence.

## `s3-law-to-lever-correspondence-is-unverified`

**Measured, narrower:** source-relative recognition, independent addressed subject
inputs, persistence and the real law/lever consumer now exist. The actual constructed
transposition test plus the full legal-correspondence test file passes **23/23 items,
exit 0** (`correspondence-tests`). Evidence:
`src/polisyos/foundry/validation/legal_correspondence.py@fc823071a`,
`src/polisyos/runtime/quality/intervention_substrate.py@fc823071a`;
command `correspondence-source`.

**Wider:** `LegalCorrespondenceResult` limits recognition to `source_relative`,
current entity binding to `consumer_asserted`, legal authority to `not_established`,
and authority status to `blocked`. Successful comparison cannot confer semantic
legal authority. This matches **W5-K07**'s existence/governing-relation distinction
and **W4-K01**'s custody/correctness distinction, not an inference that PolicyOS may
never own a minting act. **Reduction:** shares the CORR-B1 input dependency but not
the whole allocation question. **Class refuted with CG2:** both compare proposed
counterparts and can share custody/review plumbing, but legal governance and causal
instantiation have different predicates, competence, reference populations and
positive labels. Independent subject evidence unblocks comparison; exact semantic
authority and false-counterpart refusal discharge the governed legal claim.
**Unestablished:** independent positive legal subject membership and adjudication,
current production correctness or any calibration bound. Synthetic positives and
constructed negatives do not supply those quantities.

## `cg2-production-relation-gold-acceptance-unspecified`

**Measured, narrower:** input-derived calibration frames and a constructed-mismatch
refusal suite are implemented by `grounding_calibration.py`; source discovery and
exact-request replay are implemented by `ProductionCG2CalibrationSource`.
Evidence: `src/polisyos/runtime/quality/grounding_calibration.py@fc823071a`,
`src/polisyos/runtime/quality/production_grounding_calibration.py@fc823071a`;
commands `correspondence-source`, `cg2-source-body`, `cg2-refusal-tests`.
The complete selected two-file replay returns exit **1**: **20 passed and 11 failed / 31 collected cases**. One refusal-suite assertion reports `constructed_mismatch_not_structurally_refused` and `matched_control_not_structurally_supported`; ten proof-world cases fail before their assertions because the required local CAS manifest is absent. This does not establish an inherited failure or a positive gold bound. It separates a reproduced refusal assertion from a missing local substrate; neither is waived.

**Wider:** the actual `RelationAcceptanceSlot` fixes relation gold, accepted
adjudicator and outcome-sensitive rule to `None`. Its source result also fixes
candidate operator and reference epoch to `None`, admitted relation count to zero,
CG2 to cold start and production value eligibility to false. This is a deliberate
source-discovery/refusal mechanism; merely providing a person does not populate its
missing positive inputs. **Reduction, inferred:** the residual relation acceptance
is an upstream deciding property shared with GY-PA1, but S8 authorization/ranking
adds a separate consumer obligation. **Class:** causal calibration and legal
correspondence share procedure, not gold or discharge proof. Qualified reference
identities and independent labels could unblock calibration; a dated population,
correct acceptance rule and justified bound would discharge it. **Unestablished:**
any real admitted positive relation population, independent gold or correctness bound.

## `GY-PA1`

**Measured, narrower:** `build_authorized_value_schedule` and actual source callers
exist in the S8 value-choice owner; production source discovery/replay also exists.
The old blanket S8-producer and source-consumer absence does not describe this tree.
Evidence: `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py@fc823071a`
and `src/polisyos/runtime/quality/production_grounding_calibration.py@fc823071a`;
commands `correspondence-source`, `cg2-source-body`, `cg2-refusal-tests`.

**Wider:** the fixed relation-acceptance and production-value refusal above survives
all successful source discovery. Authorizing a value schedule, discovering a paper,
matching a proposal to a reference intervention, and establishing treatment evidence
are different propositions. No current 4,032-row historical corpus total is adopted.
**Reduction, inferred:** only the outstanding proposal/reference acceptance conjunct
may reduce to CG2; the full PA1 value authorization, persistence and ranked-consumer
chain does not. **Class:** a shared CG2 decision could unblock upstream relation
evidence; each S8/N8 consumer still owes its own purpose-bound value receipt and
negative refusal. **Unestablished:** actual production value-ready receipt population,
independent relation acceptance and complete positive S8→N8→promotion behavior.
The current negative source-discovery type cannot be counted as a positive producer.

## `gy-j-positive-evidence-admission-producer-has-no-owner`

**Measured, narrower:** source attempts, real S1 composition, persisted accounting
and refusal exist. `_compose_production_case_admission` always supplies
`evidence_profile="unsupported"`, a non-overridable missing-original-construct-owner
reason, and `decision_owner_ref=None`; it requires the real S1 result to be
`typed_blocker`/`publication_blocked`. Thus the exact canonical path cannot produce
an admitted positive by changing an owner string. Evidence:
`src/polisyos/runtime/quality/workspace/loop.py@fc823071a`,
`src/polisyos/runtime/quality/graded_outcomes.py@fc823071a`;
commands `gyj-source-body`, `correspondence-source`.

`gyj-report` independently reconciles the persisted report's member identities
against its three outcome partitions: **0 graded / 1 complete recorded member**,
one non-value `a_spec_gap`, period `report_generation`. Evidence:
`architecture/policy_design_case/layer3_gy_graded_outcome_routing_report_v2.json@fc823071a`.
This is recomputation of recorded arithmetic, not a new production observation.
**Wider:** positive scientific admission policy and its producer are distinct from
the runtime owner of execution/accounting. **Reduction:** no identity with the
deterministic action-admission bundle or relation calibration is established; they
admit different objects. **Class:** both missing-owner cases need allocation, but
one repair or holder does not follow. A defined original-construct evidence admission
could unblock a positive; actual independent evidence, exact persisted admission and
the real report's unchanged population rules would discharge it. **Unestablished:**
such an allocated positive scientific owner, current source adequacy, and a fresh
canonical production run. The fixed negative path is measured, not used to claim
that all possible evidence elsewhere is inadequate.

## `merged-lanes-need-a-reissue-path-neither-lane-declared`

**Measured:** the actual read-only promotion check exits **1 / failed** with
`promotion_comparison_admission_manifest_drift` (`promotion-reissue-check`). No writer
or sync is invoked. AST enumeration reads all **four authorized transition predicates**
in `check_layer3_gy_promotion_contract.py`: CORR input epoch, credal input epoch,
v3-to-v6 comparison, and v6 source-scope epoch (`reissue-source`). Evidence:
`tools/quality/validation/check_layer3_gy_promotion_contract.py@fc823071a`.

**Narrower:** the gate refuses unauthorized reconciliation; this is not a silent
restamping defect. **Wider:** two predecessor authorizations need not authorize their
union, even from a common base; composability is a semantic predicate, not a shared
commit name. The instrument builds `GyComparisonProjectionPlan` from actual payload
and admitted receipts, then compares its manifest identities. A prose instruction in
an active plan is not an input to those transition predicates. **Reduction/class:**
not identical to C13 stale capture or DEF22 digest mismatch: each has different
owner inputs, authorization and discharge. They share freshness pressure, not one
repair. Supported merged-transition authority could unblock reconciliation; exact
reissue/readback and preserved predecessor obligations would discharge it.
**Unestablished:** admissibility of any fifth transition, proof that any particular
pair composes, and full P41 introducing-lane attribution. No transition is decided.

## `education-importer-provenance-neither-inherited-nor-excluded`

**Measured, narrower:** the exact two historical test selectors both fail now
(**2 failed / 2 selected items, exit 1**, `education-tests`) at
`cycle_substrate_registry_owner_rederive_mismatch` before their intended lever/fallback
assertions. The failing reader is
`tools/quality/validation/check_layer3_gy_second_domain_pack.py@fc823071a`,
`_project_second_domain_cycle_substrate_context`; the tests are in
`tests/unit/runtime/quality/test_intervention_substrate.py@fc823071a`.

**Wider:** this is provenance of a failed current-owner rederivation, not evidence
that the education semantic assertions themselves fail. The input closure includes
current registry/data identities as well as the test/source path, so merely showing
an unchanged test cannot establish disjointness. **Reduction/class:** the two nodes
share this initialization blocker and reader; they still owe distinct semantic
assertions after it is removed. No reduction to legal correspondence or Lex SQL
schema compatibility follows from both touching the substrate. Correct current owner
binding could unblock execution; a complete exact-slice-base replay and complete
input-intersection proof would discharge the provenance question. **Unestablished:**
that historical full input set, exact fresh replay at `3d572c146`, and whether its
external data match those now mounted. Therefore no inherited attribution or test
exclusion is made. The explicit unknown is retained instead of manufactured as zero.

## `transitive-runner-closure-unbound`

**Measured, narrower:** the delivered observation explicitly attests intake closure
and explicitly excludes unmodified runner code. `runner-boundary` reconciles two
TypeScript AST node traversals over the complete C10 reconciliation owner and reads
all runner-identity objects. The Vite and Vitest witnesses bind entry path, that
entry's SHA-256 and package version. Python persistence recomputes those same local
coordinates. Evidence:
`apps/runtime-dashboard/src/test/evidence/atlasSurfaceReadinessReconciliation.ts@fc823071a`
and `apps/runtime-dashboard/scripts/persist_atlas_evidence.py@fc823071a`.

**Wider:** local entry identity does not bind the transitive executable closure or
an independent build/runner authority. A changed imported chunk with the same entry
bytes is outside that predicate. This is an inference from the exact reader's
inputs; the historical executable-chunk mutation was not replayed in this survey.
**Reduction/class:** the honest intake scope is not a missing producer or false
authority assertion. No identity with Python invocation reachability is established:
one asks who vouches for executing bytes, the other models possible calls.
Independent runner identity could unblock the stronger claim; transitive closure
verification under actual changed dependencies would discharge it.
**Unestablished:** repository-wide absence of every possible out-of-band attestation,
current full runner closure and an executed mutation witness. No stale whole-tree
file total is carried as proof. This bounded source account does not close the row.

## Exact command and receipt index

Each row uses the receipt labels below as claim-level replay keys. These are commands,
not inferred test outcomes. Run from `policy-engine/`; complete outputs are retained
at the indexed path, with the SHA-256 below. Older source-only AST receipts labelled the
full Python path digest as `path_sha256`; the instrument now labels the selected and full
sets separately. The enumerated identities and findings are unchanged. `demand-independent`
replays the complete document denominator using an independent filesystem walk.

### Receipt `denominator.json`

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/inspect_tree.py denominator
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/denominator.json`; SHA-256 `e7820b8e9b1865fc98a17549ed908f35a1b05942e3eba6cc61e2741617f584af`.

### Receipt `pyproject-gate.json`

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m tools.cli validation repository-structure-phase0 gate --gate pyproject_size --json
```

Exit **1**; complete output `docs/superpowers/journals/debt-survey/open/raw/pyproject-gate.json`; SHA-256 `4c5335490477b4cd67930c39560dd84932131d79575e3e2228abd26b7cde82fa`.

### Receipt `requirements-ast.json`

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/inspect_tree.py ast '(^|\.)(select_method_candidates_for_requirements|_method_candidates_from_capabilities|_manifest_rows)$' --source-only
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/requirements-ast.json`; SHA-256 `74a86eebb29aa06f2d31beab18d11a1346402269b8780c50a0d596673e1284c2`.

### Receipt `requirements-callers-ast.json`

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/inspect_tree.py ast '(^|\.)(_foundry_requirement_report|build_g2_method_requirement_bindings|build_foundry_method_report)$' --source-only
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/requirements-callers-ast.json`; SHA-256 `96e23ae0f24b6947aa320805c4404aede04a2bb6d33a53ab39b0262a49bf067c`.

### Receipt `requirements-tests.txt`

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/foundry/methods/selection/test_method_requirements.py -q
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/requirements-tests.txt`; SHA-256 `c4b808d34f4db00b333696dec1f3a43a2887d8bfe0cb7af07a3cb98ff43a7830`.

### Receipt `requirements.json`

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/probes.py requirements
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/requirements.json`; SHA-256 `710e8b11ef62c0709ebf9e2a9c3f7498937102835857191148659563b3de5177`.

### Receipt `calibration.json`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/probes.py calibration
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/calibration.json`; SHA-256 `7864dff1b6cd3ff3284fb6078e661642ca9e88dc2d920c42fc9dc3feaeac6af3`.

### Receipt `worktrees.json`

```sh
python3 docs/superpowers/journals/debt-survey/open/probes.py worktrees
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/worktrees.json`; SHA-256 `35ba83dc952dddafe5cd19ac5a52a63cbdc491a1c3a2f6bd9aa357fd473a2e53`.

### Receipt `udf.json`

```sh
python3 docs/superpowers/journals/debt-survey/open/probes.py udf
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/udf.json`; SHA-256 `0c517ff3c2fea9a7c280e9812b83497c0fcd168e4ac2c24f63a3c4afc3235779`.

### Receipt `json-readability-reconciled.json`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/probes.py json-readability
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/json-readability-reconciled.json`; SHA-256 `79e3d9b3ebb2e7392cf54c67c9f8c0237a667b5c5788fff494baee267b5a01cf`.

### Receipt `environment-sync.txt`

```sh
uv sync --frozen --offline --extra lint --extra test --extra runtime
```

Exit **1**; complete output `docs/superpowers/journals/debt-survey/open/raw/environment-sync.txt`; SHA-256 `1a8d8ac37e7d78a1f4ce2890ada52e0381641c548c01153a7d245857878b6db8`.

### Receipt `calibration-import-unrun.txt`

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/probes.py calibration
```

Exit **1**; complete output `docs/superpowers/journals/debt-survey/open/raw/calibration-import-unrun.txt`; SHA-256 `0f108d2fe858931735ffe79f9d959ee6d55d633bf6e1adc38fde9ffdcf99daab`.

### Receipt `scope-candidate-tests`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/core/contracts/test_scope_adjudication.py -o addopts= -q --basetemp=docs/superpowers/journals/debt-survey/open/raw/pytest-scope
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/scope-candidate-tests.txt`; SHA-256 `54d62a0149f447ee2867b9e102287fade45e0a057ff3b969489678c98884e9ae`.

### Receipt `epoch-custody-tests`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/runtime/quality/test_epoch_custody_audit.py -o addopts= -q --basetemp=docs/superpowers/journals/debt-survey/open/raw/pytest-epoch-custody
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/epoch-custody-tests.txt`; SHA-256 `46d58596b23aa8868712898d9259262aaad981fe98f5dc81e0de666e1f7c0fc5`.

### Receipt `semantic-admission-tests`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/runtime/quality/test_acquisition_epoch_admission.py -o addopts= -q --basetemp=docs/superpowers/journals/debt-survey/open/raw/pytest-semantic-admission
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/semantic-admission-tests.txt`; SHA-256 `c1dd1ccfbd6f0c344c359a2d08811e6a88e048203165690259696205e5f152a9`.

### Receipt `scope-source`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py ast 'ScopeAdjudication|scope_adjudication|scope_predicate_resolver_unappointed|PublicSignaturePopulation|public_signature_population' --source-only
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/scope-source.txt`; SHA-256 `4cb183b68c881a4c218692099faddd78efd48581b030b2ce3214d1d8fd3f1fa6`.

### Receipt `epoch-source`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py ast 'build_production_epoch_anchor_custody_provider|NoEpochAnchorAppointmentResolver|audit_epoch_custody|admit_acquisition_with_production_semantic_epoch|from_unallocated_policy_authority|NoEpochTransitionSigningAuthority|EpochTransitionSigningNonReceipt|ArtifactEpochValidityAuthorityGate|run_admission' --source-only
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/epoch-source.txt`; SHA-256 `0c019b34b2756187900fd28d4dd977280b844ecaf02111a82339d5a7f21d8584`.

### Receipt `epoch-factory-body`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py body '^(NoEpochAnchorAppointmentResolver|build_production_epoch_anchor_custody_provider)$' --path src/polisyos/runtime/quality/chronology_custody.py
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/epoch-factory-body.txt`; SHA-256 `6854ff8deae4a56714402ef339826e39320974b30ea816ce8d9b03d089423175`.

### Receipt `signer-body`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py body '^(NoEpochTransitionSigningAuthority|ArtifactEpochValidityAuthorityGate|EpochTransitionSigningNonReceipt)$' --path src/polisyos/runtime/quality/epoch_validity_cascade.py
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/signer-body.txt`; SHA-256 `80b20e8143ce50b8a2c4fb92f2d0601d1045723922edb576575128be44664c24`.

### Receipt `semantic-production-body`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py body '^admit_acquisition_with_production_semantic_epoch$' --path src/polisyos/runtime/quality/acquisition_executor.py
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/semantic-production-body.txt`; SHA-256 `984e55f5b9cbaa5e863d6dc9a86c490450eee303aab3a6f1cc2d9e8ee69d36cb`.

### Receipt `scope-body`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py body '^ScopeAdjudicationCandidate$' --path src/polisyos/core/contracts/scope_adjudication.py
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/scope-body.txt`; SHA-256 `1129090533d15f7897a003b9339261e40042b80b874e7dd8d774bc81abea909d`.

### Receipt `population-tests`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/scientist/governance/continuous/test_published_signature_custody.py::test_real_empty_issuance_slot_does_not_become_watched_empty tests/unit/scientist/governance/continuous/test_published_signature_custody.py::test_real_signed_report_inventory_is_inspected_but_not_a_governed_population tests/unit/scientist/governance/continuous/test_published_signature_custody.py::test_corrupt_actual_report_changes_population_nonreceipt_not_its_markers -o addopts= -q --basetemp=docs/superpowers/journals/debt-survey/open/raw/pytest-population
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/population-tests.txt`; SHA-256 `4a6e9c36d8f59b5f37fea72c93e4df9fc194a7d55658ccade2f5975a987ec522`.

### Receipt `ukraine-tests`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/foundry/data_plane/test_bindings_multiscale.py::test_load_ukraine_foundry_intake_content_binds_and_validates_all_method_contracts tests/unit/foundry/data_plane/test_bindings_multiscale.py::test_load_ukraine_foundry_intake_fails_closed_on_one_corrupted_method_artifact tests/unit/foundry/data_plane/test_method_contract_materialization.py::test_materialize_method_contract_rejects_mismatched_fqn tests/unit/foundry/data_plane/test_method_contract_materialization.py::test_materialize_method_contract_round_trips_deterministically -o addopts= -q --basetemp=docs/superpowers/journals/debt-survey/open/raw/pytest-ukraine
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/ukraine-tests.txt`; SHA-256 `72f248acfda3d4a6b8e99f7a9defa50b3d780222b4aa867a2b9e926c7b578efa`.

### Receipt `ukraine-source`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py ast 'load_ukraine_foundry_intake|BindFoundryInputsNode|materialize_method_contract|RunCausalEvaluationNode|_load_ukraine_intake|ukraine_foundry_method_selection' --source-only
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/ukraine-source.txt`; SHA-256 `9172adb0674c20520e114dbaedc3ed038df73c0278f5993884828872ff55c8c5`.

### Receipt `population-body`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py body '^PublicVerificationRecordPopulationProvider$' --path src/polisyos/scientist/governance/continuous/published_signature_custody.py
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/population-body.txt`; SHA-256 `04bb87bf0bfcc1c4c522a67cedc985ad5a2e6f8609f696b133dc1d3ad467a4bc`.

### Receipt `ds15-authority-source`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py ast 'AcquisitionAuthorityGateway|_require_authority_provider|AgentActionAuthorityGateway|CurrentMandateOwnerEvidence|SignedDelegation|WorldBankWDIAcquisitionExecutionPort|build_production_acquisition|AcquisitionActionService' --source-only
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/ds15-authority-source.txt`; SHA-256 `951eca3562f050c870a13d8bc8d777ca73e2a8bade15dded6ad71bfd18819898`.

### Receipt `def22-source`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py ast 'build_dependency_discriminant_companion|write_dependency_discriminant_companion|read_foundry_dependency_discriminant|resolve_dependency_discriminant|diagnose_dependency_environment|_validate_foundry_dependency_discriminant|_run_dependency_discriminant_consumers'
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/def22-source.txt`; SHA-256 `8e59b72bd23cf3d6a7a9d56a0a26b15c26760fef814ca4dc2bfd0e75a79c88ef`.

### Receipt `def22-tests`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py::test_cb_i01_n8_n10a_and_chronology_share_one_foundry_discriminant tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02_research_profile_names_torch_as_first_generic_case tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02a_label_and_shape_cannot_mask_two_data_generated_incompatibilities tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03_outside_closure_difference_is_diagnostic_irrelevant tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03a_novel_admitted_profile_verifies_from_owner_data -o addopts= -q --basetemp=docs/superpowers/journals/debt-survey/open/raw/pytest-def22
```

Exit **1**; complete output `docs/superpowers/journals/debt-survey/open/raw/def22-tests.txt`; SHA-256 `72fa63a294e0a168ab033dc7c8eaa511fcb5d1979ab82ef6a8fcd6e32b0be509`.

### Receipt `ukraine-key-reconciliation`

```sh
python3 docs/superpowers/journals/debt-survey/open/survey_queries.py ukraine
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/ukraine-key-reconciliation.txt`; SHA-256 `7c889d7dd630673722252b3c4404b155286b55fb50027fefad4560dd71e9fa9d`.

### Receipt `identity-authority-boundary`

```sh
python3 docs/superpowers/journals/debt-survey/open/survey_queries.py authority
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/identity-authority-boundary.txt`; SHA-256 `44c6531c2cea043fa41ebaa7872b1718d98a4cfce65f2e84439f6c1f59b8cea5`.

### Receipt `ceiling-demand`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py docs 'assurance.level|estimand.binding.strength|CORR-B1|CORR-B2|W5-K07|normative.*ceiling'
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/ceiling-demand.txt`; SHA-256 `11522b84fc10ac4f301723130e57db19a36532535140c200325fb0571ac7c2b4`.

### Receipt `correspondence-source`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py ast 'recognize_legal_correspondence|resolve_law_bound_lever|declare_calibration_frame|declare_refusal_suite|run_refusal_suite|ProductionCG2CalibrationSource|_compose_production_case_admission|compose_graded_outcome|_classify_production_observation|build_accounted_graded_report|build_authorized_value_schedule'
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/correspondence-source.txt`; SHA-256 `72cbbe4997126a67a238e0f6c0a78d2f323766892dd7b402f52272d461c08bce`.

### Receipt `vocabulary-distribution`

```sh
python3 docs/superpowers/journals/debt-survey/open/survey_queries.py vocabularies
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/vocabulary-distribution.txt`; SHA-256 `90139d07394d4c98e39cd316fda6dfeb4496b76cb370408d33b7da503ed11850`.

### Receipt `education-tests`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/runtime/quality/test_intervention_substrate.py::test_pack_lever_resolution_returns_typed_candidate_unbound tests/unit/runtime/quality/test_intervention_substrate.py::test_pack_context_fences_first_vertical_knob_fallback -o addopts= -q --basetemp=docs/superpowers/journals/debt-survey/open/raw/pytest-education
```

Exit **1**; complete output `docs/superpowers/journals/debt-survey/open/raw/education-tests.txt`; SHA-256 `caecd7f1347ace467710dee8826cdfeda41e55f9082bd242b22101830c1086f6`.

### Receipt `correspondence-tests`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/foundry/validation/test_legal_correspondence.py tests/unit/runtime/quality/test_intervention_substrate.py::test_phase5_real_unrelated_law_target_cannot_authorize_a_knob -o addopts= -q --basetemp=docs/superpowers/journals/debt-survey/open/raw/pytest-correspondence
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/correspondence-tests.txt`; SHA-256 `39d43afd2a59151be79b59b8beb00be3fae5857158cf4a273b3ea4e68b061354`.

### Receipt `promotion-reissue-check`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m tools.cli validation check-layer3-gy-promotion-contract --check --output-format json
```

Exit **1**; complete output `docs/superpowers/journals/debt-survey/open/raw/promotion-reissue-check.txt`; SHA-256 `066b72dfaec304952003e6a6f8340f5f0fd38921b44e52c7a67531acdbad26e5`.

### Receipt `lex-schema`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python docs/superpowers/journals/debt-survey/open/survey_queries.py lex-schema
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/lex-schema.txt`; SHA-256 `dca0f68f8a989f8dbd2ac882705c061eea7e98f3013a94b340f30c34f3644254`.

### Receipt `production-invocation`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m tools.cli validation check-production-invocation --base fc823071a --receipt docs/superpowers/journals/debt-survey/open/raw/invocation-full.json
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/production-invocation.txt`; SHA-256 `c71d77e96412c8e57cb0103ab656f937ebda1859981be7106e0ef569e68bbe86`.

### Receipt `vocabulary-semantic-source`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py ast 'NormativeModelCompleteness|NormativeAuditStatus|run_normative_arbitration|normative_arbitration_pass|compile_estimand|strength_order|stage_order' --source-only
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/vocabulary-semantic-source.txt`; SHA-256 `12519324e2e14d2bf660c792147a5a6090f828fbaed5528ed8f3f293f8d41914`.

### Receipt `n13-binding-tests`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/integration/core_runtime/test_acquisition_route_execution_binding.py -o addopts= -q --basetemp=docs/superpowers/journals/debt-survey/open/raw/pytest-n13-binding
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/n13-binding-tests.txt`; SHA-256 `4b9ce0950a032efccdb25d5f6923e6468e5324adde9f32338a6c830ad73d188d`.

### Receipt `gyj-report`

```sh
python3 docs/superpowers/journals/debt-survey/open/survey_queries.py gyj-report
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/gyj-report.txt`; SHA-256 `8bf7f13c7bcee54b98e6099ccc00881a8546e5a5bc42a26507c8895dafc487e6`.

### Receipt `runner-boundary`

```sh
node docs/superpowers/journals/debt-survey/open/runner_boundary.mjs
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/runner-boundary.txt`; SHA-256 `87be82ff1cc33eeaa9fa6b390eef0c6ea55b85aa7422b002aed534236ccdb523`.

### Receipt `invocation-selection`

```sh
python3 docs/superpowers/journals/debt-survey/open/survey_queries.py invocation
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/invocation-selection.txt`; SHA-256 `101dcf593aaa3bffb8a6a42e7f608ed5983a2c14f915f0b2d1f4058b5a233e87`.

### Receipt `builder-demand`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py docs 'GY-CB2|GY-ML2|DS15-MANDATE-INTAKE|operator.comprehension|multilingual.assurance'
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/builder-demand.txt`; SHA-256 `a5fd16062b10ec10775c698f236da5d46326ff2e5c91cdb4ef3f6c565e0c147d`.

### Receipt `reissue-source`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py body '^(_reconcile_frozen_contract|_is_authorized_.*reissue)$' --path tools/quality/validation/check_layer3_gy_promotion_contract.py
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/reissue-source.txt`; SHA-256 `f81a1bbe4eada39ddd7e5b52e2c28ecc6abe2d557e6ae3058d678e86f91e88e0`.

### Receipt `cg2-source-body`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py body '^(RelationAcceptanceSlot|ProductionGroundingSourceResolution|ProductionCG2CalibrationSource)$' --path src/polisyos/runtime/quality/production_grounding_calibration.py
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/cg2-source-body.txt`; SHA-256 `63cec327d5b49d0ec42ccfdaed01c030876d3587157e0bc2d1f51b1ae7d55a8f`.

### Receipt `gyj-source-body`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py body '^_compose_production_case_admission$' --path src/polisyos/runtime/quality/workspace/loop.py
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/gyj-source-body.txt`; SHA-256 `bb26fb6673fd14e594efcc022da2882b4b9e32ec8db09f7653c663f42d70901f`.

### Receipt `cg2-refusal-tests`

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/runtime/quality/test_production_grounding_calibration.py tests/unit/runtime/quality/test_grounding_calibration.py -o addopts= -q --basetemp=docs/superpowers/journals/debt-survey/open/raw/pytest-cg2
```

Exit **1**; complete output `docs/superpowers/journals/debt-survey/open/raw/cg2-refusal-tests.txt`; SHA-256 `a7ea7ab0dc53a852cd05ec373de78bc51a6270b75388a4ec4fdd5130e58fc7fd`.

### Receipt `demand-independent`

```sh
python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py docs 'assurance.level|estimand.binding.strength|CORR-B1|CORR-B2|W5-K07|normative.*ceiling|GY-CB2|GY-ML2|DS15-MANDATE-INTAKE|operator.comprehension|multilingual.assurance'
```

Exit **0**; complete output `docs/superpowers/journals/debt-survey/open/raw/demand-independent.txt`; SHA-256 `722b02bc5619deeef1f9dcebeb9b1e32661888f49bba357daab5991287c83be2`.

