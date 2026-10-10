# Independent review: BERL CAS persistence slice

This is a read-only review of the bounded persistence slice, not G acceptance or full BERL capability adjudication. The candidate checkout remained attached to `codex/e02-unified-local-20261009` at HEAD `4c591813507531d1bfc8c45a832662c00d8c86cd`, tree `eec418d99c6fcc0948e2ddaeb9ce618fdc4a8f19`, parent `58ab0ac58c4c3901e518e344fcccef85d22639bb`. The persistence source is author WIP `src/polisyos/berl/persistence.py@87a7aad8e0a7af06686dc0f9f4439cd43a9ae5b34c56db6485da1bd8c33a48c9`.

Reviewed source/test fingerprints:

- `src/polisyos/berl/persistence.py@87a7aad8e0a7af06686dc0f9f4439cd43a9ae5b34c56db6485da1bd8c33a48c9`
- `src/polisyos/berl/__init__.py@5a11422a24c790eeba15bfd432435b360aa89e975fa3c0491e36c274c886c799`
- `src/polisyos/berl/README.md@bcdbce26f053931c34c4b02e2476fbdd4dacbf7a424bab06296830f88841a62b`
- `src/polisyos/berl/contracts/validation_rules.py@b3619593fb6b649b9617c830185ce3985ff33c5722470fc2fa45f764c954ea0d`
- `src/polisyos/scientist/validation/phase5_preflight.py@e4895a67db461df2df03df0addc7198601c0c8f8a54cb92f6344db8e6cbf03ea`
- `src/polisyos/runtime/quality/explanation_reliability.py@f78eada3fece916c383d747ae5c3cf3105c6804e72db366805435a74de271083`
- `tests/unit/berl/test_persistence.py@d7d0928df08b9e519fc384658b4d063ed9bfb304fb1a34e49f8eb2a000a2221a`
- `tests/integration/scientist_berl/test_explanation_reliability_bridge.py@618992e1ddf60fc46529dabfc5ab4ac319f47f6eac98523c967333407ed8baac`

## Behavior and deciding checks

The writer rejects an unsupported bundle schema version before writing, persists the current JSON representation through `ensure_ir_artifact_store` / `put_json_artifact`, and returns a typed `ExplanationBundleRef` including the selected manifest profile. The reader validates the typed ref, resolves that selected manifest, checks artifact id/kind/media/schema name/schema version, reads bytes using the same selected ref and its canonical profile, checks generated-schema-required wire fields, then validates the full Pydantic bundle. The facade exports both methods.

The unit cases exercise two manifests over the same content id (an old default schema view and the current selected schema view), exact selected-view loading through a newly opened CAS, a bad selected-profile digest, wrong kind/media/schema manifest views, a missing required `methods` wire field, payload/schema-version mismatch, and writer refusal before any object is stored. The generated schema provides the required-field set; Pydantic validation remains the full content check. The integration test uses the real `ExplanationOrchestrator` on a small deterministic model, persists the bundle, loads it through a fresh CAS, and sends the loaded bundle through Phase-5 and Runtime validation. Its marginal case preserves `requested_method_id=kernel_shap_marginal` and `effective_method_id=kernel_shap` while returning Phase-5 pass / no Runtime issues. Its conditional case keeps a self-attested artifact-ref string but produces diagnostic scope with no attributions, and both consumers refuse it with `conditional_feature_law_unverified`.

I also tried a profileless ref against the unit fixture's conflicting default/current views. Clearing the selected profile returned `ValueError:explanation_bundle_manifest_contract_mismatch`. This supports refusal when the default view is not the current contract; it does not establish a general profileless-history rollout rule. The ref model permits `manifest_profile_sha256=None`, which selects the CAS default view by contract.

From `policy-engine/`, I ran the source-bound focused tests:

```text
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/berl/test_persistence.py tests/integration/scientist_berl/test_explanation_reliability_bridge.py
```

Complete output:

```text
............                                                             [100%]
=============================== warnings summary ===============================
.venv/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: cache_dir
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[marginal_interventional-kernel_shap_marginal]
tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[marginal_interventional-kernel_shap_marginal]
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/lib/python3.14/site-packages/torch/jit/_script.py:1474: DeprecationWarning: `torch.jit.script` is not supported in Python 3.14+ and may break. Please switch to `torch.compile` or `torch.export`.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```

Scoped lint and formatting checks:

```text
$ env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check src/polisyos/berl/persistence.py src/polisyos/berl/__init__.py tests/unit/berl/test_persistence.py tests/integration/scientist_berl/test_explanation_reliability_bridge.py
All checks passed!

$ env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff format --check src/polisyos/berl/persistence.py src/polisyos/berl/__init__.py tests/unit/berl/test_persistence.py tests/integration/scientist_berl/test_explanation_reliability_bridge.py
4 files already formatted
```

## Source-call boundary and capability status

To check whether a product call site is present, I walked every Python file under `src/polisyos` (2,748 `.py` files) with an AST census for direct/aliased imports and calls to `persist_explanation_bundle` / `load_explanation_bundle`. Result: `python_source_denominator=2748 root=src/polisyos; parse_failures=0`; `direct_imports=2 direct_or_alias_calls=0`. Both imports are the public re-exports in `src/polisyos/berl/__init__.py`; there are no source call sites. The integration test explicitly invokes persist/load after `ExplanationOrchestrator.explain` and proves those APIs compose with the existing validators, but it is a test bridge, not a production caller. This matches the package README's status: persistence is `implemented_but_not_orchestrated` until a product caller wires it; do not promote the full explanation capability to closed on this evidence.

The persistence source slice itself has no blocker found: fixed kind/media/schema, selected view, content decoding, required wire fields, and wrong-view refusal are exercised. This review's bucket is no new escape to repair in that bounded mechanism; there is no P40 repair round to consume. The separate producer/bridge gap remains `bridge_missing` / `implemented_but_not_orchestrated`, and the conditional observed-law capability remains `producer_missing`. The integration test uses local fixtures and passes a self-declared law reference only to prove refusal; it does not establish a real law, trusted provenance, production currentness, or an external authority fact. No G closure is proposed.

## Reproducible source-call census

The census used the following inline Python walk, excluding function definitions from call results by finding calls in the AST rather than matching text:

```python
import ast
from pathlib import Path

root = Path("src/polisyos")
paths = sorted(root.rglob("*.py"))
functions = {"persist_explanation_bundle", "load_explanation_bundle"}
parse_failures, imports, calls = [], [], []
for path in paths:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        parse_failures.append((str(path), exc.lineno, exc.msg))
        continue
    aliases = set(functions)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {
            "polisyos.berl", "polisyos.berl.persistence"
        }:
            for item in node.names:
                if item.name in functions:
                    alias = item.asname or item.name
                    aliases.add(alias)
                    imports.append((str(path), node.lineno, item.name, alias))
        elif isinstance(node, ast.Import):
            for item in node.names:
                if item.name in {"polisyos.berl", "polisyos.berl.persistence"}:
                    imports.append((str(path), node.lineno, item.name, item.asname or item.name))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in aliases:
            calls.append((str(path), node.lineno, fn.id))
        elif isinstance(fn, ast.Attribute) and fn.attr in functions:
            calls.append((str(path), node.lineno, fn.attr))
print(f"python_source_denominator={len(paths)} root={root}; parse_failures={len(parse_failures)}")
print(f"direct_imports={len(imports)} direct_or_alias_calls={len(calls)}")
for row in imports:
    print("IMPORT", "|".join(map(str, row)))
for row in calls:
    print("CALL", "|".join(map(str, row)))
```

Full output:

```text
python_source_denominator=2748 root=src/polisyos; parse_failures=0
direct_imports=2 direct_or_alias_calls=0
IMPORT src/polisyos/berl/__init__.py|18|load_explanation_bundle|load_explanation_bundle
IMPORT src/polisyos/berl/__init__.py|18|persist_explanation_bundle|persist_explanation_bundle
```

## Final Phase-5 bridge delta review — 2026-10-10

This review covers the five Phase-5 bridge delta paths from the named ready snapshot, plus the unchanged persistence implementation as the producer boundary. At review start the attached candidate was branch `codex/e02-unified-local-20261009`, HEAD `7b1b50dd1b36d8a67927775e68560eaf4842dbe1`, tree `9bad8150d5efa1d2186f0188041de81ef13f15bf`, parent `6a4bdc1be190d00fd0f25d38709184ab9cb4c0df`. The reviewed source was the live working-tree snapshot; each listed byte hash matched the handoff fingerprints exactly:

- `src/polisyos/scientist/validation/phase5_preflight.py@6e241e1414a8a12cc12ca84fcd11431314b67edff7a44158f7822350e6cc5b12`
- `tests/integration/scientist_berl/test_explanation_reliability_bridge.py@0ee4f405fc8b653bfe4910f9266f3f36753c4b4b8e6fbb1b1b4e426e0eb268f9`
- `tests/unit/scientist/validation/test_phase5_preflight.py@43f44813a942426b79342fc570a6f66267c126c11466fbed8d4003d16087f7ac`
- `src/polisyos/berl/README.md@0e5059c7d3976596baaf1f9f253c0cce5fd3613e49e1dc992fb51d5e1b3e5f96`
- `release-fragments/unreleased/2026-10-10-e02-la036-explanation-cas-bridge.toml@57c7a6f5bdb6b87da13e4e98116ae14b0640f47b272436217335213bb66a18b1`
- Unchanged producer/reader context: `src/polisyos/berl/persistence.py@87a7aad8e0a7af06686dc0f9f4439cd43a9ae5b34c56db6485da1bd8c33a48c9`.

### Blocking finding — P40 SAME_CLASS_DEEPER: default-only producer refs are rejected by the new Phase-5 bridge

The normal writer path on an empty CAS returns an `ExplanationBundleRef` with `manifest_profile_sha256=None`. The public `load_explanation_bundle` accepts and successfully resolves that ref as the CAS default view. The new Phase-5 reader, however, rejects the same valid writer output before loading it because `_load_explanation_bundle_payload` requires a non-empty profile digest. This leaves the ordinary producer → persisted artifact → Phase-5 consumer path blocked. It is the selected-view/profile identity class already being reviewed, one level deeper: the existing collision fixture exercises only the case where a second manifest view forces a non-null profile.

I independently reproduced the boundary using the actual `ExplanationOrchestrator` on the test's deterministic two-feature model, a fresh temporary `FileSystemCAS`, `persist_explanation_bundle`, the public fresh-store loader, and `run_phase5_artifact_preflight`. Exact result:

```text
producer_ref_profile=None
standalone_loader_bundle_id_matches=True
phase5_verdict=blocked
phase5_readiness=blocked
failed_refs=['sha256:dac59258579a9ac877c48cf06f6819ba32d38bfa583bb197bd287bb59fe18796 (explanation_bundle_ref_invalid)']
publishable=False
```

The artifact is valid and the direct reader succeeds; the consumer refusal is specifically the newly added profile gate. The existing integration's positive setup first calls `store.put_json` with schema `0.9.0`, then persists the same content with schema `1.0.0`. That creates a selected alternate manifest view and makes the persist call return a non-null profile. This is a valid profile-collision test, but it does not represent a fresh ordinary CAS and masks the producer/consumer incompatibility above.

The smallest repair direction is to make the normal persistence producer return a full explicit view identity for the manifest it just wrote, while keeping Phase-5's refusal of caller-supplied profileless BERL refs. Add a fresh empty-CAS producer → persisted ref → Phase-5 positive, alongside the current profileless-caller negative and exact lineage assertion. Do not weaken the reader to silently choose a default view. No G closure is proposed.

### What passed in the bounded slice

The Phase-5 code now routes BERL refs through `load_explanation_bundle` using the selected ref, attaches that ref to the loaded evidence record, and writes the artifact ID plus manifest-profile digest into the persisted Phase-5 report's `InputRef`. Other Phase-5 artifact kinds still use the generic artifact-ID loader. The integration fixture exercises a successful selected-profile route and checks the report manifest's input lineage against that ref. It also exercises profileless and wrong-profile refusal, both Phase-5 input routes (explicit preflight input and state artifact index), and conditional-profile blocking after the real orchestrator emits a diagnostic with no attributions despite a self-asserted law-ref string.

I ran the following source-bound, focused test selection from `policy-engine/`, with the product `.venv` and `PYTHONPATH=src:.`:

```text
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python -m pytest -vv -p no:cacheprovider tests/unit/berl/test_persistence.py::test_persistence_returns_selected_typed_ref_and_reads_its_manifest_view tests/unit/berl/test_persistence.py::test_loader_refuses_manifest_views_outside_the_fixed_bundle_contract tests/unit/berl/test_persistence.py::test_loader_refuses_persisted_payloads_missing_required_wire_fields tests/unit/berl/test_persistence.py::test_public_loader_rejects_reference_claims_with_wrong_kind_or_media tests/unit/berl/test_persistence.py::test_loader_refuses_payload_version_that_disagrees_with_manifest tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers tests/unit/scientist/validation/test_phase5_preflight.py::test_preflight_refuses_present_malformed_explanation_refs
```

Complete deciding output:

```text
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0 -- /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/bin/python
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
hypothesis profile 'polisyos' -> database=DirectoryBasedExampleDatabase(PosixPath('/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/_cache/hypothesis'))
test taxonomy enabled; active pytest quarantines=0
rootdir: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine
configfile: pytest.ini
plugins: benchmark-5.2.3, anyio-4.12.0, xdist-3.8.0, jaxtyping-0.3.4, asyncio-1.3.0, hypothesis-6.151.2, langsmith-0.6.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 14 items

tests/unit/berl/test_persistence.py::test_persistence_returns_selected_typed_ref_and_reads_its_manifest_view PASSED [  7%]
tests/unit/berl/test_persistence.py::test_loader_refuses_manifest_views_outside_the_fixed_bundle_contract[scientist.other_bundle-application/json-https://polisyos.local/schemas/berl/explanation_bundle/1.0.0-1.0.0] PASSED [ 14%]
tests/unit/berl/test_persistence.py::test_loader_refuses_manifest_views_outside_the_fixed_bundle_contract[scientist.explanation_bundle-text/plain-https://polisyos.local/schemas/berl/explanation_bundle/1.0.0-1.0.0] PASSED [ 21%]
tests/unit/berl/test_persistence.py::test_loader_refuses_manifest_views_outside_the_fixed_bundle_contract[scientist.explanation_bundle-application/json-https://polisyos.local/schemas/berl/explanation_bundle/1.0.0.other-1.0.0] PASSED [ 28%]
tests/unit/berl/test_persistence.py::test_loader_refuses_manifest_views_outside_the_fixed_bundle_contract[scientist.explanation_bundle-application/json-https://polisyos.local/schemas/berl/explanation_bundle/1.0.0-0.9.0] PASSED [ 35%]
tests/unit/berl/test_persistence.py::test_loader_refuses_persisted_payloads_missing_required_wire_fields PASSED [ 42%]
tests/unit/berl/test_persistence.py::test_public_loader_rejects_reference_claims_with_wrong_kind_or_media PASSED [ 50%]
tests/unit/berl/test_persistence.py::test_loader_refuses_payload_version_that_disagrees_with_manifest PASSED [ 57%]
tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[marginal_interventional-kernel_shap_marginal] PASSED [ 64%]
tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[conditional_observational-kernel_shap_conditional] PASSED [ 71%]
tests/unit/scientist/validation/test_phase5_preflight.py::test_preflight_refuses_present_malformed_explanation_refs[not-an-artifact-ref-explanation_bundle_ref_invalid] PASSED [ 78%]
tests/unit/scientist/validation/test_phase5_preflight.py::test_preflight_refuses_present_malformed_explanation_refs[sha256:1111111111111111111111111111111111111111111111111111111111111111-explanation_bundle_ref_invalid] PASSED [ 85%]
tests/unit/scientist/validation/test_phase5_preflight.py::test_preflight_refuses_present_malformed_explanation_refs[reference2-explanation_bundle_ref_invalid] PASSED [ 92%]
tests/unit/scientist/validation/test_phase5_preflight.py::test_preflight_refuses_present_malformed_explanation_refs[reference3-explanation_bundle_ref_invalid] PASSED [100%]

=============================== warnings summary ===============================
.venv/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: cache_dir
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[marginal_interventional-kernel_shap_marginal]
tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[marginal_interventional-kernel_shap_marginal]
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/lib/python3.14/site-packages/torch/jit/_script.py:1474: DeprecationWarning: `torch.jit.script` is not supported in Python 3.14+ and may break. Please switch to `torch.compile` or `torch.export`.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 14 passed, 3 warnings in 13.00s ========================
```

I also ran a tiny ephemeral temporary-CAS payload-tamper probe. After `persist_explanation_bundle`, the temporary blob bytes were replaced with `b"tampered bytes"`; loading through a fresh `FileSystemCAS` refused with `ValueError:explanation_bundle_persisted_payload_invalid`. This was a temporary test artifact only; no product source or tracked fixture was changed. The existing unit suite also refuses a required-wire-field omission and a schema-version disagreement. It does not claim a separate persisted production payload or any external authority fact.

The author's wider focused receipt is at `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/cas-contracts/berl-phase5-bridge-20261010-final/`: command `command.txt@4abd18f7faa0424a30494a966d387a86fcf74ec91280ec8a3a42632c13ba98cc`, stdout `stdout.txt@26e15289d2fdb673de9090857eac9fa534bc0479b5e2ae84a7d60d43c25375eb`, stderr `stderr.txt@e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, and exit `exit.txt@9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`. Its recorded command covered seven focused files and its source-bound output records 69 passing cases, zero stderr, exit 0. That run is the author's receipt; the 14-case command above is my independent replay.

### Capability and LA-036 limits

The delta improves the test witness for selected-view lineage, but it does not create a production call site. The existing complete-source AST census remains the relevant boundary: `src/polisyos` contained 2,748 Python files, with two direct imports (the public re-exports) and zero direct or aliased `persist_explanation_bundle` / `load_explanation_bundle` calls. The package README and release fragment correctly retain `implemented_but_not_orchestrated`; the Runtime warrant-reliability consumer still takes an inline bundle mapping rather than resolving the CAS ref. The Phase-5 test is a test bridge, not a product caller. The source-call gap therefore remains open independently of the default-profile blocker.

For the tested LA-036 method-identity boundary, the marginal request `kernel_shap_marginal` retains `requested_method_id=kernel_shap_marginal` while reporting the executed fallback `effective_method_id=kernel_shap`; Phase-5 and Runtime consume the persisted marginal bundle successfully in the collision fixture. Conditional `kernel_shap_conditional` is only a diagnostic with no attributions; the test's self-asserted law-ref string does not provide a verified law, and both consumers block it. This verifies the tested method distinction and refusal behavior, not a verified conditional-law producer, externally supplied law, production currentness, or global LA-036 closure.

Review status: **partial / blocking finding above**. No formal G closure is proposed. Keep the producer/caller gap (`implemented_but_not_orchestrated` / `bridge_missing`) and conditional-law gap (`producer_missing`) explicit until independently adjudicated.
## Final default-selector repair delta — 2026-10-10

This is an independent delta review of the five named paths; the persistence implementation is unchanged. The reviewed working-tree bytes match the supplied ready fingerprints. At review time the candidate remained attached to branch codex/e02-unified-local-20261009 at HEAD b1c63a097f447281ca690ebbf8377598019bcd92, tree 8cf344830ca8ef16acf567611b3a80b08e22f4ae, parent 7b1b50dd1b36d8a67927775e68560eaf4842dbe1.

- policy-engine/src/polisyos/scientist/validation/phase5_preflight.py@b2b60036844408dba22aa1895941a837b6b5a50e469f2ae2249f71f2bcfd021a
- policy-engine/tests/unit/scientist/validation/test_phase5_preflight.py@b383f6631534b656a5dca76f2f3d20668885a976457d3fc9a052243b1c0d58ce
- policy-engine/tests/integration/scientist_berl/test_explanation_reliability_bridge.py@531fb06c6bab727128ef640f38c5bf2597c836d0a1baa71b211c7daa6a8cc518
- policy-engine/src/polisyos/berl/README.md@7db195af738e24d8ad391ba516b515ad7d36f4bb76db9173d002307cd90e824d
- policy-engine/release-fragments/unreleased/2026-10-10-e02-la036-explanation-cas-bridge.toml@f9afc69713c9d6f7cf1dc9c14f95f7cefd44650fd9c95e843e9ae8dac26f9980
- Unchanged producer/reader context: policy-engine/src/polisyos/berl/persistence.py@87a7aad8e0a7af06686dc0f9f4439cd43a9ae5b34c56db6485da1bd8c33a48c9.

### Review result: ready for this bounded selector contract, with the declared P40 residual

The prior blocker is fixed within the current CAS selector semantics. In the Phase-5 reader, a supplied profile digest is passed unchanged to the BERL reader and resolves that exact view. A missing digest now means the store’s selector-free default view; Phase-5 still validates that actual manifest’s fixed kind, media, schema name/version, required wire fields, canonical JSON, and full ExplanationBundle payload. It does not select a “latest” manifest. The persisted Phase-5 InputRef carries the same artifact ID and selector: explicit profile for an alternate view, None for the default. The public API has not been changed to manufacture or infer a profile digest.

I verified the local Core FileSystemCAS contract in source and through its existing focused test: None resolves the selector-free first manifest, which is immutable; a later same-content write with another manifest is stored as an alternate selected view. tests/unit/remediation/test_cas_01.py::test_distinct_profiles_get_honest_views_of_one_blob passed independently. The BERL integration now runs both an empty CAS and a same-ID collision with a preexisting 0.9.0 default, for both marginal and conditional requests. On the empty CAS, persistence returns None for the default view and Phase-5 admits that default only after reading and validating it. In the collision case the 1.0.0 alternate has an explicit profile; stripping that selector falls back to the 0.9.0 first default and refuses on the fixed schema contract. The integration compares persisted validation-report InputRef fields against the actual producer ref in both cases and exercises the state-index consumer path too.

I reran this independent focused matrix from policy-engine using its .venv Python, PYTHONPATH=src:., and one numerical thread:

~~~text
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python -m pytest -vv -p no:cacheprovider tests/unit/berl/test_persistence.py::test_persistence_returns_selected_typed_ref_and_reads_its_manifest_view tests/unit/berl/test_persistence.py::test_loader_refuses_manifest_views_outside_the_fixed_bundle_contract tests/unit/berl/test_persistence.py::test_loader_refuses_persisted_payloads_missing_required_wire_fields tests/unit/berl/test_persistence.py::test_public_loader_rejects_reference_claims_with_wrong_kind_or_media tests/unit/berl/test_persistence.py::test_loader_refuses_payload_version_that_disagrees_with_manifest tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers tests/unit/scientist/validation/test_phase5_preflight.py::test_preflight_refuses_present_malformed_explanation_refs tests/unit/remediation/test_cas_01.py::test_distinct_profiles_get_honest_views_of_one_blob
~~~

Complete output:

~~~text
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0 -- /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/bin/python
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
hypothesis profile 'polisyos' -> database=DirectoryBasedExampleDatabase(PosixPath('/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/_cache/hypothesis'))
test taxonomy enabled; active pytest quarantines=0
rootdir: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine
configfile: pytest.ini
plugins: benchmark-5.2.3, anyio-4.12.0, xdist-3.8.0, jaxtyping-0.3.4, asyncio-1.3.0, hypothesis-6.151.2, langsmith-0.6.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 18 items

tests/unit/berl/test_persistence.py::test_persistence_returns_selected_typed_ref_and_reads_its_manifest_view PASSED [  5%]
tests/unit/berl/test_persistence.py::test_loader_refuses_manifest_views_outside_the_fixed_bundle_contract[scientist.other_bundle-application/json-https://polisyos.local/schemas/berl/explanation_bundle/1.0.0-1.0.0] PASSED [ 11%]
tests/unit/berl/test_persistence.py::test_loader_refuses_manifest_views_outside_the_fixed_bundle_contract[scientist.explanation_bundle-text/plain-https://polisyos.local/schemas/berl/explanation_bundle/1.0.0-1.0.0] PASSED [ 16%]
tests/unit/berl/test_persistence.py::test_loader_refuses_manifest_views_outside_the_fixed_bundle_contract[scientist.explanation_bundle-application/json-https://polisyos.local/schemas/berl/explanation_bundle/1.0.0.other-1.0.0] PASSED [ 22%]
tests/unit/berl/test_persistence.py::test_loader_refuses_manifest_views_outside_the_fixed_bundle_contract[scientist.explanation_bundle-application/json-https://polisyos.local/schemas/berl/explanation_bundle/1.0.0-0.9.0] PASSED [ 27%]
tests/unit/berl/test_persistence.py::test_loader_refuses_persisted_payloads_missing_required_wire_fields PASSED [ 33%]
tests/unit/berl/test_persistence.py::test_public_loader_rejects_reference_claims_with_wrong_kind_or_media PASSED [ 38%]
tests/unit/berl/test_persistence.py::test_loader_refuses_payload_version_that_disagrees_with_manifest PASSED [ 44%]
tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[empty-cas-marginal_interventional-kernel_shap_marginal] PASSED [ 50%]
tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[empty-cas-conditional_observational-kernel_shap_conditional] PASSED [ 55%]
tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[same-id-collision-marginal_interventional-kernel_shap_marginal] PASSED [ 61%]
tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[same-id-collision-conditional_observational-kernel_shap_conditional] PASSED [ 66%]
tests/unit/scientist/validation/test_phase5_preflight.py::test_preflight_refuses_present_malformed_explanation_refs[not-an-artifact-ref-explanation_bundle_ref_invalid] PASSED [ 72%]
tests/unit/scientist/validation/test_phase5_preflight.py::test_preflight_refuses_present_malformed_explanation_refs[sha256:1111111111111111111111111111111111111111111111111111111111111111-explanation_bundle_ref_invalid] PASSED [ 77%]
tests/unit/scientist/validation/test_phase5_preflight.py::test_preflight_refuses_present_malformed_explanation_refs[reference2-explanation_bundle_ref_invalid] PASSED [ 83%]
tests/unit/scientist/validation/test_phase5_preflight.py::test_preflight_refuses_present_malformed_explanation_refs[reference3-explanation_bundle_manifest_contract_mismatch] PASSED [ 88%]
tests/unit/scientist/validation/test_phase5_preflight.py::test_preflight_refuses_present_malformed_explanation_refs[reference4-explanation_bundle_ref_invalid] PASSED [ 94%]
tests/unit/remediation/test_cas_01.py::test_distinct_profiles_get_honest_views_of_one_blob PASSED [100%]

=============================== warnings summary ===============================
.venv/lib/python3.14/site-packages/pytest/config/__init__.py:1428
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/lib/python3.14/site-packages/pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: cache_dir
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[empty-cas-marginal_interventional-kernel_shap_marginal]
tests/integration/scientist_berl/test_explanation_reliability_bridge.py::test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers[empty-cas-marginal_interventional-kernel_shap_marginal]
  /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/.venv/lib/python3.14/site-packages/torch/jit/_script.py:1474: DeprecationWarning: torch.jit.script is not supported in Python 3.14+ and may break. Please switch to torch.compile or torch.export.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 18 passed, 3 warnings in 13.14s ========================
~~~

The author's broader receipt is under policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/cas-contracts/berl-phase5-default-selector-20261010/: command.txt@4abd18f7faa0424a30494a966d387a86fcf74ec91280ec8a3a42632c13ba98cc, stdout.txt@a7638e8a54ead5af2541933ce7e84c86c3af5014355dc2663b69cde6fe8437d8, exit.txt@9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa. The recorded seven-file command reports 72 passing cases and exit 0. That directory has no separate stderr.txt, so I do not claim an independently recorded zero-stderr stream; my 18-case replay completed successfully with the three warnings shown above.

The previous independent finding that Phase-5 must reject every profileless ref and that the writer must manufacture an explicit digest described the earlier source snapshot only. This delta intentionally changes that contract: an absent digest is the existing optional IR selector for the immutable default view. The former default-only blocker is resolved for this declared selector contract; it is not still a code blocker in these exact bytes.

### Bounded P40 residual: a valid default selector cannot prove preservation of a lost non-default selector

The source and updated docs state that a profileless ref selects only the immutable default and does not prove that some upstream non-default selector was not stripped. If same artifact ID has same-kind/schema views whose inputs differ, the BERL reader validates the chosen default view against its artifact contract but does not establish that a caller originally intended that view. A caller that needs non-default manifest lineage must preserve the explicit profile. This is the named bounded residual, not another per-example repair request; the current scope does not claim profileless-history rollout, anti-tamper authority, or recovery of a prior selector from a valid None. The Phase-5 report records None for default and the explicit digest when supplied, and the tested same-ID collision demonstrates refusal when stripping the selector would resolve to an incompatible old schema.

This delta does not add a product caller. The independent source-call census in the preceding section still applies: automatic ExplanationOrchestrator-to-CAS wiring remains implemented_but_not_orchestrated; Runtime continues to take an inline validated bundle rather than resolve the ref. The conditional-law producer remains absent, and the self-asserted law ref still yields a diagnostic/no-attribution bundle that Phase-5 and Runtime block. I propose no formal G closure.

Review conclusion: **READY for the bounded Phase-5 default-selector source contract, subject to the explicit profileless/non-default lineage residual above. This is not G acceptance of the full BERL capability or LA-036.**
