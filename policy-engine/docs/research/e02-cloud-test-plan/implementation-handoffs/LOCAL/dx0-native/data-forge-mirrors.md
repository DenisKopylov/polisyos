# DataForge owner mirror tests

The three tests below add direct owner behavior coverage for the DataForge routes selected in `ratchet-repair-routing-current.md`. Their source modules were read-only for this slice. The supplied candidate base is `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a`; source and test byte hashes are retained in the ignored receipt `raw/data-forge-mirrors-sha256.json` (receipt SHA-256 `f31f421fb0b969695ea0e93456708947d7e76c71f46c316531e59b04b28bcee7`). The complete source/test-route denominator remains the referenced census JSON, not this three-file sample.

| Direct owner test | Property exercised |
|---|---|
| `tests/unit/data_forge/domains/academic/batch/test_table_extractor.py` | Exercises the pure numeric-cell parser and parameter conversion without Marker/PDF installation. A cell with an estimate, standard error, significance marker, and confidence interval yields the corresponding typed dictionary values and source parameter; surrounding whitespace preserves the parse; a nonnumeric malformed cell produces no candidate value. |
| `tests/unit/data_forge/domains/catalog/batch/test_material_inputs.py` | Exercises `_material_file_snapshot`, `generation_member`, and the real YAML `lru_cache`. Selected-present, selected-absent, and not-selected material have distinct member identities; required absence raises; replacing bytes at the same selected path changes both the generation member and parsed cached value. This is a deeper falsifier for the existing C05 material-basis/currentness class: if the generation basis or YAML cache were path-only, the same-path changed-byte assertions would remain green incorrectly. |
| `tests/unit/data_forge/domains/catalog/knowledge/test_country_codes.py` | Exercises equivalence of ISO2, ISO3, numeric, and name-alias forms for Armenia, preserving numeric code `051`; unknown code normalization stays empty, an omitted scope uses the existing regional default, and an unregistered named scope is refused. |

The table extractor emits generic numeric cells with their source headers; this test does not assert that numeric p-value cells should be excluded, because that semantic rule is not established by the current contract. No table-extractor source change is included. The material-basis test verifies the selector/presence/byte behavior at the producer helper and its parser cache; it does not claim production-generation currentness beyond those exercised functions.

Verification allowed in this slice was limited to the three target tests:

```text
.venv/bin/python -m ruff check tests/unit/data_forge/domains/academic/batch/test_table_extractor.py tests/unit/data_forge/domains/catalog/batch/test_material_inputs.py tests/unit/data_forge/domains/catalog/knowledge/test_country_codes.py
All checks passed!

.venv/bin/python -m ruff format --check [same three paths]
3 files already formatted

.venv/bin/python -m py_compile [same three paths]
exit=0
```

Pytest was not run under the parent instruction to defer it until the combined lane grant. Earlier Ruff import-order errors were repaired only in the new test files; the final check above passed.
