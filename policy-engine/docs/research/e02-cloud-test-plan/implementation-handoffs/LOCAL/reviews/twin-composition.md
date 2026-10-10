# Causal Twin runtime bridge review

## Review boundary and P40 classification

This is an independent implementation assessment of the Twin persistence bridge in the shared
worktree. The worktree was attached to `codex/e02-unified-local-20261009` at `00c200c2ec33786a80dd41209eca46a2539dac5c`
(tree `5ba74fcb78e28d61be21f3208ee7a4b42665b6fe`); the reviewed source paths were modified in the
worktree, so the hashes below, rather than the HEAD tree, identify the bytes I inspected. This is an
intermediate, mutable snapshot, not a global source freeze or a review of every peer change in these
large modules. In particular, `ir/analytics/README.md` also contains a posterior-summary entry, and
the causal-engine artifact module contains unrelated selected-reference edits.

**P40:** the runtime Twin artifact bridge is a **NEW** class relative to the static F821 inventory
check. It is the **SAME** original counterfactual-evidence producer class one layer deeper: the
question is whether a real counterfactual run persists evidence and lets a separate consumer reopen
it, rather than whether a static artifact marker exists. The current review finds no second-level
escape requiring another repair round. The `EvidenceBundle` CAS-version compatibility point below
is a separate NEW boundary question, not another runtime-producer escape. This review does not
adjudicate or close a G finding.

## Independent implementation assessment

The requested runtime chain is present for a counterfactual `CausalEngine.run()` with an artifact
store and a typed SCM:

1. `estimate()` recognizes the actual `twin_network_result` method output and carries the method
   state’s SCM into `report_dependencies`. The normal Twin executor preparation returns the typed
   SCM in that state, including when it creates the SCM for the query.
2. `audit()` persists that SCM, persisting an input edge to `SCMTrainingRows.source_ref` when the
   model has source-bound training rows. It persists the run’s `EstimandAST` with an SCM input,
   then persists the actual `TwinNetworkResult` with the available source, selected SCM, and query
   refs. The implementation computes and binds manifest-profile hashes for these views.
3. The typed result ref is returned on `EvidenceBundle` and embedded in the persisted proof trace.
   The trace manifest has a selected-profile input edge to the Twin result; the proof bundle links
   that trace.
4. The focused test enters through `CausalEngine.run()`, checks the result payload and all three
   selected lineage views, follows the proof-bundle/trace refs, then reopens the CAS in a separate
   Python process and loads the same result and ref. It does not call a test-only persister to
   simulate the bridge.

The positive fixture is honest about its scope: it creates persisted synthetic source rows and a
manual SCM (`fit_method="manual"`), then exercises the real Twin executor and persistence bridge.
It does not invent selected-worker provenance or claim that the manual SCM is admitted, valid,
calibrated, or authoritative. Source lineage is conditional on the SCM carrying a source ref; the
implementation and README state that limit.

The GCM rejection preserves the expected exception boundary. `_fit_gcm_specs()` rejects a graph
that is not a declared DAG, or whose observed columns do not cover its graph nodes, before importing
or invoking the worker. `_SelectedGCMGraphRefusal` subclasses `ValueError` and supplies the typed
`reason_code`; both the executor and `CausalEngine.run()` re-raise it instead of converting it to
best-effort missing/NaN output. The focused actual-run ADMG test observes that exception and reason.
The reason is also reused when a DAG has incomplete observed columns; the message describes the
full-observation requirement, but the reason code does not distinguish that case from an ADMG.
This does not make the ADMG refusal fail open, but callers should treat the code as a broad selected
GCM graph/input-profile refusal rather than a subtype-specific diagnostic.

`EvidenceBundle.twin_network_result_ref` is optional and defaults to `None`. The compatibility test
validates a historical-shaped payload without that field. `load_causal_evidence_bundle()` reads the
artifact and validates it through the same model, so that absent-field default applies on load; the
focused test does not separately construct an old CAS manifest/payload. This is a bounded test
coverage limit, not an observed loader failure.

There is a separate unresolved forward-reader compatibility question. The persister still defaults
to CAS schema `ir.causal_evidence_bundle` version `1.0` and calls `model_dump(mode="json")`; the new
optional field is therefore serialized on new bundles, including as `null`. `EvidenceBundle` uses
`extra="forbid"`, so a prior strict reader that lacks this field would reject a newly written payload
carrying it, even though the CAS manifest still says `1.0`. No prior-reader compatibility contract
or old-reader execution was provided here. Root should decide whether additive fields are permitted
under this schema version or whether the CAS schema/reader contract needs a versioned change. The
focused legacy test covers the opposite direction only: the current reader accepting an older
payload without the field.

The executable property check exercises the runtime and resulting CAS objects, not field-name
markers. For the tested run, the implementation and property agree. The authority predicates remain
limited: source profile selection is derived from the manifest when the source ref lacks a profile,
but source admission and SCM validity are **not established** by this persistence bridge. The new
link records lineage; it does not promote the result.

## Companion still pending

The current generated `docs/reference/ir/schema-catalog.md` entry for
`polisyos.ir.analytics.evidence_bundle.EvidenceBundle` does not yet list
`twin_network_result_ref` (entry begins at line 8893). The Twin delta does not include a regenerated
schema-catalog companion, and its release fragment sets `public_surface_inventory_reviewed = false`.
Root should reconcile the generated schema/docs companion and record the surface decision after the
source freeze. I did not run a generator or edit generated files under this review assignment.

## Verification and limits

The worktree-local interpreter was used, and its import origin was
`policy-engine/src/polisyos/__init__.py`.

Command (from `policy-engine/`):

```bash
.venv/bin/python -m pytest \
  tests/unit/foundry/methods/catalog/causal/test_id_star_algorithm.py::test_counterfactual_run_persists_and_reads_typed_twin_network_result \
  tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py::test_selected_gcm_refuses_admg_with_declared_dag_reason \
  tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py::test_causal_engine_run_surfaces_selected_gcm_admg_refusal \
  tests/unit/ir/analytics/test_evidence_bundle.py::TestEvidenceBundle::test_legacy_payload_defaults_twin_result_ref_to_none \
  -q
```

Result: exit 0; four selected cases completed (`.... [100%]`). The Twin case's fresh-reader child
uses the same worktree-local `sys.executable`. An initial attempt used the product-root-prefixed
`.venv` path while already inside `policy-engine/`; the shell returned 127 before pytest started.
The corrected command above is the only test result counted. No DoWhy fit, numerical fit, full-suite
run, generator, source/test/config edit, or Git mutation was performed. The result does not establish
selected-worker fitting behavior or final frozen-candidate closure.

## Reviewed worktree file fingerprints

These SHA-256 values identify the current whole-file bytes at review time, including any unrelated
peer hunks in those files. Only the Twin-specific behavior described above was assessed.

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/foundry/methods/catalog/causal/causal_engine/artifacts.py` | `5487727f8a77f7a27100142141698b93ef64fa0d5cd78e0e70c082c563f1012e` |
| `src/polisyos/foundry/methods/catalog/causal/causal_engine/estimation.py` | `cc0019fc4e84e2221ff0876e73f7a76fe67e9bb800d631a6c7634c00b455da81` |
| `src/polisyos/foundry/methods/catalog/causal/gcm_fit.py` | `287c2a8c1300b3c38d41ca32bcb6e264fe77c775ff819e69957318a3a33f4bd7` |
| `src/polisyos/ir/analytics/evidence_bundle.py` | `3e41d8577b5ed5498b5ef6271a251f2da21a3e80c2aff58730bee09008539e44` |
| `tests/unit/foundry/methods/catalog/causal/test_id_star_algorithm.py` | `ae27a017abe3f3f883bf4c3ed0ee761d7ded9a06dcee90e4b1e57657f2b378d7` |
| `tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py` | `716a15e0a93e0063a112effec1acb6f4578db2906da95f427011687bb170e761` |
| `tests/unit/ir/analytics/test_evidence_bundle.py` | `fdff8395b17ce913f4875702d9736836e98d4eaddc94793dd4583fe03c294091` |
| `src/polisyos/foundry/methods/catalog/causal/README.md` | `745127dbf7536419bb1397d1d7b1db915ce9dd4d9d9e3cec410eb6f81e1af845` |
| `src/polisyos/ir/analytics/README.md` | `de7ecfa1a633ef44b57395a5ce9fed7e635d992b56e1f17e41add1d14871cc12` |
| `release-fragments/unreleased/2026-10-09-causal-engine-twin-result-persistence.toml` | `5b505427a1c164b9f32c7a8eb17f5200f245bab3ef21233ded1feec13e3c8ad8` |

No formal closure, acceptance decision, or generated-doc update is recorded here.
