# Workspace CAS negative-property patch candidate

Source candidate HEAD: `c4563fd4da93bf9cc06de3dc77554a8a0d117359`; known 10-file WIP is present.

Target test: `tests/unit/runtime/quality/test_workspace_loop.py` SHA-256 `b8b69ea936a9149bb2653bc39e6d7d23b462cef8b19da3a3b25ca41c2aa00cc3`.
CAS API source: `src/polisyos/core/artifacts/store.py` SHA-256 `f787817462174c52d3ffdce9586d74a1c42276af8f38fae08d73c5f8bb7beec2`.
CAS layout source: `src/polisyos/core/artifacts/_layout.py` SHA-256 `693f2a119d9b413e3091f0fbf5b1dc093ad3786c7af5cc15ed0c3209e660f194`.
Patch: `LOCAL/raw/workspace-cas-negative-property.patch`
Patch SHA-256: `b53f1ed50ab41eb245cbfbab085d63753175472ded479d6a5473a2dbcc0abad8`

The existing predicate walks every file below the CAS root, so it treats FileSystemCAS's internal empty ownership transaction lock as a published artifact. The replacement asks `FileSystemCAS.inventory_snapshot()` for its complete stable artifact-view inventory and requires both a `pass` verdict and zero entries. This measures blobs plus default and selected manifest views using the CAS's source-of-truth inventory, and does not count transaction metadata outside the artifact member base. It is not a blanket root allowlist: actual artifact members still appear as inventory entries; an incomplete/failed scan cannot satisfy the assertion.

The production refusal expectation and the existing no-payload-before-admission property remain unchanged. The current working test already includes the separately prepared typed `DatasetSearchResult` fixture repair. This patch changes no checkout files, was not applied, and was not test-run.
