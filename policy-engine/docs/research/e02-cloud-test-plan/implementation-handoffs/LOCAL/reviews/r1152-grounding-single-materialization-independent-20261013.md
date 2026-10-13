# R1152 independent review of R1147 grounding snapshot

**Verdict: GO for one focused native replay only.** R1147 addresses R1142's split-capture finding: a fallback value is now converted once, with that captured text reused for the immutable lookup view and the JSON projection consumed by payload, hash, and FTS paths.

## Binding and scope

- Current root frame: `root-author-source-frame-r1151-20261013.json`, SHA-256 `12e262d19976b9a2ca4642cbe228f89e671dbfe09c957fb23ae058e8c4d84213`; HEAD `5fd4096ab9389d15abcedb00b03b968f6b60c953`, tree `d65d5ba135001d29968734cb0bace6fe50a572b8`, branch `codex/e02-unified-local-20261009`. The frame records 568 physical source paths.
- Candidate: `raw/r1147-grounding-single-wire-and-runtime-snapshot-materialization-20261013/candidate.patch`, 95,020 bytes, SHA-256 `a6a5ad45cdea0592265847abf8b8e0129e834484b2c6817e060b18e79acefe3c`; manifest SHA-256 `1f7a257c21a6cabaa6c144527a087ee92cf20e37f70d87f1da90c449621c25f0`. The packet binds the prior source frame R1141; its nine physical preimages remain exact after the metadata-only HEAD advance. The candidate remains virtual.
- I verified the complete manifest denominator: nine paths, eight `.py` and one `.md`; all nine current preimages match. `git apply --check` exits 0 and the worktree has no tracked changes. The full set is `runtime/quality/README.md`, `credal_reference.py`, `grounding_active_controller.py`, `grounding_bind.py`, `grounding_phrasing_defense.py`, `grounding_relation.py`, `tests/unit/runtime/quality/test_credal_reference.py`, `test_grounding_bind.py`, and `test_grounding_relation.py`.

## Review of the R1142 property

`_capture_reference_payload` returns the frozen lookup value and its matching wire projection from one traversal. For exact dictionaries it visits entries in the old sorted-key order, captures each fallback once, and uses that captured text in both representations. `_FrozenReferenceMapping` retains the wire for later `_json_ready` reads, so payload/hash/FTS do not reevaluate the fallback. The generic non-dict `Mapping` branch still emits the established `default=str` representation at that mapping boundary while separately freezing its lookup view; the existing UserDict, MappingProxyType, and nested-mapping controls retain that behavior.

The candidate adds direct stateful-fallback tests for lookup and payload, then checks content hash and FTS text against an independent serializer oracle with no later fallback calls. The six legal completion kinds remain in the legacy FTS source-field oracle. The static recursive-cycle refusal matches the standard JSON encoder for recursive JSON containers. The isolated `probe.py` also passes: its stateful exact-dict and generic/nested Mapping outputs match the standard-library wire oracle.

**P40 bucket: SAME_CLASS_DEEPER.** R1147 supplies the mechanism-wide capture that R1142 lacked; I found no new concrete escape in the reviewed nine-path delta. This is a scoped code-review GO, not a formal closure or a global/native acceptance claim. `closure_ids: []`.

## Verification limits

The author reports AST parsing and configured Ruff format/lint for all eight changed Python paths. I independently checked the source binding, all nine preimages, the patch apply check, and ran the packet's stdlib-only probe. Pytest, product imports, database/runtime/ML checks, and native replay remain unrun; the root may now run the single focused native wave.
