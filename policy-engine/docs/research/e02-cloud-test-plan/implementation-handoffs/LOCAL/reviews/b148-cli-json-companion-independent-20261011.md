# Independent review: B148 CLI JSON refusal companion

**Disposition: GO for the bounded two-path CLI JSON refusal-projection change; not a B148 closure.** Current candidate HEAD is `259cba002b8227734f793b65e54625463579fb41` / tree `15362abfd369f2c2787d8adeeb579a9017c473ea`. This was read-only source/test review; no tests, heavy commands, or source edits were performed.

## Pinned inputs

- `src/polisyos/core/components/_cli_replay.py` current SHA-256: `44519d13c82169a16e61bfe0eab31dd4139a41888595657f91bd78124a49a138` (tracked WIP). Its diff also contains an unrelated import-line reflow; the B148 edits are the no-graph JSON response at lines 78–91 and the `verification_failed` projection at lines 98–112.
- `tests/unit/core/components/test_cli_replay.py` current SHA-256: `3939b4a97e39b957ae859b7dd9e0e1176c24db763427fd19ac04301570c8533e` (untracked WIP).
- The actual importer source `src/polisyos/core/artifacts/_transfer_ops.py` is SHA-256 `0881b924e2bb9d9f602df7d2643dddf09fdbf9d04d0de49ce92e139dd60c09d8`; its `ImportReport` fields are at lines 228–238 and early binding-failure return is at lines 876–910.
- CLI parser/dispatch: `tools/ops_runners/runtime_cli.py` SHA-256 `60cb4d4d24986e2e007422d74707a5e870a0961519ed24aca217a2fde08e61b9`; `main` dispatches `replay` to `_cmd_replay` at lines 94–150, with `--bundle`, `--export`, and `--json` parser options at lines 1010–1059.
- Original acceptance: `docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md:3917–3928`, SHA-256 `9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`. It requires preserving the old readable generation through damaged/truncated/conflicting/competing imports, checking manifest/owner and tenant/cell boundaries where required, and reporting checked, published, and refused outcomes separately rather than collapsing them into copied-file counts.
- Reviewed context: `LOCAL/t1-t2-intake/b148-report-surface-decision.md` SHA-256 `94ba080f17feb3a21395c0d9dee742508e628ce7c039bbd6e4fd408d4d01d7ca`; `LOCAL/t1-t2-intake/b148-original-import-consumer-final-readiness-20261010.md` SHA-256 `640787235ccf7fb2086687db1cbb1604718ad2f2aa31ebf1c1340fd6190429ff`; `LOCAL/reviews/q2-installed-read-api-companion-r2-independent-20261010.md` SHA-256 `719c86f1d1c930b1216390da3f5b58ba3d2ff3bc86a1968ede8127f833d81412`.

## Producer-to-consumer evidence

The new test calls the real `tools.ops_runners.runtime_cli.main` in-process. It creates a real `FileSystemCAS`, writes an artifact, exports a directory bundle, corrupts the exported blob while leaving the inventory intact, then invokes `replay <id> --bundle <dir> --export <path> --json`. No graph, CAS, or report is mocked. The actual CLI path builds its temporary CAS and calls `import_subgraph(..., verify_integrity=False)` (`_cli_replay.py:37–50`); the importer still checks the blob digest against the artifact ID and inventory binding before staging (`_transfer_ops.py:876–910`). The refusal report is therefore produced by the actual importer.

Since the fresh temporary CAS receives no members after this binding refusal, the real completeness check finds no readable root packet and returns `graph=None` (`scientist/replay/deterministic.py:543–561`). The tested export branch then emits JSON to stdout with exit code 1, retaining the graph-unavailable error and the report fields `imported_files=0`, `imported_artifacts=1`, and `verification_failed=[artifact_id]`. The assertion checks the complete `bundle_import` object and empty stderr (`test_cli_replay.py:33–54`). This is a genuine consumer-boundary regression test for the prior behavior that discarded the refusal report. It is not constructor-only or a marker-presence test.

## Boundaries and remaining checks

The test is intentionally a refusal-projection witness, not a valid replay-bundle fixture: it uses `{}` under `kind="test.replay_packet"`, then corrupts the only imported blob. It does not exercise a complete packet, a successful graph/export, or the new empty `verification_failed` field on the graph-present export branch. That branch is not reached by the normal `--bundle` caller when `verification_failed` is nonempty: importer failure returns before staging/publication, and the CLI uses a fresh empty temporary store. The added field is consistent with other JSON replay projections, but the current test does not directly cover a successful complete-bundle export. Do not manufacture an internal helper call solely to claim that branch was exercised.

This CLI test also does not prove the core B148 preservation property: the import target is a fresh temporary CAS, so there is no prior readable object to preserve, and no tenant-owned persistent store, conflicting manifest, signature-policy route, interrupted intake, or competing publication is exercised. `verify_integrity=False` is specific to this CLI route; the corruption is still caught by mandatory content/member binding before staging, but staged-manifest verification is not tested here. Other malformed inputs that raise before `ImportReport` is returned are not serialized by this change; whether those exceptions count as a refused outcome remains the separate report-contract decision already recorded in the B148 decision note.

The returned fields retain their existing mixed meanings: `imported_artifacts` counts distinct IDs encountered during intake, `imported_files` counts staged member files on successful publication and is zero on no-op/refusal, and `imported_refs` is omitted from this CLI projection. The test correctly shows the refusal ID rather than interpreting `imported_artifacts=1` as publication, but it does not establish the full distinct checked/published/refused outcome contract. Keep B148 open for that choice and the direct CAS receipt.

**P40: SAME_CLASS_DEEPER.** This is the existing B148 import-outcome reporting class one consumer edge deeper, not a new importer or authority class. **P38 discriminator:** the narrow property is “the CLI caller can observe the returned integrity refusal when export is blocked for lack of a graph.” Before the change, the code printed only a generic error and hid the report; the corrupted one-artifact bundle is the divergent case. The new test detects removal of the report projection. The broader B148 outcome-unit ambiguity remains outside this two-path repair.

## Focused root selection

Run the new actual consumer selector together with core importer witnesses when verifying the batch:

```sh
.venv/bin/python -B -m pytest -q --tb=short \
  tests/unit/core/components/test_cli_replay.py::test_replay_export_json_reports_refused_bundle_import \
  tests/unit/remediation/test_cas_02.py::test_import_verifies_before_publication_and_preserves_prior_generation \
  tests/unit/remediation/test_cas_02.py::test_import_preserves_distinct_manifest_profile_as_selected_view \
  tests/unit/core/artifacts/test_transfer_import_fresh_process.py::test_imported_view_survives_fresh_process_and_rejects_disk_corruption
```

The first selector is the companion’s CLI consumer proof. The other three are existing API-level preservation/profile/fresh-reader controls; they do not turn the CLI test into a tenant-CAS or full B148 proof. This reviewer did not run them.
