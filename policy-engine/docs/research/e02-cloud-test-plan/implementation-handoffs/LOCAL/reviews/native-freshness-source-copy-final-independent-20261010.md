# Independent delta review: native freshness source copy

## Decision

**GO to apply for focused author iteration and regenerate the rendered reference; NO-GO to freeze this patch as complete or use it to claim native source isolation/currentness.** The parent reports `git apply --check` succeeds. I did not apply it, run tests, invoke a generator, run the native wave, or mutate Git. The four source preimages still match the patch pins exactly.

The patch closes the prior concrete `POLISYOS_GOVERNED_ARTIFACT_ROOT` escape and fixes the tracked-only source selector for ignored files under declared roots. It also adds useful fail-closed controls. Three source-basis defects remain: directory traversal errors can disappear silently; structural cache exclusions diverge from the trust compiler’s actual `src/**/*.py` selector; and the package-manager exception validates lock metadata without binding each linked runtime target/content. These are same-class, deeper input-boundary escapes, not new classes. The patch’s explicit `not_established` limit for arbitrary ambient/absolute reads is correct and must remain; ordinary copying does not enforce an OS read sandbox.

## Patch and source identity

- Patch: `LOCAL/raw/native-freshness-source-copy.patch`, SHA-256 `45535b728a5f08d2e3efcd8eb9041f91b473b6fb0f5397616838acd6c7733348`, 49,277 bytes.
- Author note: `LOCAL/dx0-native/source-copy-engineering.md@19062cea1785b2c79572b23a7f21ca05b35c186dea97ccb220cca61f4a291293`.
- Prior independent review: `LOCAL/reviews/native-freshness-source-copy-independent-20261010.md@d24ac6c777c556dcc20c76e19e0ae6cdb367e15acb0e0a7235e0e41e500d5d71`.
- All four actual preimage hashes match the pins: `tools/devx/architecture/guardrails.py@5d30de37ed02c5e346458e62e00b2772e7ba0eed501cf8282f72d3058bf9b4f6`; `tests/repo_quality/tools/test_architecture_phase3.py@6cbdbe384c2ea300ffdfed7bdd460fa2a696e5ea22179cf6135db64d9d4a61d2`; `architecture/generated_artifacts.toml@0a79005a1d37c38ea759509215205284698b4bb12ecabb42c29e70196486eb6a`; `tools/quality/validation/check_trust_claim_posture.py@3cc47926a168f903a0dd6921eaa131b2d335ef850e8586e7cfbf2ae5837a5ac5`.
- Root reports an apply-check pass and a 110-family manifest with four current default output-probe families; the patch adds selectors to those four. This review did not run either command.

## Current family basis inspected

The four declared bases are coherent starting points for their current source families:

- OpenAPI: roots `src`, `tools`, `architecture`, `schemas`; exact requirements include `pyproject.toml`, `uv.lock`, the family manifest, directory contract, and current OpenAPI snapshot.
- Runtime client: roots `packages/runtime-api-client`, `tools`, `architecture`, `schemas`; exact root package/workspace/lock, Python lock/config, directory contract, and OpenAPI snapshot; runtime paths are root and package `node_modules`.
- Dashboard types: adds `apps/runtime-dashboard` to the client roots and declares the third dashboard `node_modules` path.
- Trust posture: roots `src`, `tools`, `architecture`, and the trust feature source; exact identity, accessibility, debt-register, generated-manifest, and five DS11 receipt inputs. The producer’s `measure_file_reads()` receipt adds successful byte/text reads.

The trust producer’s current source rule is broader than Git: `trust_claim_posture_sources.walk_source_files` walks `src.rglob("*.py")`, reads contained regular files, and excludes `__pycache__`; the token producer also walks `src/**/*.py`. The explicit roots plus required docs cover the known source locations, including the formerly omitted `docs/plans/active/DEBT-REGISTER.md`. The read receipt only promotes successful `read_bytes`/`read_text` operations; it does not reconcile `is_file`, `is_dir`, `rglob`, or other recorded operations. Current known paths appear covered by the broad roots and exact requirements, but the copy has not been compared with a real producer receipt from inside the clone.

The family root and required-path tuples are parsed as absolute paths anchored at `REPO_ROOT`, matching the new absolute membership checks in the patch. I found no relative/absolute mismatch there. `uv.toml` is omitted from explicit required inputs; its current sole setting is `cache-dir = "_cache/uv"`, while the probe sets `UV_CACHE_DIR` to the retained external cache. Its omission is not a demonstrated output divergence under that override.

## Blocking property gaps

1. **Filesystem enumeration is not fail-closed.** The new copy walks each selected root with `os.walk(..., followlinks=False)` and no `onerror` handler. Python’s default walk behavior ignores directory-scanning errors when `onerror` is unset. An unreadable untracked descendant under an admitted root can therefore be omitted without a typed `UNRUN`; a successful child may then run on a partial basis. The tracked-file pass does not cover an ignored, untracked file inside such a directory. Require every scan error to abort admission and add a behavioral control with a denied/erroring subtree.

2. **The cache filter contradicts the trust producer’s source selector.** Before copying, the patch excludes any structurally detected Python environment or Hugging Face cache encountered under a selected root. But the canonical trust producer includes every contained `src/**/*.py` except `__pycache__`; it has no corresponding venv/HF exclusion. A `.py` file under a structurally valid environment/cache inside `src` can affect the live trust output while the isolated copy drops it. The new venv/HF tests assert the drop but do not execute the trust producer or prove that dropped members are irrelevant. Remove those exclusions for source roots whose consumer selects them, or reconcile the consumer selector and its tests under the owning contract before claiming complete basis.

3. **The pnpm exception validates a path and lock receipt, not the linked input target/content.** The patch accepts a runtime path when it is one of three names and `is_dir()`; it does not bind `resolve()` of each package-level runtime path to the root pnpm installation. A package `node_modules` symlink to an unrelated directory still passes the path check, and the copy then links that external directory into the child. The lock check verifies `packageManager`, `.modules.yaml`, and byte-equality of `node_modules/.pnpm/lock.yaml` to `pnpm-lock.yaml`; it does not content-bind installed package files. I independently read the current receipt: `packageManager = pnpm@10.33.2`, installed manager matches, and both lock files are 482,583 bytes with SHA-256 `436723e8090a442f7ecb2d544ddac5ac2ee2c8a9680f64ef28d3444da2f4161e`. The three current workspace paths resolve to directories in this checkout (not symlinks). That establishes today’s lock/manager agreement, not target integrity. Add a wrong-target negative control and constrain package links to the admitted installation, or explicitly mark installed dependency contents as an external, unverified input.

## Environment, tests, and companions

The `POLISYOS_GOVERNED_ARTIFACT_ROOT` change addresses the prior finding: unset removes it; a contained selected path is remapped under the clone; an outside path is refused; the trust-specific output runner applies the same mapping. The tests cover unset, selected mapping, and external refusal. They test the helper value/refusal boundary rather than a real OpenAPI example whose emitted bytes change with the mapped artifact.

The child test for an ignored untracked Python file is genuine and behavior-based: it reads the copied file, then demonstrates different output after changing source bytes without force-adding the file. Other tests cover missing required input, a mocked missing-tracked member, symlink ancestors/unselected links, FIFO, disk preflight, owner-contract local roots, structural cache names, and lock mismatch. Gaps relevant to the closure claim: no canonical trust compilation from the copied tree; no removal of each of the five receipt members; no denied-directory traversal control; no redirected package-runtime target control; no producer-output check for the mapped OpenAPI root; and no content digest/after-copy verification. These are mechanism-level conditions, not evidence of current production input bytes.

The patch changes the manifest and renderer, and its new renderer fields are absent from the current `docs/reference/generated-artifacts.md`. That generated reference is a mandatory renderer companion before source freeze. No DEBT-register content change is implied; the debt file is now a required input. Preserve the current generated output and run the owning renderer only after source review.

A scoped source scan also finds other inherited path-valued settings in runtime HTTP code, including `POLISYOS_RUNTIME_SERVICE_PRINCIPAL_GRANTS_PATH`, `POLISYOS_PUBLIC_PUBLICATION_CONFIG`, and `POLISYOS_PUBLIC_VERIFICATION_CONFIG`. Whether the OpenAPI export reaches these paths and whether they affect emitted bytes is **not established**. The author correctly limits the claim to the mapped governed root and labels other ambient/path reads `not_established`. Keep that label unless the effective family environment is separately reconciled. Arbitrary absolute reads remain outside this copier’s guarantee; the falsifier is a child read from a deliberately changed external file, and the smallest general closure is an OS sandbox/mount boundary.

## P40 and final disposition

**P40: SAME_CLASS_DEEPER.** All blockers are deeper instances of the same source/input-basis and isolation class. The patch structurally widens from Git-visible selection to declared filesystem roots and fixes the known governed-root path, but it has not yet covered scan failures, canonical-consumer cache semantics, or package-link targets. Do not add per-path exclusions. Widen the basis mechanism and run the discriminating controls above, or retain each unresolved boundary as an explicit residual with its falsifier.

No source or test was changed in this review. No tests, generator, native wave, or Git mutation was run.
