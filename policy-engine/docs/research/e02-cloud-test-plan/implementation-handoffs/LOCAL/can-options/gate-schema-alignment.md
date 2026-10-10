# GateRequest runtime/schema parity receipt

This is a source-model and contract-test candidate; it does not claim formal G acceptance. The generated snapshot, OpenAPI, and client surfaces remain root-owned and were not edited.

P40 classification: same P38 runtime-versus-schema contract class, one level deeper at version-conditional nested requiredness. Runtime validation and `GateRequest.model_json_schema()` now consume the same version-to-required-context-fields mapping. For schema 1.2, JSON Schema requires `context.selected_replay_refs` to be present and non-null; an omitted `schema_version` is covered because Pydantic defaults it to 1.2. Schema 1.1 remains readable without the field. This narrows the GateRequest divergence only; it does not claim closure of other runtime/schema field-specific constraints.

The new contract test compares Pydantic validation with Draft 2020-12 validation for explicit 1.2 missing/null/empty refs, legacy 1.1 without refs, and omitted-version missing/empty refs. Before the model change it failed exactly on 1.2 missing, 1.2 null, and omitted-version missing: JSON Schema accepted those while Pydantic rejected them. After the change, the five-file serial gate suite passed 49 tests with two existing Python 3.14 TorchScript deprecation warnings.

Verification:

- `.venv/bin/python -m ruff check --config ruff.toml src/polisyos/ir/governance/gate.py tests/contract/test_gate_models.py` — passed.
- `.venv/bin/python -m ruff format --check src/polisyos/ir/governance/gate.py tests/contract/test_gate_models.py` — passed.
- `.venv/bin/python -m py_compile src/polisyos/ir/governance/gate.py tests/contract/test_gate_models.py` — passed.
- Release TOML parsed successfully.
- The serial pytest command and complete output/JUnit are under `raw/gate-schema-alignment/`; JUnit records 49 cases, zero failures, and zero errors.

The schema snapshot check/generation remains pending root's canonical 104-model regeneration, as directed. The current committed snapshot must be regenerated from this model before the source-to-snapshot contract can be called aligned. The release fragment now classifies this as a `public_stable` persisted-artifact-format change and leaves `public_surface_inventory_reviewed = false` because no full inventory review was performed. The fragment explicitly keeps formal G acceptance pending.

Source and output manifests are `raw/gate-schema-alignment/source.sha256` and `raw/gate-schema-alignment/outputs.sha256`.
