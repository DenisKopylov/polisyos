# R975 native SOTA row execution readiness — 2026-10-13

**Decision:** The existing local locked environment can provision the canonical native command. The full native SOTA wave is not yet green, inherited, or frozen; run it once after root freezes current source/profile/input and completes independent review.

## Exact boundary

Read-only checkout: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos, branch codex/e02-unified-local-20261009, HEAD dae174623baca79449638758ada159ab7ebdaefb, tree 0e7846a9576e698150de7e613d424dc72d5dd43a. Root source frame root-author-source-frame-r948-20261013.json has SHA 42bcaacaa47c4a131b64157a1f609bd84ff869565bdcbcd1761f9ad207d5a418, records 545 postimage paths and zero staged paths, and identifies itself as an author checkpoint rather than a global freeze or G acceptance. At inspection, branch was three commits ahead of origin and dirty: 2,179 status entries, 37 tracked modifications, 2,142 untracked.

The current gate registry repository_sota.toml is b049b8f7d27ec1af17c0d024da86f2c4ab846a24c05a654448f1eb02cbc0baf1, runner repository_sota_closeout.py is f09855fdc002fe8b8b5fd02d66bfd51c444438288ca95fb05d398d96d7e72008, phase-3 test is f72c61f30fcf65e080537c80bd92e004d3a0cdf919b2ec631faaa93b0ee40c39, and phase-5 test is a5db3609d4d01d3f22bfd8174c2ca841e1376e93558fecd98061e7f5d2a9d5e1. Registry and runner bytes match R398. The current phase-5 test is newer than the test image used in R398; its old test outcomes do not transfer.

## Complete command denominator

Current runner planes reconcile to **13 registry rows**, **20 unconditional children** (6 registered + 14 supporting), **1 conditional docs-freshness child**, and **11 top-level preflight predicates**. The older 17-child count describes pre-dispatch source and is obsolete.

| Registry row | Owner | Route and exact declared command | Current status |
|---|---|---|---|
| topology-loose-files | team-architecture | subprocess; uv run pytest tests/repo_quality/architecture/test_repository_sota_phase3_topology_cleanup.py -q | Native UNRUN. R398 broad replay failed five same-module topology tests. |
| import-linter | team-architecture | subprocess; uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml | UNRUN. |
| public-surface | team-architecture | subprocess; uv run polisyos-tools architecture guardrails check | UNRUN. |
| generated-drift | team-architecture | subprocess; uv run polisyos-tools architecture guardrails check --all-generated-checks | UNRUN; use full generated checks. |
| docs-freshness | team-docs | preflight:docs-freshness-contract + conditional:docs-freshness-runtime; uv run polisyos-tools validation check-docs-accuracy --repo-root . | Current UNRUN. R398 zero-count config was not a child receipt. |
| public-polish | team-docs | subprocess; uv run pytest tests/repo_quality/architecture/test_repository_public_polish.py -q | UNRUN. |
| shim-audit | team-architecture | preflight:migration-shim-contract; contract-only runner | UNRUN row-isolated; R398 combined contract output reported expired shims. |
| complexity-exceptions | team-architecture | preflight:complexity-exception-contract; contract-only runner | Current UNRUN. Empty exception rows are valid; R398 KeyError was test-consumer indexing, not active complexity debt. |
| security-baselines | team-security | preflight:ops-modes; contract-only runner | UNRUN row-isolated; combined R398 invocation was nonzero. |
| dependency-baselines | team-security | preflight:ops-modes; contract-only runner | UNRUN row-isolated; combined R398 invocation was nonzero. |
| sbom-baseline | team-security | preflight:ops-modes; contract-only runner | UNRUN row-isolated; combined R398 invocation was nonzero. |
| commit-policy | team-release | preflight:ops-modes; contract-only runner | UNRUN row-isolated; combined R398 invocation was nonzero. |
| command-registry | team-devx | subprocess; uv run polisyos-tools docs --output docs/reference/tools.md --check | UNRUN. |

The exact 20-child argv and all 11 preflight names are enumerated in the companion JSON. Supporting children are: repository-sota-registry-contract; repository-structure; last-mile-inventory; package-import-gates; directory-health; test-ratchets-helper-topology; dead-overrides; extension-examples; adr-thematic-index; validator-module-size; schema-purity; operability-release; compatibility-release; acceptance-audit. Conditional child is docs-freshness-runtime.

Canonical one-shot command from policy-engine/:

    uv run polisyos-tools workspace repository-sota-closeout --output-json docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-sota-frozen/report.json --subprocess-receipt-dir docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-sota-frozen/children

Do not add --contract-only or --skip-generated-checks. Retain full top-level stdout/stderr/status, report JSON, each child argv/exit/stdout/stderr, and generated _build/.tmp/last-mile outputs under ignored LOCAL/raw.

## Profile, timing, controls, and expiry

The locked profile is product-root uv run with policy-engine/uv.lock SHA e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463. Existing .venv metadata records CPython 3.14.3 and uv 0.10.6; package metadata confirms pytest 9.0.2, Ruff 0.14.10, mypy 1.19.1, basedpyright 1.39.0, Torch 2.10.0, BoTorch 0.16.1, JAX/JAXlib 0.8.2 and hnswlib 0.8.0. No imports or environment changes were made. Native SOTA uses this standard project profile; optional vector-search is not invoked by this queue.

Full native duration and matching timeout are UNMEASURED. R398's 71.656 seconds was a 28-module pytest replay, not native SOTA. The 1.654-second contract-only receipt and 82 findings belong to older candidate 9e89. A coarse 251.358-second guardrails timing lacks argv and does not establish duration for --all-generated-checks. Root should set and retain an explicit generous deadline for the first frozen serial wave; these timings are not proxies.

R398's prior broad replay exited 1 with five phase-3 topology and three phase-5 test failures. The current phase-5 source contains behavioral tests for deleting each required row, wrong commands/routes, generated-only skip behavior, malformed rows, refusal to run children on invalid registry, and retaining real child failure output. The current phase-5 suite is UNRUN; its PASS cannot be inferred from those declarations. R398 also records three R3 remove-property/keep-markers patch replays as UNRUN.

R398 counted 33 effective expiry findings among 34 past-date fields, one on a zero-count docs baseline. Do not carry that tally as the current contract result: current exception/config/test source changed after R398, and the current full closeout is UNRUN. Current source still includes old dates. Recompute after freeze; remove technical debt only on measured evidence. Any still-needed exception requires its own named issuer decision, with no blanket renewal, waiver, or date shift.

## Input denominator and P41

The declared command denominator is complete; the current file-level child input denominator is not established. Child commands scan or select repository paths dynamically, and no current native read-set ledger exists. The R948 545 source postimages are not gate inputs. An older 9e89/93d6 contract audit covered 969 old checker paths and found three changed-path intersections. R398's 6,202-file map came from broad pytest and is not the native SOTA denominator. P41 is not_established; no current red can be labeled inherited. P37/P38 remain not_established for the full native closeout until current frozen child outputs show what was measured.

Remaining root work: reconcile current physical topology without widening allowlists; batch technical repairs; obtain row-specific issuer decisions only where an exception remains necessary; independently review; freeze current source/profile/input; run one complete serial native wave. closure_ids=[].

Sources: R398 row-debt review daccb7b6ea5043599fa73d695fec32b9f8d86ab0fa7afb423d49223d7013388b; static queue audit 8dba7f9c31d5784bb1aa61cbced732bac39b5fe8d6cf44dbc84d5130e0e48e1c; full command plan 4170452d0c8c8296a3d091ee6b5c3ba23cfc6dc02d1c541e5a1c1435ffa24c18.
