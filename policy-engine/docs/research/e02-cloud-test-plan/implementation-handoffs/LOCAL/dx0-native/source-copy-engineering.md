# Native freshness source-copy engineering record

Current status (2026-10-10): `LOCAL/raw/native-freshness-source-copy.patch` is an apply-ready unified diff against the four pinned source files below. It remains unapplied; no product tests or native freshness rows were run. A Python AST parse and unified-diff reconstruction from the pinned files passed. The prior design prose was preserved verbatim at `LOCAL/dx0-native/source-copy-proposal-design-20261010.md@0c8822e2f2c9bf069076ab46b856283675ec039f340e103510a1448d8f216c46` before the `.patch` path was replaced.

Current patch: `LOCAL/raw/native-freshness-source-copy.patch@45535b728a5f08d2e3efcd8eb9041f91b473b6fb0f5397616838acd6c7733348` (49,277 bytes). The product source files remain at their pinned hashes; this work wrote only the patch artifact and this local engineering note.

The diff changes these four paths:

- `tools/devx/architecture/guardrails.py`: parses and reports family input selectors; requires an explicit basis; copies the full filesystem roots, including ignored/untracked source; checks the tracked and exact required paths; rejects path escapes, symlinks, special files, and insufficient space before destination creation; derives exact local-only roots from `architecture/policies/directory_contracts.toml`; recognizes Python environments by `pyvenv.cfg` plus an interpreter and Hugging Face caches by `blobs/refs/snapshots`; preserves only registered Node package-manager links and checks the installed pnpm lock and manager metadata against root declarations; reconciles trust-compiler explicit reads through `measure_file_reads()`; maps or rejects `POLISYOS_GOVERNED_ARTIFACT_ROOT` before environment provisioning.
- `architecture/generated_artifacts.toml`: declares full roots and exact required source/config/lock/resource paths for the four currently selected families. The frontend families declare only the three existing package-manager dependency-link locations.
- `tools/quality/validation/check_trust_claim_posture.py`: passes its selected family basis to the shared copier and maps the governed-artifact root into the copied tree.
- `tests/repo_quality/tools/test_architecture_phase3.py`: adds a real child read whose output changes with ignored source bytes; required and tracked removal controls; exact local-root versus same-name nested-source controls; structural environment/Hugging Face controls; missing/mismatched pnpm install receipt; symlink/FIFO/disk controls; and unset/mapped/refused governed-root environment controls.

The selector is driven by manifest fields rather than a second hard-coded four-family ID set. Its property is that a child receives every filesystem entry under its selected family roots plus every exact required member, while owner-declared local-only roots and typed runtime dependency links remain separate. The prior Git-visible list/basename filter diverged on an ignored `.py` under `src/`, which the trust compiler enumerates with `src.rglob("*.py")`; the copied-child test reads that file and observes changed output after its bytes change. `P40` is `SAME_CLASS_DEEPER`: one source-basis/copy mechanism is widened, not a per-path exception.

The trust read collector observes explicit file-reader calls, not Python imports, subprocess reads, Git, or services. The family filesystem roots and exact required paths cover the known current source set, but the diff does not add a copied-content digest receipt or an OS-level read sandbox. It maps/refuses `POLISYOS_GOVERNED_ARTIFACT_ROOT`; other ambient environment configuration is not comprehensively audited here. Arbitrary absolute reads and those unreviewed settings remain `not_established`, not green. The current rows remain `UNRUN` until root review and the final native wave.

## Historical proposal and evidence

The rest of this note records the original investigation and source evidence. Its “Required patch shape” section is superseded by the apply-ready diff above; the preserved proposal file is the verbatim artifact for that earlier design.

## Finding and class

This is `P40 SAME_CLASS_DEEPER`: the earlier caller-root defect was one resolver path; the current defect is deeper in the same freshness mechanism because the isolated source selector can omit admitted inputs or permit a generator to read outside the clone. The previous patch is superseded. It used Git tracked plus nonignored-untracked paths, which is not the full selector used by the trust posture compiler, and it treated some unsafe untracked symlinks as exclusions. The latest independent review also found that `_isolated_probe_environment()` inherits `POLISYOS_GOVERNED_ARTIFACT_ROOT`.

The property is: each native family consumes the complete, current, admitted source/config/resource/lock basis in the isolated source tree, and required external inputs either map to an admitted copy or make the row `UNRUN` before environment provisioning. The previous stand-in was a Git-visible path list plus basename exclusions. A divergent case is an ignored untracked Python module below `src/`: the canonical trust scanner discovers it through filesystem `src.rglob("*.py")`, while `iter_repository_files()` expressly returns tracked paths only and `git ls-files --others --exclude-standard` excludes it. Another divergent case is a host `POLISYOS_GOVERNED_ARTIFACT_ROOT` pointing outside the copy; the copied Python code can still resolve that path. A third is a selected file reached through an external parent symlink. These are `P38` boundaries; path count and output equality alone do not establish the actual input property.

## Reconciled source and consumer evidence

The trust posture command at `tools/quality/validation/check_trust_claim_posture.py:3629` wraps `compile_claim_posture_register()` in `measure_file_reads()`. `derive_token_sources()` at lines 277–345 resolves `repo/src`, enumerates the complete filesystem set with `rglob("*.py")`, records its candidate count, and reads admitted source files through `admitted_read_bytes()`. `derive_page_a11y_receipt()` at lines 867–950 requires and reads exactly five receipt members. `CUSTODY_APPOINTMENT_SOURCE_PATH` resolves to `docs/plans/active/DEBT-REGISTER.md`; this tracked required input is 961,811 bytes at this checkout. The earlier proposal named the receipt but omitted the debt register as a required input. The register’s tracked status does not replace an explicit required-input assertion and post-copy byte check.

The current four default families are `runtime-openapi-snapshot`, `runtime-api-client`, `runtime-dashboard-api-types`, and `trust-claim-posture-register` in `architecture/generated_artifacts.toml:728–870, 2183–2226`. The manifest’s `source_of_truth` prose is not a selector. Current consumers require:

- OpenAPI: the full filesystem `src/` and `tools/` roots (runtime import/dependency closure and exporter), Python project configuration and lock, family manifest, and source/resource files in those roots.
- Runtime client and dashboard types: each package’s full source/config root, `schemas/runtime_api_v1.openapi.json`, and root package/workspace/lock configuration. The existing three `node_modules` links are a typed dependency exception that requires the current frozen pnpm install/lock receipt.
- Trust posture: the compiler’s actual read receipt plus full filesystem `src/` and `tools/` roots for dynamic Python/import inputs; the identity boundary, accessibility audit, generated-artifact manifest, debt register, and all five DS11 receipt files. The receipt path is `docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base/` with `environment-after.json`, `environment-before.json`, `receipt.json`, `run-1/.last-run.json`, and `run-1/results.json`.

The existing read collector is useful but bounded by its own contract: it measures explicit file-reader operations, not Python imports, subprocess reads, Git or services. The trust compiler receipt must be used to derive actual explicit inputs, then reconciled with the full `src/` root and family source roots. It cannot by itself certify every process read. This report does not claim a complete native read denominator or a green native row.

## Required patch shape

The old inventory helper is not sufficient. The new mechanism should take the required family tuple and produce one source admission receipt containing each selected path, content digest, mode/link target, and provenance class (`tracked`, `visible_untracked`, `family_root_filesystem`, `compiler_read`, or `required_family_input`). It should be built from:

1. `iter_repository_files()` for the committed denominator, retaining absent tracked entries so an absent tracked input fails before copying.
2. The same tracked + nonignored-untracked worktree universe used by `_snapshot_git_visible_worktree()`.
3. A filesystem walk of typed `probe_input_roots` from the selected families, which deliberately includes ignored-untracked source/config/resources under those real roots. At minimum the current Python families need full `src/` and `tools/`; frontend families need their package roots; the trust family additionally binds the required posture documents/receipt members. Do not use `LOCAL`, `raw`, file-extension, or broad `docs` exclusions.
4. The trust owner compiler’s actual `measure_file_reads()` input receipt as a second source for required explicit reads. Every successful read must resolve beneath the product root and appear in the selected copy; unreadable/absent required members make the family `UNRUN`.

Make the family root/file selectors machine-readable in the generated-artifact family contract and validate them. The four current records need typed `probe_input_roots` plus exact `probe_required_paths`; retain the human `source_of_truth` prose as descriptive text only. The runtime client and dashboard records must carry their own package roots and OpenAPI/lock/config inputs. Tests should derive the current family set from the manifest, not duplicate a separate hard-coded list in the selector.

Use typed local-state/config policy for exclusions, not directory basenames. `.polisyos` and local production/data roots come from their existing owner contracts; Python environments require the `pyvenv.cfg` plus interpreter structure; a Hugging Face cache requires its `blobs/refs/snapshots` structure; Node dependency links are only the existing three registered package-manager roots. Preserve source/config/resource files even when Git ignores them if they are under an admitted family root. A special file inside a selected family root is a failed admission; it is not silently skipped. A FIFO outside a family root is outside the selector, but a tracked or required FIFO must make the copy `UNRUN`. Do not classify a folder named `venv` or `models--*` as a cache without its structural evidence.

Validate every selected path and each ancestor before reading or copying. For ordinary source paths, resolved targets must remain under the admitted repository root; an escaping parent symlink, broken symlink, or unsafe untracked symlink makes the family `UNRUN`. Internal symlinks may be preserved only when their resolved target is also selected and copied. The three package-manager links are an explicit exception with provenance and the frozen lock/install receipt.

For `POLISYOS_GOVERNED_ARTIFACT_ROOT`, build the child environment from an allowlist. If unset, remove the inherited variable so the normal `__file__` fallback resolves inside the clone. If set to a path contained in the product root and selected by the family basis, rewrite it to the same relative path under the clone. If outside the root, excluded as local data, absent, or not selected, return an environment `UNRUN` before `uv venv`/`uv sync`. Do not copy external production data to make the check green. Apply the same mapping/refusal rule to every path-valued host setting that a current output probe consumes; unknown external dependencies remain `UNRUN`.

`_copy_isolated_probe_source()` is called both by the architecture freshness runner and `run_generated_family_output_probe()`. Both callers must pass the selected family basis. Preserve the disk preflight, but estimate and report the complete selected regular-file bytes and excluded typed-local bytes before creating the destination. Verify copied content digests, symlink targets, and all required paths after copy. Do not claim the selection manifest digest proves file contents unless it actually binds each content hash.

## Behavioral falsifiers required in the patch

The focused mirror should use a real copied child that opens the selected bytes and emits a result derived from them. It should include an ignored-untracked `.py` under `src/` that the real filesystem source selector enumerates, plus ignored source/config/resource files under each declared family root; no `git add -f` shortcut. The result must change when the copied source is changed, and removal of a selected source must produce `UNRUN` rather than a partial green.

The trust-family fixture should include the debt register and all five DS11 receipt files as actual reads. Remove each required file in turn and prove admission fails before child execution. Include an untracked ignored source module containing a relevant field and prove the canonical compiler read receipt and child output change when it is removed or edited.

Containment controls should exercise an external symlink in an ancestor, an unsafe untracked symlink, an internal symlink whose target is not admitted, and a FIFO within a declared root. All must fail closed. The environment control should prove: (a) no inherited governed root is present when unset, (b) a contained selected root maps into the cloned copy, and (c) an outside or excluded governed root produces an environment `UNRUN` before environment provisioning. Keep a positive typed `node_modules` link control tied to the package lock/install receipt. Keep structural cache controls for a genuine venv and genuine HF cache, and a same-name non-cache source control.

The preflight deletion/corrupt-source control must remove a property while retaining family/selector markers and prove the actual child output or compiler failure changes. Assertions that merely inspect metadata fields or prove files were copied are insufficient (`P29`).

## P40/P41 and remaining decision

This is the second finding in the source-copy/input-basis class, so the patch widens the whole selector, environment, and containment mechanism rather than adding another path-specific exception. The target is one reusable basis builder over actual family contracts and canonical owner readers. P41 is not inherited: no exact-slice-base replay with a complete zero-intersection proof was performed here.

One bounded question remains for the root decision: the existing `measure_file_reads()` explicitly does not observe imports or arbitrary subprocess reads, and this repository has no cross-platform filesystem sandbox in this mechanism. The preferred current-family repair is the typed full-root basis above, the actual trust compiler receipt, a scrubbed environment, and refusal of every unadmitted path-valued setting. That is enough to close the known current inputs only after the real four-family children pass and their required read roots reconcile. If the acceptance bar includes proving that arbitrary child code cannot directly read an absolute external path, the current mechanism cannot prove that; the smallest added capability is a supported OS-level sandbox with the copied source and explicit package dependency roots as the only read mounts. Until that distinction is decided and the native child evidence exists, unknown external reads stay `UNRUN`; do not record a partial clone as native green.

No expiry, authority, family semantics, or waiver changes are proposed. No source/test/generator/native command was executed for this proposal.

## Patch/source custody

Proposal patch: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-freshness-source-copy.patch`.

Pinned source hashes at this checkout:

- `tools/devx/architecture/guardrails.py@5d30de37ed02c5e346458e62e00b2772e7ba0eed501cf8282f72d3058bf9b4f6`
- `tests/repo_quality/tools/test_architecture_phase3.py@6cbdbe384c2ea300ffdfed7bdd460fa2a696e5ea22179cf6135db64d9d4a61d2`
- `architecture/generated_artifacts.toml@0a79005a1d37c38ea759509215205284698b4bb12ecabb42c29e70196486eb6a`
- `tools/lib/fs.py@d0ec5e12b7762027051614290cf4e21b09dc3602e371a040f9d7ffcd38a8193`
- `tools/quality/validation/check_trust_claim_posture.py@3cc47926a168f903a0dd6921eaa131b2d335ef850e8586e7cfbf2ae5837a5ac5`
- `src/polisyos/scientist/evidence/claims/posture.py@d5608ca790e70ba637dee4cb57f6ca473661cef852ff33d0fba07cf68f31731a`
- `pyproject.toml@b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267`
- `uv.lock@e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463`
- `pnpm-lock.yaml@436723e8090a442f7ecb2d544ddac5ac2ee2c8a9680f64ef28d3444da2f4161e`
- `docs/plans/active/DEBT-REGISTER.md@133bf46f5835a73e117bcfde31edd87b98a5514c364a23b74926278c9f883f6e`
