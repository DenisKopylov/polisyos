# BERL automatic ScalarModel resolution — DEC0 for G

**Status:** G decision packet; no source or semantic change is proposed as already authorized. The current BERL producer is usable when its caller supplies an in-memory callable. Automatic resolution from persisted model/data refs remains `implemented_but_not_orchestrated`: the source census below finds no matching direct/import-alias producer call, and the inspected `ExecutionContext` declares no model-resolver port. This does not rule out dynamic or registry-mediated paths. Conditional feature-law support remains a separate `producer_missing` item and receives no positive here.

## Observed boundary

BERL’s existing callable is deliberately small: `ScalarModel.__call__(features) -> float` ([`protocol.py:16–19`](../../../../../../src/polisyos/berl/adapters/protocol.py)). `ExplanationOrchestrator.explain(model, request)` takes that callable as an argument ([`service.py:127–140`](../../../../../../src/polisyos/berl/service.py)). Its request carries an inline feature mapping, feature names, and background rows; `model_id`, `model_hash`, `feature_values_ref`, and `feature_schema_version` are strings, with defaults including `sha256:unknown`, `inline://features`, and `unknown` ([`service.py:80–116`](../../../../../../src/polisyos/berl/service.py)). The bundle’s `ModelContext` stores string identity/provenance fields and `FeatureContext` stores string refs/schema version; neither is an executable-model ref or a resolver result ([`explanation_bundle.py:19–27,41–48`](../../../../../../src/polisyos/berl/contracts/explanation_bundle.py)).

Persistence and readback exist. `persist_explanation_bundle` writes the fixed `scientist.explanation_bundle` / JSON / schema contract and returns an `ExplanationBundleRef`; its upstream `InputRef` list is optional ([`persistence.py:30–69`](../../../../../../src/polisyos/berl/persistence.py)). `load_explanation_bundle` resolves the selected ref and checks manifest kind, media type, schema name/version, and payload ([`persistence.py:72–129`](../../../../../../src/polisyos/berl/persistence.py)). Phase 5 invokes that loader for the persisted bundle ([`phase5_preflight.py:290–303,1063–1074`](../../../../../../src/polisyos/scientist/validation/phase5_preflight.py)); this is a real consumer, not a model producer.

The current Scientist runtime context exposes the artifact store and domain ports, but no model resolver ([`context.py:87–124`](../../../../../../src/polisyos/scientist/orchestration/engine/context.py)). A nearby execution mechanism is Foundry `JobSpec`: it carries a method FQN/version and typed `ArtifactRef` inputs ([`job_spec.py:15–36`](../../../../../../src/polisyos/scientist/compute/job_spec.py)). Its runner loads inputs, calls a method backend, and returns a `JobResult` with result/evidence refs; it does not return a `ScalarModel` callable ([`runner.py:728–816`](../../../../../../src/polisyos/scientist/compute/runner.py)). Likewise, the existing `load_model_artifact` helper decodes JSON into a caller-selected Pydantic model class, not an executable predictor ([`models.py:397–410`](../../../../../../src/polisyos/scientist/methods/autotune/models.py)).

An AST census of all **2,748 product `.py` files** under `src/polisyos` (parse errors: 0) found zero matching direct/import-alias producer calls, including constructor calls, for `ExplanationOrchestrator` and `persist_explanation_bundle`; it found one matching direct call to `load_explanation_bundle`, in Phase 5. The public imports in `berl/__init__.py` are exports, not call sites. This census does not build a whole-program call graph and does not rule out dynamic assignment, `getattr`, or registry-mediated paths. The inspected runtime port shape likewise does not establish a configured resolver. It is source evidence only, not a claim about external applications. The existing integration test supplies a local Python function, runs BERL, persists a bundle, and reads it through a fresh CAS store and Phase 5 ([`test_explanation_reliability_bridge.py:180–233,247–265`](../../../../../../tests/integration/scientist_berl/test_explanation_reliability_bridge.py)). It proves the explicit-callable physical path; it does not prove model-ref resolution or an automatic runtime workflow.

The census is reproducible from the product root with this alias-aware AST walk (it prints the Python-file denominator and every matching direct call):

```sh
python3 - <<'PY'
import ast
from pathlib import Path
files = sorted(Path("src/polisyos").rglob("*.py"))
targets = {"ExplanationOrchestrator", "persist_explanation_bundle", "load_explanation_bundle"}
imports, calls = [], []
for path in files:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for item in node.names:
                if item.name in targets:
                    local = item.asname or item.name
                    aliases[local] = item.name
                    imports.append((path, node.lineno, item.name, local))
        elif isinstance(node, ast.Import):
            for item in node.names:
                tail = item.name.rsplit(".", 1)[-1]
                if tail in targets:
                    local = item.asname or item.name.split(".")[0]
                    aliases[local] = tail
                    imports.append((path, node.lineno, tail, local))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            semantic = aliases.get(name, name)
            if semantic in targets:
                calls.append((path, node.lineno, semantic))
print(f"python_files={len(files)} parse_errors=0 imports={len(imports)} calls={len(calls)}")
for row in calls:
    print(*row, sep=":")
PY
```

Output on this source: `python_files=2748 parse_errors=0 imports=4 calls=1`; the one call is `src/polisyos/scientist/validation/phase5_preflight.py:1073:load_explanation_bundle`.

## G alternatives

| Path | Concrete reuse and boundary | Migration, authority, input and time impact |
|---|---|---|
| **Reuse current explicit API** | Keep `ExplanationOrchestrator.explain(ScalarModel, ExplanationRequest)`, the fixed BERL CAS writer, and the Phase 5 reader as-is. Callers that already own a callable may use them. | No schema or history migration. Does not add an automatic caller; status remains `implemented_but_not_orchestrated`. Never treat `model_id`, `model_hash`, a method name, or a profile string as permission or proof that a callable was loaded. |
| **Extend an existing runtime boundary** | If G wants configured execution, add a typed ref-to-predictor boundary to the existing Scientist/Foundry runtime rather than infer a callable inside BERL. Intake must preserve the full selected model `ArtifactRef` (including its manifest-profile selector) and the actual feature/data source ref; output must still satisfy the existing `ScalarModel` protocol or invoke an explicit explanation job. | This needs a G-selected executable artifact format/loader and verifier, output selection, feature schema/order and row/background binding. The current request and `ModelContext` have no model/data `ArtifactRef` or execution-time field. Choose fit/evaluation time and staleness behavior before enabling automatic runs; do not default to “latest.” Existing direct-call behavior remains compatible. |
| **Consolidate with Foundry method execution** | Use the existing method registry/dispatcher and `JobSpec` typed input refs as the one execution owner, if its extension can actually load a supported fitted model and provide repeated scalar predictions to BERL. Do not introduce a second BERL registry for the same executables. | Current `JobSpec` dispatch produces job-result artifacts, not a callable, so this is a candidate consolidation, not a capability already present. It still needs the same content-bound model/data, feature, output, and time contract; an FQN/version label alone cannot establish executable identity. |
| **Build a new model-serving subsystem** | Add a separate model loader/runtime only if the canonical runtime cannot support the G-selected execution contract. | Largest surface and new lifecycle/security/versioning obligations. Not justified by the current bounded BERL gap; defer unless the existing runtime is demonstrated unable to meet the selected contract. |

**Recommended narrow vote:** retain the explicit callable API and the existing typed bundle persistence/consumer. Do not authorize automatic lookup by the present string metadata. If G wants automatic resolution, first select a supported model artifact and verifier contract; then prefer extending the existing Foundry execution owner over creating a parallel BERL registry. This packet does not select a model format, trust policy, or conditional-law estimator.

For that future contract, use the repository’s existing selected-ref type as input rather than an artifact ID alone: model ref, data/snapshot ref, feature schema/order, requested output, and any background population must remain identifiable at the call boundary. Execution provenance must come from the registered loader/verifier and resolved content, not caller-supplied hashes or bundle annotations. Time must bind the actual model fit/source view and the prediction/evaluation context; the present BERL DTOs do not establish those times. Unknown or unsupported inputs should stay a typed limitation/refusal in the existing caller path, not be silently converted into an ordinary BERL result.

## Prototype, falsifier, and residuals

The integration test above is the available prototype for the explicit in-memory route. A future automatic-route acceptance test must start with a real configured full model ref and feature-data ref, resolve and invoke the actual registered predictor, persist the result with its selected input lineage, then consume it through a fresh CAS reader and the real Phase 5 path. Negative controls must show that changing only `model_id`/`model_hash` or a method label cannot select a different callable; wrong kind/schema/profile, corrupt selected content, mismatched feature schema/order, and stale/unavailable inputs must refuse before a normal result is emitted. A removal probe should delete the runtime resolve/content-bind check while keeping all DTO markers: the negative must then fail, or the test is checking labels rather than execution identity.

Keep conditional-law status separate: the persisted law decision refuses conditional attribution absent a verified observed-feature law and records that law producer as `producer_missing` ([`berl-persisted-law/decision.md`](../berl-persisted-law/decision.md)). A model resolver would not itself produce or verify that law.

Also keep CAS selection separate from model/data lineage. The current fixed-kind/schema loader proves that the selected bytes are an ExplanationBundle; it does not prove which model or feature population produced them. The writer permits `inputs=None`, and the explicit-callable prototype uses that path. The current Phase 5 default-view behavior treats a profileless ref as the immutable default selection (the focused profileless/default and wrong-profile cases are in [`test_explanation_reliability_bridge.py:342–376`](../../../../../../tests/integration/scientist_berl/test_explanation_reliability_bridge.py)); it does not prove that a previously non-default profile was retained or bind the bundle to its source inputs. Exact model/data lineage remains a distinct contract question; do not infer it from same-kind/schema identity or from profileless-default compatibility.

## Pattern pass

P01/P02: the typed writer and consumer exist, but the automatic producer-to-runtime bridge is missing. P05/P32/P15: string metadata and LLM/caller declarations do not prove executable identity or conditional-law authority. P10: a callable is not useful unless its inputs, output, and feature semantics are bound. P29/P35: the prototype is an actual component path; the census walks all 2,748 product Python files but measures only matching direct/import-alias calls, not indirect or registry-mediated edges. P37/P38: the meaningful predicate is whether the selected, verified model/data bytes resolve to the callable and inputs actually executed; the divergent case is a plausible `model_id`/`model_hash` pair with no corresponding executable model. P40: this is the same producer/bridge class one level deeper—the callable API exists, but the inspected port and direct-call census do not establish a configured ref-to-callable path—so any selected repair must cover that whole boundary, not add per-method aliases.
