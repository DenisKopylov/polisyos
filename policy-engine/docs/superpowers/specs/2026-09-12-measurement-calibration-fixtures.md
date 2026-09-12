---
title: Calibration fixture admission differs from generic artifact persistence
status: stage1-analysis-complete-owner-repair-decision-required
owner: team-foundry / team-runtime / team-scientist
authoritative_for:
  - bounded fixture-family and validation-path research
may_not_use_for:
  - choosing helper fixture or model repair
  - calibration validity or production capability closure
  - treating fixture authority declarations as verified evidence
  - permission to edit source or configuration
---

# Row 3 — calibration fixture decision input

**Owner decision remains open.** This is analysis only: it does not select a
helper change, a fixture change, or a model change. Root commits the Stage1
documents before any source work. Source coordinates below are relative to
`policy-engine/` at `42c09a7a46ac7ec42e39e4cc19a259a10b2c8811`.

## Findings

**MP3-01 — the generic helper adds three authority fields.**
`tests/_helpers/runtime_http.py:87–105` defines
`_with_runtime_fixture_authority` → `_put_json` → `_put_json_raw`.
For a Mapping without `authority_boundary`, it copies the mapping, uses
`setdefault` for `authority_result="authority"` and
`legacy_path_disposition="authority_path"`, then supplies `authority_boundary`
from `_runtime_fixture_authority_boundary:66`. A mapping already carrying that
boundary and every non-Mapping pass through unchanged. The added boundary's
declared authority purposes are fixture declarations, not producer verification.

At `:398–415`, `build_runtime_api_env` sends the literal
`foundry.calibration_report` mapping through this helper. That literal has
**12 keys**; the decorated mapping has **15 keys**, of which **3 are outside
the current model**. A count equal to the model's field count therefore proves
nothing about conformance. The missing optional model members are
`identifiability`, `uncertainty_envelopes`, `uncertainty_envelope_refs`.

**MP3-02 — current model, current schema, other schemas.** The relevant model is
`src/polisyos/foundry/calibration/report.py:72–106`, `CalibrationReport`, with
`extra="forbid"` and **15 fields**, enumerated from `model_fields` in the replay:
`schema_version`, `calibrated_params`, `total_loss`, `per_target_loss`,
`target_weights`, `loss_history`, `grad_norm_history`, `series_comparison`,
`fit_quality`, `uncertainties`, `identifiability`, `uncertainty_envelopes`,
`uncertainty_envelope_refs`, `diagnostics`, `execution_context`.
Its live `model_json_schema()` has the identical property set and
`additionalProperties=false`.

The full tracked **154 `*.schema.json` file** search under `policy-engine/`
finds no dedicated Foundry CalibrationReport schema snapshot. The similarly
named `src/polisyos/ddm/calibration/calibration_report.schema.json` describes
the distinct DDM detector report with 12 properties; it is not this model's
authority. `schemas/snapshots/ir/dynamic_microsim_validation_report.schema.json`
references another calibration type. This absence is bounded to that exact
schema-file denominator; the live Python-generated schema is present.

The literal fixture also triggers a separate `schema_version` pattern error:
the model at `report.py:77` uses the doubly escaped raw regex
`r"^\\d+\\.\\d+$"`, which rejects explicit `"1.0"`. The model's default is
`"1.0"` and is not default-validated. This source/schema divergence is recorded
for the owner; it is not resolved here and must not be hidden behind the three
extra-field errors. Omitting only that field in a scratch variant isolates
exactly three `extra_forbidden` failures.

**MP3-03 — strict rejection and generic persistence both replay.**
`tests/_helpers/artifacts.py:15–34`, `put_json_artifact`, builds `PutOptions`
and calls `FileSystemCAS.put_json`. At
`src/polisyos/core/artifacts/store.py:706–729`, that writer canonicalizes JSON
and calls `put_bytes`; it does not dispatch payload validation by kind or schema
name. `SchemaInfo` is a manifest identity, not a call to CalibrationReport.

The scratch replay extracts the actual fixture literal with AST, invokes the
actual decorator and writer, and reads back via `from_canonical_bytes` (plain
`json.loads` exposes canonical float wrappers). Strict validation rejects the
three extra fields plus the version pattern. The generic writer nevertheless
persists exactly that decorated payload, with manifest schema name
`foundry.calibration_report`; CAS integrity verification passes. The same bytes
then fail the real downstream loader
`src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py:215–217`
when invoked with `CalibrationReport`. The bypass demonstrated here is **payload
model validation at persistence**, not successful downstream calibration or
authority admission. No production optimizer run was attempted.

**MP3-04 — complete fixture-family denominator.** MP2-01's independently
reconciled 12,875-file tracked set is the shared source denominator. All 6,181
Python/pyi ASTs and 1,289 JS/TS ASTs were traversed; complete case-insensitive
source search and import/call review resolve the helper family. The private
decorator has one call in `_put_json:102`; the wrapper has **31 call sites,
all in `build_runtime_api_env`, covering 28 distinct kind strings**. The complete
family is below; numbers are source lines in `tests/_helpers/runtime_http.py`,
not runtime artifact counts (conditional execution still matters).

| Kind | All wrapper call sites |
| --- | --- |
| `test.child`, `test.root`, `security.secret_bundle`, `core.registry_bundle` | 312; 313; 338; 345 |
| `scientist.governance_report` | 346, 684 |
| `fabric.evidence_bundle`, `fabric.actuals_bundle`, `fabric.quality_report` | 357; 366; 374 |
| `lex.legal_report`, `foundry.calibration_report`, `lex.norm_pack` | 385; 398; 416, 446 |
| `scientist.execution_plan`, `scientist.preflight_report`, `scientist.evaluator_report` | 476; 505; 523 |
| `scientist.reproducibility_manifest`, `runtime.capability_manifest` | 541; 555 |
| `fabric.data_snapshot`, `foundry.input_bindings`, `fabric.retrieval_trace` | 569; 580; 610 |
| `scientist.decision_card`, `ir.normative_arbitration_result` | 664; 685 |
| `scientist.decision_packet` | 728, 835 |
| `scientist.reflexion_terminal`, `scientist.experiment_state` | 881; 900 |
| `scientist.workflow_report`, `scientist.workflow_spec` | 1055; 1090 |
| `foundry.equilibrium_multiplicity_report`, `test.run_paper_growth_output` | 1115; 1329 |

Of these calls, 27 pass AST literal dictionaries and four pass expressions:
`:610` producer call, `:684` `governance_json`, `:728/:835`
`_with_fixture_authority_surface_packet(...)`. This census does not claim all
31 gain three fields: the helper's existing-boundary branch is real. Negative
controls verify pre-existing boundaries, non-Mappings, pre-existing values of
the other two fields, and no mutation of the input mapping. No blanket repair
is justified by the calibration witness alone.

## Owners, callers and seams

Compose Foundry's report/optimizer owner, Runtime's test-fixture owner,
Scientist's typed-loading consumers, Core's generic CAS owner, and frontend's
fixture/display owner. The existing producer is
`src/polisyos/foundry/calibration/calibrator.py:1406`, `Calibrator.run`, which
constructs the typed report and may attach uncertainty envelopes at `:1430–1434`.
The typed writer `report.py:128`, `put_calibration_report`, is exported by
`calibration/__init__.py`; the complete Python AST census finds **zero direct
call expressions to that symbol**. Export availability is not a production
caller or persisted producer chain. Dynamic/external callers are unmeasured.

If an owner proposes changing the helper or fixture, its actual outer callers
are `runtime_api_env:1463–1467` and direct `build_runtime_api_env` users: the
complete Python AST census finds **50 calls across 19 files**, listed with
functions/lines in `target-ast.jsonl`. The non-`tests/` caller is the dashboard
fixture server `_build_dashboard_fixture_env` at
`apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py:174`, loading the
test module via `importlib` at `:33`. It is development/test infrastructure,
not production calibration. Runtime HTTP fixtures are re-exported by
`tests/unit/runtime/http/conftest.py:1`; changing the shared helper reaches
integration, HTTP, performance and dashboard-fixture users. No direct imports
of the private wrapper/decorator were found in the complete Python denominator;
reflective accesses are not thereby disproven.

If an owner proposes changing the model, actual production consumers include
Scientist feedback (`feedback/core.py:486`, loader `:841`), autotune
(`methods/autotune/calibration.py:321`), uncertainty propagation (`:263` in
`propagate_uncertainty.py`) and welfare propagation (`propagate_welfare.py:632`).
The runtime control contract names the kind at
`runtime/http/services/_control_contracts.py:95`; frontend simulation projection
reads `total_loss` in `apps/runtime-dashboard/src/shared/lib/domain/simulation.ts:340`.
Display or kind routing is not equivalent to strict model admission.

Untouchable without owner decision: the 15-field report and its strictness,
optimizer/UQ semantics, fixture helper and all sibling fixtures, CAS identity and
canonicalization, schema semantics, custody/authority meaning, package import
boundaries, runtime config and unrelated lanes. No selection among helper,
fixture, model or writer repairs has been made. A generic CAS writer is not
automatically defective merely because it accepts arbitrary JSON; the mismatch
is treating its success as evidence of model-valid calibration.

## Falsifier, shared effects and pattern pass

The deciding falsifier holds artifact kind and fixture authority declarations
constant, then sends the payload through the **real strict producer model** and
the **real generic writer/readback**. It must distinguish validation failure
from successful byte persistence; a marker or equal field count cannot pass.
The production consumer loader is the final negative control. Any future owner
repair must preserve those distinctions and assess the complete family above;
neither removing three keys from one sample nor relaxing all models is an
authorized conclusion of this document.

Shared-instrument effects: a helper change changes the inputs to tests and the
dashboard fixture server; a model change alters producer and consumer admission;
a CAS change affects generic artifact persistence well beyond calibration.
Root must freeze an owner-selected direction before repricing those checks.

Pattern pass: **P31** uses the complete family, not one fixture; **P32** refuses
to infer authority from fixture fields or CAS refs; **P35** fixes path/type and
call-site denominators; **P37** labels schema/field/rejection/persistence facts
`recomputed`, tracked membership `independently_reconciled`, fixture authority
`consumer_asserted`, production calibration validity `not_established`;
**P38** identifies the divergence between valid model payload and successful
generic storage (MP3-03). Model-validity evidence on this fixture route is
`verification_missing`; its candidate repair remains unselected. This is not a
claim that all calibration producers or all HTTP fixtures are broken.

## Replay receipts

Use the exact commands in the Row2 document's Replay receipts section. Complete
output is `docs/superpowers/journals/measurement-plane/rows23/raw/replay.out`,
with `MP3-REPLAY`, `MP3-CONSUMER` and `MP3-CONTROLS` records. Scripts, enumerated
`fixture-family.json`, `helper-references.json`, `private-helper-imports.json`,
`target-summary.json`, full source/AST outputs and `receipt-hashes.json` are in
that same gitignored directory. The initial scratch assertions were corrected
to use canonical decoding and the manifest's serialized schema field; both
earlier full outputs remain retained. No existing suite failure was excluded as
inherited, and no source/config/git mutation was made by this task.

Verified research replay: **4 passed in 27.81 s**, exit 0. One pytest warning
records `cache_dir` with the cache provider deliberately disabled for scratch;
it is not a product failure. The earlier retained failures were scratch harness
assertion/serialization mistakes, corrected without changing repository owners.

## Root sibling witness and routing

**MP3-05:** an additional real-helper replay extracts the complete constant
`test.child` and `test.root` payloads at runtime_http.py:312–318 using AST.
Both gain exactly `authority_boundary`, `authority_result` and
`legacy_path_disposition`. Thus the answer to “any other fixture?” is yes,
independently of the calibration sample. Denominator: those two complete payloads
within the enumerated 31-site family; this is not a family-wide model-validity
claim. Complete output: `docs/superpowers/journals/measurement-plane/rows23/raw/other-fixture-replay.json`.

The owner decision rests on intended artifact admission at each seam: should
these fixtures be model-valid calibration, generic persisted JSON for HTTP display,
or a different versioned report contract? Foundry and Runtime must decide that
before selecting helper, fixture or model repair. The explicit-version regex
rejection (MP3-02) is a separate Foundry model-admission finding, routed to MP-B4
in the completion journal; generic CAS acceptance alone is routed to explicit
nowhere as a storage defect because generic storage makes no model-validity claim.

## Stage 2 disposition

Research complete; owner decision remains deliberately open. No helper, fixture,
producer model, regex, or strict-admission repair is selected. The strict-model
rejection and actual generic CAS bypass were executed separately, with the
unblanketed control and other fixture replays preserved under `rows23/raw/`.
The exact source coordinates and 31-call / 28-kind family denominator above are
the decision basis. MP-B4 routes the explicit-version regex defect to the Foundry
calibration owner. The completion journal retains deciding command receipts.
