# P41 D2 safe fixture implementation plan

> For agentic workers: implement this plan task by task; this plan is design
> guidance only and contains no test or product-code changes.

**Goal:** Keep the household proxy-to-point behavioral witness while preventing
any copy or write of appointed `production_data` bytes.

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

## Review focus

- If either module-level loader binding is unpatched, the second build stays proxy;
  the test must detect that.
- The override must change only `household_distribution`, leaving other loaded L5
  rows unchanged.
- The world output must identify the test fixture override as its mode source;
  it must not claim that production bytes select point identification.
- The source registry SHA-256 must be identical before and after both builds.
- The original whole-file test at the four pinned bases remains `UNRUN`: those
  historical blobs still call `copytree`. The rewrite enables safe execution of
  the rewritten test; it does not retroactively make the old blobs safe.

---

## Finding and source seams

The audited unsafe helper is
`policy-engine/tests/integration/runtime_quality/test_data_state_substrate.py`
@`ec7191b1713b09f2a312ea229cc1d538ebfe8306b1de2fe365e480b9211c7adf`.
`_repo_with_household_identification_mode` copies the D2 directory, edits one
registry file, and the sole caller is
`test_l5_proxy_identification_materializes_bounded_state_and_toggle_changes_it`.
The four-cell risk and source path are recorded in `P41_SAFETY_AUDIT.md`.

The canonical loader is
`policy-engine/src/polisyos/runtime/quality/substrate_registry.py`
@`6321750ec9641369e683c9a38795405c93dc5e4dc8d245e25c61f2cc199bbd5a`.
`SubstrateCatalogPaths` can choose file paths for `load_l5_catalog_authority`,
but no existing overlay type or in-memory override is exposed by the high-level
build. `build_l5_family_binding_profile` and
`build_substrate_registry_from_existing_catalogs` resolve default paths
internally. The materializer is
`policy-engine/src/polisyos/runtime/quality/data_state_substrate.py`
@`b29a8cab49c2a01312b27246cebc88829dbf1f0fa3e80f38bb13b76c0de80de4`.

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
  called inside `build_substrate_registry_from_existing_catalogs`.
- **P32 (trust by form):** the override is a test fixture, never evidence that
  the production registry selects point identification. Put a distinct
  `fixture://policyos-test/l5-identification-mode-overlay/sha256/` ref followed
  by 64 lowercase hex digits in
  `L5CatalogAuthority.identification_mode_registry_ref`.
- **P37/P38:** the test recomputes the production source digest and checks the
  materialized status/width. The mode override itself is test-supplied. The
  implementation tests downstream behavior of a loaded typed authority; it
  does not test a file edit flowing through source resolution. Keep that
  divergence explicit in the test docstring and this record.

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
  - Capture SHA-256 of
    `default_substrate_catalog_paths(REPO_ROOT).identification_mode_registry_path`
    using `hashlib.file_digest(stream, "sha256").hexdigest()` on a read-only
    binary stream.
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
    owner-issued production artifact.
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
    Use this guard before either build:

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

No production source, generated family, governed artifact, plan, or register is
in this write set. No tests are run as part of this planning task.

## Implementation sequence and closure signal

1. Replace the helper/caller as specified, using `dataclasses.replace` on the
   real loader's typed result rather than serializing or copying owner files.
2. Keep the original production call and verify the two outcomes in the test:
   proxy remains non-refusing with a positive-width bound; the fixture override
   produces point identification with zero width.
3. Keep the removal probe effective: omit or misroute the override while leaving
   assertions in place; the point-status / zero-width assertions must fail.
4. Keep the source-preservation control: the registry hash computed before the
   proxy build equals the hash after the point build. The production-copy guard
   fails if the former `copytree` call is restored.
5. After review, run the rewritten test with the linked production-data tree:

   ```bash
   cd policy-engine
   POLISYOS_PRODUCTION_DATA_ROOT=/Users/deniskopylov/polisyos/policy-engine/production_data \
     JAX_PLATFORMS=cpu .venv/bin/python -m pytest \
     tests/integration/runtime_quality/test_data_state_substrate.py::test_l5_proxy_identification_materializes_bounded_state_and_toggle_changes_it -q
   ```

   Then run that whole test file at the integration head. Do not replay the four
   old `test_data_state_substrate.py` blobs; retain their four `UNRUN` cells in
   the P41 baseline record. The test can be added to a later safe baseline only
   once each pinned test tree contains the rewritten source.

**Acceptance:** the real world-build consumer still distinguishes proxy from
point through a typed L5 input; the fixture ref makes the test-only premise
visible; the production identification-registry file digest is unchanged; and
no copy operation may start from the production D2 tree through
`shutil.copytree`. The audit found no other direct file-copy call in this
fixture; that bounded scan does not rule out dynamically assembled copies from
imported helpers.
