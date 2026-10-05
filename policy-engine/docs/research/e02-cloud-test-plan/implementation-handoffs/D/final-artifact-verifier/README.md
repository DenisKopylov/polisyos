# Independent Git artifact verifier

Run `python verify.py --repo <repository> --target <full-commit> --base <full-commit>`.
The optional `--output <path>` retains the full machine-readable report.

The script reads immutable Git blobs, all tracked D handoff JSON, all added or
modified JSON in the selected base-to-target diff, and changed release fragments.
It discovers file/reference/hash pairs from the receipts, preserves explicit
historical source bindings, and checks available bytes, sizes and Git blob IDs.
The canonical finding-owner rows are joined to the complete routes and cells
tables. Their ID sets, finding routes, owners, cell identities and source
line/byte locators are reconciled against the baseline map. Counts are derived;
the campaign's 45/17/115 counts are not constants in the verifier.

Unreceived raw or external files, unavailable Git objects, and hashes without a
byte locator are reported as limitations. Their bytes are not verified. Local
Git-reference absence, mismatched available bytes, incomplete census mappings,
and invalid JSON/TOML are errors. Closure and program behavior are outside this
artifact check. The companion tests are
`tests/repo_quality/tools/test_e02_final_artifacts.py`; they retain declared
labels while corrupting payload bytes, omit a routed cell, shift byte locators,
exercise old source bindings, and distinguish raw absence from a missing local
artifact. No original CI replay is performed.

`architecture-classification.json` separately compares every reported import
edge with its actual base/candidate AST statements. A statement's presence at
the base is not an inherited-red verdict for the complete architecture gate.
