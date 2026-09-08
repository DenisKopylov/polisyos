# S3 credal law-status consumer audit — 2026-09-08

**Decision: this is a load-bearing sibling-consumer escape, not documentary evidence.**
The S3 law owner refuses the real law/knob correspondence, but the current L6-to-credal
projection unconditionally labels it `confirmed`. The actual CG0 atom consumer then emits
`admissibility=passed`. This belongs to S3's changed law-resolution handoff. Repair only that
projection and its deciding proof; do not reopen general S2/CG1 algorithms or weaken their
existing reference-status predicates.

## Property, implementation, divergent case

`credal_reference.py`'s modality definition explicitly names
`L6_LEX_INTERVENTION_MAP` as **“JTCG law-to-knob admissibility.”**
`CredalReference.all_essential_confirmed` calls itself the CGF bind predicate.
`_iter_l6_edges` calls the real `resolve_law_bound_lever`, but tests only whether it throws.
A successfully constructed typed `blocked` resolution proceeds into `_confirmed_edge`, whose
single fixed completion is labelled `owner_signal_confirmed`.

This is authority promotion by exception absence. The decisive predicate is whether the
mapping is established; the implementation measures whether a resolver returned an object.
The divergent case is already the complete real source vocabulary: the three owner outputs
are `blocked`, `mapping_predicate_provenance=consumer_asserted`, and
`mapping_reason_code=law_mapping_correspondence_not_established`; every corresponding credal
edge is `confirmed`.

The consumer chain is exact:

1. `_reference_atoms_from_cg0` in `grounding_relation.py` groups law edges by
   `completion.value.knob_id`, places them in each matching atom's `edge_scope`, lifts the
   complete scope, and sets `admissibility="passed"` iff all scoped statuses are confirmed.
2. `GroundingBindGate._safe_set` re-resolves that exact scope and requires every support status
   to be confirmed. Its `support_confirmed` check is an actual bind predicate.
3. The law-token parser can also use the declared association for candidate interpretation.
   That candidate use is compatible with an uncertain edge; it does not require classifying
   an unresolved mapping as confirmed authority.

The isolated execution below proves the edge and atom handoff. It does not mint a CG2
certificate or a promotion receipt, and does not assert that any complete production
promotion currently succeeds through this escape. Full K_ref generation remains subject to
the separately measured academic confidence-forwarding restriction.

## Read-only execution and complete denominator

S3 supplied an already emitted real WMR CAS blob for direct reading:

`policy-engine/.tmp/gy-s-composed-wmr-cas/artifacts/sha256/8b/96/8b96b3761b471ab0d05fb6f7ecd17ebeba9812abcc703b353bdbb70563f494b4.blob`

Its bytes SHA-256 agrees with the CAS identity; its decoded `WorldModelRecord.content_hash`
is `sha256:61fb1eeb738aac25a6dd71e307cfc6719046bdcd0bc09ddb44ce9b5e9b1d92e6`.
The probe calls no composed-world builder and writes no shared scratch or production data.
It loads the real L6 bundle and legal owner, resolves every law map, extracts actual L6 and
WMR edges, and runs the actual CG0 atom consumer over that explicitly scoped view.

The complete real law identity set, independently obtained from the typed owner and the raw
`lex_intervention_map.json`, is:

| Law identity | Declared knob association | Owner result | Current credal result |
| --- | --- | --- | --- |
| `budget_law` | `budget_allocation_multiplier` | `blocked` / `consumer_asserted` | `confirmed` |
| `procurement_decree` | `procurement_shock_intensity` | `blocked` / `consumer_asserted` | `confirmed` |
| `tax_relief_statute` | `tax_relief_rate` | `blocked` / `consumer_asserted` | `confirmed` |

Every constructed atom's semantic identity is retained in the outputs. The completed probe
also independently enumerates the full raw knob-owner × real WMR-slot relation through the
existing compatibility owner, and compares the full `(operator, target tuple)` identity sets.
It does not compare content-dependent atom hashes as if a status change should preserve
those hashes.

| Complete semantic atom identity | Current | Naive status-only change | Incomplete, association retained |
| --- | --- | --- | --- |
| `budget_allocation_multiplier → agents.income` | `passed` | `passed`, law edge lost | `reference_contested`, law edge retained |
| `budget_allocation_multiplier → agents.reported_income` | `passed` | `passed`, law edge lost | `reference_contested`, law edge retained |
| `budget_allocation_multiplier → government.balance` | `passed` | `passed`, law edge lost | `reference_contested`, law edge retained |
| `procurement_shock_intensity → cells.distress_score` | `passed` | `passed`, law edge lost | `reference_contested`, law edge retained |
| `procurement_shock_intensity → cells.output` | `passed` | `passed`, law edge lost | `reference_contested`, law edge retained |
| `tax_relief_rate → global.tax_rate` | `passed` | `passed`, law edge lost | `reference_contested`, law edge retained |

Both counterfactuals exist only in research memory. The naive variant substitutes the existing
generic `_incomplete_completions`, whose values are empty. That makes the isolated law scope
unconfirmed but removes `knob_id`, so CG0 drops the law edge from the atom's scope and its
admissibility still passes. The second variant preserves the declared mapping in an uncertain
`may_exist` completion, pairs it with `may_not_exist`, and marks the edge incomplete. The
candidate denominator remains intact and the real existing consumer refuses confirmation.

## Classification and smallest correct move

**S3-CC01 — same P37/P38 class one level deeper.** The owner now distinguishes numeric
threshold evaluation from legal correspondence, but a sibling projection launders its
refusal back into authority. The status-only/empty-completion escape is another worked
example of the same class: the implementation has to preserve the dependency being refused.
Do not ladder-patch each atom or weaken a bind check (P31/P40).

Extend the existing L6 map projection in `credal_reference.py::_iter_l6_edges` to preserve
the actual declared law/knob association while carrying the real resolver disposition and
mapping-predicate provenance. An unresolved mapping must become an uncertain/nonconfirmed
edge that remains in the atom dependency scope. The exact current source requires no
modification of `grounding_relation.py` or `grounding_bind.py`: their current scope-status
consumers distinguish the proposed projection correctly in execution.

The choosing property is independently established correspondence, not merely a token such
as `status="admissible"`; P37 classification must remain visible. Current mappings have no
authority-grade positive source, so a fabricated positive mapping is not a completion
witness. An actual independently verified future mapping can use the existing confirmed
branch under its governed source epoch. Keep historical reference/receipt bytes under their
own epochs; record this handoff correction as part of S3's governed semantic change before
editing production code.

The decisive red-first test should consume **actual resolver output through actual credal
extraction and CG0 atom scope construction**, require the full real map denominator to remain
represented, and require each affected atom to retain its map edge and refuse confirmed
admissibility. Its removal probe restores unconditional confirmation while keeping provenance
fields and markers: the gate must go red. A second removal probe keeps `incomplete` but drops
the declared association: it must also go red. Unaffected knob/world/observation-route
behavior remains its own valid baseline; do not require an invented law-authority positive
to compensate for a missing scientific/legal predicate.

## Exact commands and complete records

All run from the lane's `policy-engine` root, with lane `.venv/bin` first in child PATH and
`PYTHONPATH=src`. The child is the only gate invocation; actual subprocess statuses are
retained without an echo wrapper.

Child command:

`.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.s3.credal_consumer_audit`

The outer recorder was:

`python3 docs/superpowers/journals/gy-phase5-evidence/pr1/run_measurement.py ../s3/<record-name> <child command>`

- [credal-consumer-audit.json](credal-consumer-audit.json): RC 1, 23.075 s. Harness nonreceipt:
  raw CAS uses canonical float wrappers, so direct Pydantic JSON loading failed. No semantic
  conclusion is credited from this run.
- [credal-consumer-audit-ready.json](credal-consumer-audit-ready.json): RC 0, 29.244 s. Existing
  `from_canonical_bytes` decodes the exact source first; actual owner, current consumer and
  both counterfactual projections execute successfully.
- [credal-consumer-audit-complete.json](credal-consumer-audit-complete.json): same command,
  adds the independent raw-knob × WMR identity reconciliation. Exact RC/time and complete
  output are in the record.

No executed task is reclassified as repaired by this audit. The finding's home is **GY-S3
law-resolution dependent propagation / P27/P31/P37/P38/P40**, and its residual remains the
original unestablished authority-grade law correspondence. Introducing-history attribution
is `not_established`; no slice-base P41 replay was attempted during S3's exclusive scratch
window.
