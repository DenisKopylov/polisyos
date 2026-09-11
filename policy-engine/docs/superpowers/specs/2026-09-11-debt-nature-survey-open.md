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
