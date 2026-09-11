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

## Remaining indexed rows

The remaining rows are still being measured; this checkpoint is incomplete.

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
