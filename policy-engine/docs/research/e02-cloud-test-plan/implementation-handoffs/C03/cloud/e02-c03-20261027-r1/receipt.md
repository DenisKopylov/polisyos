# C03 / e02-c03-20261027-r1 receipt

## Identity and admission

- Environment: `polisyos` (`6965429cdb308191a0e6eb63cb118ea3`); task token `e02-c03-20261027-r1`.
- Working directory/branch: `/workspace/polisyos`; `work` (attached, clean on admission).
- Base commit/tree: `8db01b1076e425b7998b05a658776c991b7bd594` / `1706923ebe943f1a332dca4860cd145ddd366e36`.
- Proposal: `implementation-handoffs/LOCAL/executor-handover-20261027/proposals/i4-legacy-r2/patch.diff`, SHA-256 `be21279e6fee6e167026f5aad1613d57c183944034106ac2208d403473eacbbd`.
- Admission resources: overlay disk 32 GiB total, 2.8 GiB used, 28 GiB available; RAM 17 GiB total, 13 GiB free, 16 GiB available; no swap. Existing `.venv` occupied 1.1 GiB.

## Changed footprint and review

- Added the corrected deterministic LA-040 regression to `tests/unit/data_forge/legal_batch/test_embed_local.py`; no producer or shared/generated family changed.
- Correction from the proposal: encoder-call accounting is scoped to the provisions batch (`encoded_batches[-1]`), to target the provisions projection explicitly; this regression intentionally empties entity and fact rows, so it does not exercise their nonempty encoder calls.
- The fixture creates the legacy flat NPZ/HNSW pair through `build_embedding_index`, proves absent selector and `legacy-flat`/nonselected resolution, then invokes the real Legal producer incrementally. It independently checks projected content basis and encoder/profile binding, NPZ ID/row/vector identity, real HNSW nearest labels, changed-text nonreuse, append-only reuse, withdrawal, and immutable history.
- Capability status remains `verification_missing`: the supported native backend could not be provisioned in this environment, so positive, adversarial removal, existing remediation selectors, and the optional real Legal entrypoint are `UNRUN`, not product failures.

## Outcomes

- PASS — proposal SHA-256 and exact base/tree matched.
- PASS — `git diff --check`.
- PASS — `ruff check tests/unit/data_forge/legal_batch/test_embed_local.py` (system shim; all checks passed).
- PASS — `.venv/bin/python -m py_compile tests/unit/data_forge/legal_batch/test_embed_local.py`.
- ERROR (environment) — the pre-existing `test_build_local_embeddings_and_indexes` also reaches the native writer and fails solely because `hnswlib` is absent.
- ERROR (environment) — pinned `hnswlib==0.8.0` installation: network tunnel failure; complete output is in `hnsw-install.txt`.
- ERROR (environment) — targeted pytest reached collection/execution and failed solely at `import hnswlib`; complete output is in `targeted-pytest.txt`.
- UNRUN — property-removal control (preserve selector/status markers while permitting legacy-flat reuse); native HNSW prerequisite unavailable, so no false red is claimed.
- UNRUN — relevant `test_emb_03.py` append/withdraw/profile/corrupt-selector selectors; defining new discriminator could not execute first.
- UNRUN (`not_established`) — `POLISYOS_RUN_LEGAL_PROFILED_ENTRYPOINTS=1 ...::test_ordinary_legal_cli_generation_preserves_candidate_default_exclusion`; admitted C12 offline asset identities are unavailable and no model was downloaded.

## Exact rerun

Install the repository-pinned vector-search extra in a supported frozen environment, then run alone:

```sh
cd policy-engine
.venv/bin/python -m pytest -q -ra tests/unit/data_forge/legal_batch/test_embed_local.py::test_legacy_flat_pair_rebuilds_changed_text_then_reuses_current_membership
```

For the required removal control, temporarily make `_load_reusable_vectors` accept `reference.status == "legacy"` / `selected is False` while leaving marker/status fields and this test unchanged; rerun the same selector and retain the complete red output, then restore and rerun green. Do not commit that mutation.

The affected actual Legal entrypoint remains a separate layer and, only with admitted local C12 assets, is:

```sh
POLISYOS_RUN_LEGAL_PROFILED_ENTRYPOINTS=1 POLISYOS_I4_RECEIPT_DIR=<unique-dir> .venv/bin/python -m pytest -q -ra tests/integration/data_forge_runtime/test_legal_runtime_material_entrypoints.py::test_ordinary_legal_cli_generation_preserves_candidate_default_exclusion
```

No schema/public/generator companion is required because production/public surfaces are unchanged. LA-028, LA-032, LA-033, and both LA-046 occurrences remain separate and unclaimed.

Coordinator source review: GO for this bounded provision-vector regression, with native HNSW/removal verification still pending. This correction does not alter the received author diff identity or imply Legal source authority.
