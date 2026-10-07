# C4 independent CAN Mapping review

## Frozen identity and scope

- Candidate: `e3cb3fafc847b94a5d4b3adc03b814b4c711920c`
- Tree: `2d27c9c182cf550088c5a8c072dc2f36df84e20d`
- Parent/baseline: `79cbb05c90026973a32022ca02c63877b2cde1a5`
- Readback: candidate HEAD/tree match the pinned identity; branch `codex/e02-C-canon-20261006`; tracked worktree clean.
- Exact delta: 4 paths, 130 insertions: `io.py`, `test_ir_adapter.py`, artifacts README, and one release fragment. No other paths changed.
- Reviewed the complete four-path commit diff and the LA-021/CAN-01 handoff/criteria.

## Independent property result

The required property is that an unchanged, complete `ArtifactManifest.model_dump(mode="json")` mapping from a typed `FileSystemCAS` can be passed through public `get_json_artifact`, and returns the same payload while honoring the persisted profile.

At this candidate, `_validated_ir_canon_info` shallow-copies a Mapping and converts `separators` only if its value is exactly a list of length 2 whose elements are exactly strings. The normal strict `CanonInfo.model_validate(..., strict=True)`, supported name/version comparison, nonnegative depth check, and pre-byte validation order remain in force. Since the copy is shallow but the new tuple is assigned only into the copied dict, the caller's full manifest mapping is not mutated.

Independent runtime witness used the observed global CPython 3.14.0 / Pydantic 2.12.5 with `PYTHONPATH=src`, not a new environment. It wrote a depth-129 payload using IR `CanonSpec(max_depth=129)` to a real temporary `FileSystemCAS`, obtained the typed `CoreArtifactRef`, read the real manifest, and passed the untouched full JSON-mode mapping through a byte-counting wrapper backed by that same CAS. The manifest ID equaled the typed ref; the decoded payload equaled the original; the mapping remained value-identical and unmodified; reads were exactly one manifest and one payload read.

Nineteen independently mutated full-mapping profile cases all raised `unsupported_ir_canon_profile` with zero payload-byte reads. These cover separator lists of length 1/3, non-string and bool separators, unsupported name/version and wrong name/version types, invalid scalar types for each bool profile field, wrong/string/bool/negative depth, missing separators, an extra profile field, and an absent profile.

The remove-property/keep-markers control executed the exact candidate module source in memory with only the list-to-tuple normalization block removed. The on-disk source, tests, README, and release fragment remained unchanged. The same valid JSON-mode Mapping then failed with `unsupported_ir_canon_profile` before bytes, while the positive and negative test markers remained on disk. This is a behavioral control, not a marker check.

## Commands and captured output

Focused affected selectors, including both persisted-depth checks and the existing raw-Core float-tag boundary:

```sh
env PYTHONPATH=src /opt/homebrew/opt/python@3.14/bin/python3.14 -m pytest -v -q tests/unit/core/artifacts/test_ir_adapter.py -k 'json_mode_manifest_mapping or malformed_json_mapping_separators or unsupported_json_mapping_profiles or keeps_other_json_mapping_profile_fields_strict or profileless_json_mapping or persisted_profile_depth or direct_core_json_writer_remains_an_ir_profile_bypass'
```

Result: exit 0, 14 passed, 30 deselected in 0.14s. Full output: `.tmp/e02-C4/raw/can-independent/final/focused-pytest.out` (SHA-256 `ec13b07075705e78575f94e56c86cd546af8215e824ae1c5993f7ecd1fa49666`).

Independent actual-CAS/mutation/removal witness:

```sh
env PYTHONPATH=src /opt/homebrew/opt/python@3.14/bin/python3.14 /Users/deniskopylov/.codex/worktrees/e02-c-canon-20261006/polisyos/.tmp/e02-C4/raw/can-independent/final/mapping_oracle.py
```

Result: exit 0. Full JSON output: `.tmp/e02-C4/raw/can-independent/final/mapping_oracle.out` (SHA-256 `86d1657265d680b6ad226db794e3d80dd5b9f9f43240563d874b057acac30ba0`). Probe source: `.tmp/e02-C4/raw/can-independent/final/mapping_oracle.py` (SHA-256 `313ce03b42deda32563c262fa71c5bc3e296872a431a86a522d4ed52cde0f3f7`). The earlier plan is `.tmp/e02-C4/raw/can-independent/probe-plan.md` (SHA-256 `b831e5f9d37c718af5c392c493c4f1481127ae01b37e6289df54b6039e99752c`).

## Finding disposition

- **P38:** Prior code measured strict tuple acceptance directly and rejected the exact JSON representation even though the supported profile property held; this real mapping case diverged before payload read. The shared profile intake now handles that representation narrowly and the property-level witness passes. Recommend **closed** for this specific Mapping-intake escape.
- **P37:** For the positive witness, the profile and artifact ID came from the real CAS manifest and were reconciled to the typed artifact ref. The reader independently validates the full profile before reading bytes; malformed variants are rejected at that boundary.
- **P40:** Same CAN shared profile-intake class, one representation level deeper; this is not a new historical-profile promise.
- **LA-021 overall: held.** This delta establishes the bounded JSON-mode Mapping behavior. It does not establish ownership/admission for raw Core-only `float_hex` bytes or readability for historical profile-less artifacts. The focused existing raw-Core test still shows `float_hex` rejected by the IR decoder; raw Core remains a separate held boundary, and profile-less historical readability remains unestablished. The delta is not evidence that the full LA-021 capability is closed.
