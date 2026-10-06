# Independent selector lineage review

`c1-full-output.txt` preserves the complete observed exception and full static trace for root c1d031ed48134a2c084b937f0275884aeb40971c. `c1-observed-driver.txt` preserves the exact runnable Python driver used in that observation. The observer caught the selector exception, so its own process returned zero while the observed instrument outcome was FAIL. No selector output was published; no pytest, collection, product code, or gate ran.

The complete traced set was 229 existing test files and 18 missing names: 14 canonical planned names with reviewed mappings, plus four incidental source constants without mappings. All 18 already carried `UNRUN_named_selector_absent`. The four incidental origins were solely `script_native_child_static`, reached through current-native-pytest-input-admission.json → b336.json → review.py. Source regex discovery of a metadata discriminator's constants established lineage; it did not establish an eligible executable test. Exact command descriptor shape alone cannot establish that distinction either.

The original observer's annotation incorrectly appended `.py` to markdown origin locators. Its original `source_refs` locators and complete membership/counts were correct. `normalize_origins.py` reconciles those locators generically against the full pinned Git path set; `c1-source-origins.json` contains its complete output. This correction does not modify the original output or classify its failure as a product defect.

`trace.py` is the reusable successor observer. It resolves source locators by exact tracked prefixes and captures both normal return and exception. It runs only the unchanged Git-reading selector from the requested SHA. To use a fresh isolated output directory:

```bash
/workspace/polisyos/policy-engine/.venv/bin/python policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/final-selector-lineage-independent-review/trace.py --repo /workspace/e02-B-current-coordination --target <immutable-SHA> --out <fresh-ignored-directory>
```

Mapping availability, canonical plan membership, tracked file existence, and test execution remain distinct predicates. Missing paths must retain explicit UNRUN; incidental constants must not satisfy canonical criteria or become collected cases. This review does not endorse a prefix exclusion, a per-name mapping, or an unknown file execution rule.
