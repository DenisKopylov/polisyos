# DFI installed resource/profile review

Review scope: read-only source, profile, package-content and existing probe-output review at DFI worktree `ab44166335130463178e65dfc29a252c96afe479` (`codex/e02-C-dfi-emb-20261006`). No source edits, installs, tests, or builds were performed for this review.

## Verdict

The failing isolated-wheel run is **not a qualified package-plus-workspace setup** and does not establish a DFI-041 failure. DFI-041's own scope is the source-tree catalog batch checkpoint/resume behavior in `batch/checkpoints.py` and `batch/pipeline.py`; its acceptance matrix concerns state/input/output integrity, legacy/malformed state, rule/config changes and skip/rerun decisions. It does not specify a non-editable wheel execution profile.

The observed install-only result is therefore **not_established as a supported DFI runtime profile**, not a pass. Keep it out of the DFI-041 acceptance result. There is nevertheless a concrete packaging/resource integration gap if non-editable-wheel callers are expected to use the exported default seed-alignment helper or core-source producer: the public default resolver depends on a checkout-shaped ancestor path, but the declared wheel and sdist omit the canonical registry and the docs specify no staging/resolution contract. If wheel use is intended for those consumers, that is a real missing-resource bug to address separately with the Data Forge owner. The evidence here does not establish that support commitment.

## Resource owner and path behavior

The sole committed owner is `policy-engine/data/dataset_catalog/seed_variable_alignments.yaml`, owned by `team-data-forge` under `dataset_catalog_registry` / `committed_registry` in `architecture/policies/data.toml`. Its SHA-256 is `cb1daa3237ff58d8c875571ff2459a55c5182c3a4f13a076497a517f9a8740d8`.

At `src/polisyos/data_forge/domains/catalog/knowledge/variable_alignment.py:58-66`, `default_seed_alignments_path()` takes `Path(__file__).resolve().parents[6]`; in source that resolves to product root `policy-engine`. At `src/polisyos/data_forge/domains/catalog/batch/core_sources/loaders.py:272-280`, `_seed_alignments_path()` uses parents[7], also resolving to product root in source. From the installed module locations, those same indices resolve to the interpreter's `lib/python3.14` directory, so the installed code expects `<venv>/lib/python3.14/data/dataset_catalog/seed_variable_alignments.yaml`. It does not resolve from the working directory or accept a workspace root. The core-source API calls this resolver during ingest (`core_sources/api.py:463,470-471`), before its source-observation transport path.

The product/package boundary makes this relevant beyond internal implementation: `architecture/packages/data_forge.toml` names `polisyos.data_forge.read_api` as the sole runtime import surface, and `read_api/catalog.py` re-exports `default_seed_alignments_path`, `load_seed_alignments`, and `score_variable_pair`. The latter defaults to this path when seed alignments and an explicit path are both absent (`variable_alignment.py:461`).

## Profile and package contract

The supported onboarding material describes checkout/workspace profiles: runtime and research via workspace bootstrap / `uv sync`; the manual install in `docs/how-to/install.md` is explicitly `pip install -e "."`. No documented profile installs a non-editable wheel and stages data under the Python interpreter's `lib/pythonX.Y/data` directory.

Packaging config `hatch.toml` declares wheel packages `src/polisyos` and `tools`, and the sdist include set does not include `data/`. The existing packaging contract test, `tests/repo_quality/tools/test_hatch_packaging.py`, preserves that complete member contract. Inspection of the exact candidate artifacts confirms neither `policy_engine-0.1.0-py3-none-any.whl` nor `policy_engine-0.1.0.tar.gz` contains `seed_variable_alignments.yaml`. Thus the canonical resource is deliberately repository product data, not wheel payload.

## Divergent installed-only case and qualification limit

The isolated probe at `.tmp/e02-C2/raw/installed/dfi-ab441/main-runtime-output/probe.stdout` records `python -I`, `PYTHONPATH=null`, cwd at the original repository root, and site-packages-only import origins. The actual installed modules equal their wheel and frozen-source bytes, but producer execution raises `FileNotFoundError` for `.../venv-vector-search/lib/python3.14/data/dataset_catalog/seed_variable_alignments.yaml`; the transport call delta is zero. The stdout SHA-256 is `748b1219fc79ad65cf7cf8d6b6b4a69c1ae2c465340f515fb49206dc017f19e`.

A paired control stages the exact canonical resource bytes at that computed interpreter path. Its staged file SHA matches the tracked file. The core-source stage then completes with one observed row, a current output receipt, and one recorded World Bank request; the complete pipeline still returns a separate fixture/readiness QC failure, so this is not a whole-pipeline green. This control shows the missing path is causal; it does **not** qualify the staging convention, because the staged path is under the venv's Python library root, not the repository workspace, and no documented install step creates it. The control stdout SHA-256 is `5c64c1f63d6905f0d3b5bb405e817365140006e9364cc5859538a9626ea8b116`.

The supported qualification for DFI-041 remains a checkout/workspace execution (including the documented editable install from `policy-engine`) where the module path makes its ancestor resolver land on the canonical product-data root. An ordinary wheel installed into a venv beside a checkout is still not qualified: cwd alone cannot fix the module-relative resolver. Treat any future standalone-wheel claim as requiring an explicit owner-supported data locator or a deliberate packaged-resource contract, plus a real installed consumer test.

## Evidence identities

- DFI candidate: `ab44166335130463178e65dfc29a252c96afe479`.
- Wheel SHA-256: `68c77ca5b91a30e98a8a21c4e651ade143724ed3a8c83e9961512ea4469c78d6`.
- Resolver sources: `variable_alignment.py` SHA-256 `6dbfbb04cddff8d1af11ed226e68092a2763a8d007b73f911f4ed9eaa5e54cd9`; `core_sources/loaders.py` SHA-256 `21df92502db9ad60ab40da24a0ab93ab027ad2c5b8841b908f03582dbedcb640`.
- Install docs: `docs/how-to/install.md` SHA-256 `c74c89a4996910aa5dce9fb166892c5461adb2ac26e21d36faa933c9dc185252`; dependency profiles SHA-256 `2c45e8783744d00830875d6ef8eff92af36d83c8483e140159321bad308bda85`.
- Package/data contracts: `hatch.toml` SHA-256 `065c99c71b69bceac54e7d0083b7f261796f0733a4b721d1e6267fd6e28098a5`; `architecture/policies/data.toml` SHA-256 `8060a633c88097cc32e573d2a7e24357b28362738556c00e3f762f0f4fe8fd63`; `architecture/packages/data_forge.toml` SHA-256 `dd17ff392e2d1ebe8126428234c8b06cba006d0f5332a8eb86161fdc5464206d`.
- DFI-041 original card: archived `source/LA_r09_original.md`, SHA-256 `2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727`; bundle acceptance is also summarized at `docs/research/e02-cloud-test-plan/bundle-catalog.md:1106-1130`.

## Scope conclusion

For DFI-041, classify the installed-only failure as **outside the card's source-workspace acceptance / package-profile support not_established**. Do not call the ad-hoc staged-resource control a supported wheel+workspace qualification. Record the resolver-versus-public-read-API packaging gap separately; if non-editable wheel execution is intended, the current design lacks its resource handoff contract and installed-runtime behavior is broken.
