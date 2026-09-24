# P41 D2 safe fixture implementation plan

> For agentic workers: implement this plan task by task; this plan is design
> guidance only and contains no test or product-code changes.

**Goal:** Keep the household proxy-to-point behavioral witness while replacing
the test's production-data copy/edit setup with a test-local typed override. The
test's no-copy/no-write evidence is bounded to the audited call path below.

**Architecture:** Reuse the canonical `load_l5_catalog_authority` owner and the
real `build_production_data_state_world_model_record` production call. In the
single test, apply a typed in-memory override to the loaded L5 authority and
label its identification reference as a test fixture. The real production
registry, L1 catalog, and L4 files remain at their canonical read-only paths;
CAS and materialization outputs stay under `tmp_path`.

**Tech Stack:** Python, dataclass `replace`, pytest `monkeypatch`, SHA-256.

**Spec:** `P41_SAFETY_AUDIT.md`
@`9a21368942ed272b1a448424eb0fa91f760f7748a67d2bde1aebf53744e76e7d`.

## Global constraints

- Never copy files or directories from `production_data`; never write beneath it.
- Keep runtime materialization, CAS and fixture output under `tmp_path`.
- A test override must replace the loaded production registry reference after
  changing the identification mode; only a fixture reference may describe the
  override.
- Do not add a production API solely to make this one test injectable.

These remain operating constraints. The test-local `copytree` guard below is a
regression guard for the former helper; it is not a generic filesystem
no-copy/no-write gate.

## Review focus

- If either module-level loader binding is unpatched, the test must detect it in
  both S1's household state and the persisted S0 registry's household row and
  fixture provenance.
- The override must change only `household_distribution`, leaving other loaded L5
  rows unchanged.
- The world output must identify the test fixture override as its mode source;
  it must not claim that production bytes select point identification.
- The SHA-256 of the canonical identification-mode registry file must be
  identical before and after both builds. This is a single-file mutation check,
  not a digest of all production data or proof that no write was attempted.
- The original whole-file test at the four pinned bases remains `UNRUN` because
  those historical blobs call `copytree` on production data. A safe run of the
  rewritten test at the integration head is a new witness; it never backfills
  or relabels any of those four historical cells.

---

## Finding and source seams

The audited unsafe helper is
`policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py`
@`bae992dfe8986d82559a1898cf4f1076632a977d`.
`_repo_with_household_identification_mode` copies the D2 directory, edits one
registry file, and the sole caller is
`test_l5_proxy_identification_materializes_bounded_state_and_toggle_changes_it`.
The four-cell risk and source path are recorded in `P41_SAFETY_AUDIT.md`.

The canonical loader is
`policy-engine/src/polisyos/runtime/quality/substrate_registry.py`
@`586be103d3a78aff425a3fba72aa5928fa7246e5`.
`SubstrateCatalogPaths` can choose file paths for `load_l5_catalog_authority`,
but no existing overlay type or in-memory override is exposed by the high-level
build. `build_l5_family_binding_profile` and
`build_substrate_registry_from_existing_catalogs` resolve default paths
internally. The materializer is
`policy-engine/src/polisyos/runtime/quality/data_state_substrate.py`
@`c141184edc49e7b9c868dd7d40a91ec0dc32a483`.
The persisted S0 projection is
`policy-engine/src/polisyos/runtime/quality/world_model_record.py`
@`3dc15d1e20307c573826d553a4df66f8cfe3314b`.

There is therefore **no current owner-supported overlay seam** for this
end-to-end call. A test-local typed override is the smallest safe route for the
behavioral property. It does not prove that changing an on-disk registry file
changes the loader result. That narrower file-resolution property remains
outside this test; if it is required, the owner would need an explicit typed
catalog/overlay input with a separate fixture provenance contract.

## Pattern pass

- **P27 (owner bypass):** use the existing substrate-registry loader; add no
  parallel loader or second authority owner.
- **P31 (instance patch):** patch both module bindings used by the production
  call chain: `data_state_substrate_module.load_l5_catalog_authority` and the
  canonical `substrate_registry_module.load_l5_catalog_authority`. The latter is
  called inside `build_substrate_registry_from_existing_catalogs`. Assert the
  point-mode household row and fixture authority reference in the persisted
  registry read through `load_substrate_registry`, as well as in the S0 resolved
  entries; S1 state alone cannot prove the second binding was patched.
- **P32 (trust by form):** the override is a test fixture, never evidence that
  the production registry selects point identification. Put a distinct
  `fixture://policyos-test/l5-identification-mode-overlay/sha256/` ref followed
  by 64 lowercase hex digits in
  `L5CatalogAuthority.identification_mode_registry_ref`.
- **P37/P38:** recompute the digest for the one declared identification-mode
  registry file and assert that every loader wrapper receives that same resolved
  path. The mode override itself is test-supplied. The implementation tests
  downstream behavior of a loaded typed authority; it does not test a file edit
  flowing through source resolution. The `copytree` guard catches only copies
  through that function from this production tree; the bounded no-write
  conclusion also relies on the inspected call graph's `tmp_path`, in-memory,
  and read-only database paths. Keep those limits explicit in the test docstring
  and this record.

## Exact implementation write set

**Modify only:**

- `policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py`
  - Remove `_repo_with_household_identification_mode`, `_symlink_dir`, the
    helper-only path constants, and the now-unused `os` import.
  - Change
    `test_l5_proxy_identification_materializes_bounded_state_and_toggle_changes_it`
    to accept `monkeypatch` and update its docstring to say the point-mode input
    is a test-supplied in-memory overlay, not a production registry rewrite.
  - Add the test-local `substrate_registry_module` import and
    `urllib.parse.quote`; change the `dataclasses` import to include
    `replace`; retain `shutil` for the production-data copy guard.
  - Retain the unmodified production build as the proxy control.
  - Resolve and retain the canonical
    `default_substrate_catalog_paths(REPO_ROOT).identification_mode_registry_path`
    as `canonical_identification_registry_path`; capture its SHA-256 using
    `hashlib.file_digest(stream, "sha256").hexdigest()` on a read-only binary
    stream. This digest covers that registry file only.
  - Wrap the canonical loader: call the original loader for each supplied path,
    copy only its in-memory `identification_modes` mapping, set
    `household_distribution` to `point_identified`, and return
    `replace(authority, identification_modes=modes,`
    `identification_mode_registry_ref=fixture_ref)`. Use this wrapper and
    fixture-ref preimage with `urllib.parse.quote`:

    ```python
    original_loader = substrate_registry_module.load_l5_catalog_authority
    fixture_refs = []

    def load_point_overlay(paths):
        supplied_registry_path = paths.identification_mode_registry_path.resolve()
        assert supplied_registry_path == canonical_identification_registry_path
        authority = original_loader(paths)
        modes = dict(authority.identification_modes)
        modes["household_distribution"] = "point_identified"
        original_ref = authority.identification_mode_registry_ref
        overlay_record = {
            "base_ref": original_ref,
            "base_sha256": source_digest,
            "family_id": "household_distribution",
            "selected_mode": "point_identified",
        }
        overlay_hash = hashlib.sha256(
            json.dumps(
                overlay_record,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        fixture_ref = (
            "fixture://policyos-test/l5-identification-mode-overlay/sha256/"
            f"{overlay_hash}?source_ref={quote(original_ref, safe='')}"
        )
        fixture_refs.append(fixture_ref)
        return replace(
            authority,
            identification_modes=modes,
            identification_mode_registry_ref=fixture_ref,
        )
    ```

    This labels the derived input and links its source without claiming an
    owner-issued production artifact. The path assertion binds each module's
    loader call to the same file whose digest appears in the fixture-ref
    preimage; if a caller selects a different catalog path, the test fails
    before deriving the override.
  - Patch the two loader bindings listed above for the second build. Use the
    same `REPO_ROOT`; keep both workspace directories and CAS under `tmp_path`.
    The exact patch calls are:

    ```python
    monkeypatch.setattr(
        substrate_registry_module, "load_l5_catalog_authority", load_point_overlay
    )
    monkeypatch.setattr(
        data_state_substrate_module, "load_l5_catalog_authority", load_point_overlay
    )
    ```
  - Install a `shutil.copytree` guard that rejects sources resolving beneath
    `REPO_ROOT / "production_data"`, while allowing unrelated temporary copies.
    Use it before either build to catch restoration of the audited helper. This
    guard does not cover `copy2`, `copyfile`, direct writes, or imported helpers;
    the bounded no-write claim relies on the inspected call graph showing S1
    outputs and CAS under `tmp_path`, L4 on DuckDB `:memory:`, and source DuckDB
    handles read-only. Do not describe this guard as a general no-copy gate.

    ```python
    real_copytree = shutil.copytree
    production_data_root = (REPO_ROOT / "production_data").resolve()

    def guarded_copytree(src, dst, *args, **kwargs):
        source = Path(src).resolve()
        if source.is_relative_to(production_data_root):
            raise AssertionError("production_data_copy_forbidden")
        return real_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copytree", guarded_copytree)
    ```

  - Assert the first build succeeds with `proxy` status and nonzero width; the
    second succeeds with `point` status and zero width; the outputs differ; the
    second profile's family ref equals
    `f"{fixture_refs[-1]}#/household_distribution"`; and the production
    identification-registry digest is unchanged after both builds.
  - Verify the second build's persisted S0 registry, not only its S1 materialized
    state. Load it through the existing
    `substrate_registry_module.load_substrate_registry(store,
    point.substrate_registry_ref)` reader. Select the nonempty L5
    `household_distribution` entry set and assert every selected entry has
    `identification_mode == "point_identified"` and includes `fixture_refs[-1]`
    in `authority_refs`. Also select the matching entries from
    `point.world_model.record.substrate_registry_ref.resolved_entries` and
    assert the set is nonempty and point-identified. These S0 assertions detect
    omission of the `substrate_registry_module` binding even when the S1
    materialization still reaches point identification through the other
    binding. Keep the fixture reference described as a test label, not as
    owner-verified evidence.

No production source, generated family, governed artifact, plan, or register is
in this write set. No tests are run as part of this planning task.

## Implementation sequence and closure signal

1. Replace the helper/caller as specified, using `dataclasses.replace` on the
   real loader's typed result rather than serializing or copying owner files.
2. Keep the original production call and verify the two outcomes in the test:
   proxy remains non-refusing with a positive-width bound; the fixture override
   produces point identification with zero width.
3. Keep both loader-binding removal probes effective: omit or misroute the
   `data_state_substrate_module` binding and confirm the S1 point/zero-width
   assertions fail; separately omit or misroute the
   `substrate_registry_module` binding and confirm the persisted S0 household
   mode/provenance assertions fail while S1 may still be point-identified.
4. Keep the source-preservation control: the canonical identification-mode
   registry hash computed before the proxy build equals the hash after the point
   build. The production-copy guard fails if the former `copytree` call is
   restored. This guard covers that callsite/function only; use the audited
   read-only/in-memory/tmp-path call graph for the bounded no-write assessment.
5. After review, run the rewritten test with the linked production-data tree:

   ```bash
   cd policy-engine
   POLISYOS_PRODUCTION_DATA_ROOT=/Users/deniskopylov/polisyos/policy-engine/production_data \
     JAX_PLATFORMS=cpu .venv/bin/python -m pytest \
     tests/integration/runtime_quality/test_data_state_substrate.py::test_l5_proxy_identification_materializes_bounded_state_and_toggle_changes_it -q
   ```

   Then run that whole test file at the integration head. Do not run, overlay,
   or rewrite the four historical pinned test blobs: retain their four
   `UNRUN` cells in the original P41 baseline record because their exact
   same-command execution enters the production-data `copytree` helper. A safe
   post-repair integration-head run is a separate witness and cannot be recorded
   as one of those historical outcomes.

**Acceptance:** the real world-build consumer distinguishes proxy from point
through the typed L5 input; both S1 state and the persisted S0 household row
carry the point mode; the S0 row carries the test fixture authority reference;
and the second profile identifies the same fixture premise. The canonical
identification-mode registry file digest is unchanged. The test guard rejects
the former `shutil.copytree` source under D2. This is a bounded witness, not a
generic filesystem no-copy/no-write proof: its no-write conclusion depends on
the reviewed call graph routing outputs to `tmp_path` or memory and opening
source DuckDB/SKG data read-only. It does not establish file-resolution
behavior, verify the fixture URI as external evidence, hash all production
bytes, or prove that no write was attempted.
