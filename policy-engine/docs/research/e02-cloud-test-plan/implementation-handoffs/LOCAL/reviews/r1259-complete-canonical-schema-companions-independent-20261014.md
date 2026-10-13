# R1259 — Independent review of canonical schema companions

Verdict: **GO for the exact R1258 Source33 composition to proceed to the root-owned commit and native Source33 wave.** The generated companion set is complete against the current full active registry, its retained unfiltered check passes, and the current composed bytes match their frozen postimages. This is not a closure of filtered-generation behavior, runtime integration, or the open ABM version/publication decision.

## Bound inputs

- Worktree: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`
- HEAD: `51f1db1a47d17c6ee3ccedbdf3f2cc85eb8d4960`; tree: `5a4d54dcfdb37d2b47373326d1747de8d7014082`
- Current source frame: `LOCAL/root-author-source-frame-r1258-20261014.json@e3632db76cb3441f9c594accf74c330bd0b84cf6e2707babab098b5b61b007a3` (590 postimage entries)
- Composition: `LOCAL/raw/r1258-source33-with-complete-canonical-generated-companions-20261014/composition.json@7654d7a2a6f6d8602275063718385f34fa6bf19ed51bf0e2bfb3ea5e2742d0ac`
- Composition patch: `LOCAL/raw/r1258-source33-with-complete-canonical-generated-companions-20261014/net.patch@b04ba314df9e38603a501740a9fe857045c87662f1770d072c5dd49c56f4f633`

I verified all 33 composition postimages against current disk: 33/33 match. The 31 existing paths also match their declared HEAD preimages; the two new companion paths are correctly marked as absent preimages. The composition records 11 generated companions and says the reviewed Source22 postimages are unchanged. I made no product, index, history, or generator writes.

## Registry and generated outputs

The complete current manifests contain 106 active entries and 106 unique schema filenames: IR 103, Fabric 2, Scientist 1. A read-only standard-library walk recomputed each module manifest content hash and the full and semantic hash for every referenced schema; all three manifest hashes and all 106 full/semantic schema hashes matched. All entries are lifecycle `active`, and the current manifests contain no duplicate FQNs or schema files.

| Generated companion | Current postimage SHA-256 |
| --- | --- |
| `policy-engine/docs/reference/ir/schema-catalog.md` | `d4a1755e66a4482d57c73711483f540e7eb90b9a952074b50b9191b9f62bc090` |
| `policy-engine/docs/reference/schemas.md` | `6efbb868cd9a8e8c865fe1ee63aec56c938b060a3d3dbbe9e1eaa96421d7725b` |
| `policy-engine/schemas/snapshots/fabric/_manifest.json` | `2b1947a59b8b944953258a1e614318454b6c26a03e5f0486cd44b9c4d7fd9fc6` |
| `policy-engine/schemas/snapshots/ir/_manifest.json` | `d304496ecef5ff93ef7082416f98329e115fa2e123fe03375b4240c302adbf57` |
| `policy-engine/schemas/snapshots/ir/abm_result.schema.json` | `828205167f4e6f38d6c50c69252bc71e1e064466b53f2417ec1325eceffcebdb` |
| `policy-engine/schemas/snapshots/ir/backtest_plan_bundle.schema.json` | `4ce167b5a2dd40f20e9853f9542d4bd61c8255ca2a5929f5cb1d7285497ab2cc` |
| `policy-engine/schemas/snapshots/ir/backtest_report.schema.json` | `2eca8f866b86ce360723f99ae9865150ae96a9c87936e0168ee4505b6be417a1` |
| `policy-engine/schemas/snapshots/ir/causal_discovery_report.schema.json` | `bad34944660ef3f805430e20750e818bacc3160fceb3f0465384ebd30e3afda3` |
| `policy-engine/schemas/snapshots/ir/causal_effect_report.schema.json` | `97c135d278a1ec77f0f6c105f30157ec065c3bd850f375fc499b127fa8638ddd` |
| `policy-engine/schemas/snapshots/ir/structural_causal_model_spec.schema.json` | `3f8820a3504650b9f30711d924600691218dbc67e1f1e6367a8c3989166ab9e3` |
| `policy-engine/schemas/snapshots/ir/transportability_result.schema.json` | `fb32154134b7877baa61a28d92e33883b45acdb97e3fcdd5a89c6b17ffa0b9c7` |

The generated ABMResult schema contains the typed optional `execution_input_basis_ref` and `execution_source_status` enum, while retaining the existing required references and other properties. Its manifest records schema version 1.3. The generated docs and snapshots therefore reflect the current typed source fields without choosing a new version namespace.

## Deciding receipts

The retained canonical full generation used no selector: `.venv/bin/python -B -m tools.quality.diagnostics.gen_schema`. Receipt `LOCAL/raw/r1256-actual-full-canonical-schema-generation-20261014/command.json@d8c6c8718003a3e3199a42f1f33877e05872b67161c4bfbb1bc75f113def2abd` binds it to source frame `LOCAL/root-author-source-frame-r1251-20261013.json@67042261b1e1ec3af938fdd402c76dafa511b1f49123541bdc5593a7dab3defa`, HEAD 51f1db1. Exit 0, 7.3287 seconds, stdout `Generated ABI schema snapshots for 106 models (10 file updates, scan_mode=full)` with SHA-256 `3ab1e636dd55fcba7a636a139b70a8cf4a69fb099305512893eeadf8f5e4d989`; stderr was empty.

The retained unfiltered canonical check was `.venv/bin/python -B -m tools.quality.diagnostics.gen_schema --check`. Receipt `LOCAL/raw/r1257-actual-full-canonical-schema-check-20261014/command.json@f23094eb2bf03b1118217855ce430a208a20f48ec1f6a1397d7bba8917e9363e` records exit 0 in 5.8478 seconds; stdout `ABI schema snapshot check passed (106 models, scan_mode=full)` has SHA-256 `14cd269d316d6479a0392575980b5bb96fb494f5d672e927d7f51205bd50d7c4`; stderr was empty.

The retained P29 removal control, `LOCAL/raw/r1260-full-schema-corrupt-field-drift-control-20261014/control.json@ddac6971a9de6c3900009001249a739263c540ee4e31f625850343022d3a5574`, uses a copied output tree with 112 symlinks to canonical snapshot files and one changed ABMResult copy. The only JSON difference removes `single_step_basis` from the `execution_source_status` enum while leaving the field and other markers intact. The actual unfiltered `--check` exits 1 with exactly one `snapshot out of date` error for that copied ABMResult file; output SHA-256 `8f9f7bde47d583ee305964a3088582ecda8b999068004d6634a3323ac205ae09`, stderr empty. The control detects the semantic schema drift rather than merely checking marker presence.

The actual Source33 Ruff receipt is `LOCAL/raw/r1261-actual-source33-ruff-check-and-format-20261014/receipt.json@506d51a555648dc1d2d79680c96094c6c0fd37847af7ca7daf4c422ceff9230c`: 17 Python paths, `ruff check` exit 0 (`All checks passed!`) and `ruff format --check` exit 0 (`17 files already formatted`). This review did not rerun generation, tests, or native suites.

## Separate filtered-mode finding and limits

The filtered path remains a separate tooling defect. R1250 ran `gen_schema --models abm_result`, exited 0, and reported one model and two file updates. R1252 ran the same selector with `--check`, exited 1, and reported 102 unselected registered IR snapshots as “unexpected snapshot file”; its complete retained stdout is `LOCAL/raw/r1252-actual-abm-schema-canonical-check-20261013/stdout.txt@9694ca03868063b021d9c6c8f5af78dc8461862f61bb28b5ccd9d444ff379866`. The generator builds each module manifest from the selected entries, while the check compares the selected file set against all files in that module. This is a **new P40 tooling class**: filtered operations are not isolated from the shared module-wide manifest and snapshot set. The current full regeneration and full check restore and verify the full registry, but they do not close this filtered route; R1254 remains separate. This is not an inherited-red claim under P41.

This GO covers the exact R1258 composed bytes and permission to proceed with the root-owned Source33 native wave. It does not claim runtime producer-to-CAS-to-reader behavior, generated-client compatibility, wheel/sdist behavior, scientific validity, a release decision, or formal closure. R1237 remains an author proposal with the Core payload, IR ABMResult, and outer CAS version coordinates unresolved; the release fragment preserves that limitation and marks generated-client compatibility as requiring regeneration. G publication/version adjudication remains open. `closure_ids=[]`.

Pattern pass: P29 drift is exercised by the remove-field-keep-markers control; P35’s 106-model count is derived from the complete active registry/manifests rather than a sample; P39’s docs, manifests, release fragment, and decision are companions to the mechanism; P40 classifies filtered shared-manifest behavior separately; P41 does not carry a prior red as inherited. The canonical registry owners read for this review were `policy-engine/src/polisyos/schemas/abi_models.py@8c43d8085ee94fae96d7c560bb05b2e7b7b84a6f9fca64fd60bf32b46e0d153f` and `policy-engine/tools/quality/diagnostics/gen_schema.py@39a833a5259d47e46384c93f1a11464b850e85c3e26457040725ab927191205c`.
