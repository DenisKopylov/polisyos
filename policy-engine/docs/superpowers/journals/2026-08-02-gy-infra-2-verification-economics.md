# GY-INFRA-2 Verification Economics Journal

Plan: `docs/superpowers/plans/2026-08-02-gy-infra-2-verification-economics.md`

## 2026-08-02 — Session and branch receipt

- Main checkout began at `4b9e76f20d3ae68d65672faf69493141f158c954` on `main`; the main checkout had one unrelated user edit in `policy-engine/src/polisyos/data_forge/read_api/catalog.py`. It was not copied, modified, stashed, or otherwise touched.
- Isolated worktree: `/Users/deniskopylov/polisyos/.worktrees/gy-infra-2`.
- Attached branch: `codex/gy-infra-2`; base/current-main identity at creation: `4b9e76f20d3ae68d65672faf69493141f158c954`.
- `python3 -m tools.cli workspace bootstrap` provisioned `.venv` but returned an honest setup non-receipt when `pre-commit install` refused the repository's existing `core.hooksPath=/Users/deniskopylov/polisyos/.git/hooks`. The hook configuration was preserved.
- `corepack pnpm install --frozen-lockfile` completed for all six workspace projects with pnpm `10.33.2`; lockfile resolution was skipped and 1,211 packages were linked.
- `python3 -m tools.cli workspace doctor` completed its checks and returned exit `1` only for a pre-existing generated schema reference drift: `docs/reference/ir/schema-catalog.md`. Python 3.14.0, Node 22.22.2, uv 0.9.21, Playwright Chromium, `uv.lock`, `pnpm-lock.yaml`, runtime OpenAPI, and frontend contracts passed.
- This baseline was captured before any task source or tool edit. Under P34 it is not attributed to GY-INFRA-2; no generated file is refreshed in this task.

## Initial design and pattern pass

- Part A is `extend-existing`: `tools/lib/timing.py` already owns records, retention, atomic replacement, p95 summaries, and budgets; `tools/cli.py` persists registered runs. The registry already discovers all 41 `check_layer3_gy_*.py` scripts, but direct canonical invocations bypass the wrapper. State: `artifact_missing` for direct run timings and `surface_missing` for before-run budget/unmeasured inspection.
- Chosen Part A path: one shared direct-entry timing wrapper, 41 mechanical boundary wires, and one generic shell-free timed-suite runner for Atlas/frontend commands. The direct command forms remain unchanged.
- Part B is `producer_missing`/`verification_missing`: E14(b) is ratified, but the repository has no code-review delta packager. The academic `build_expert_review_bundle.py` supplies deterministic assembly patterns but is a different domain and will not be generalized into a god-bundler.
- Part C remains measurement-gated. P29/P32 prohibit a serializer-success or trusted-manifest claim from standing in for cold/warm byte identity. No cache implementation begins before the cold component table and serialization verdict exist.

## Committed historical timing evidence available to Part A

These are input samples, not yet the catalog. Exact source anchors will be stored with each catalog entry.

- Depth-N: check `104.41s`; corrupt-field drift `9.09s`; behavioral rederive `1493.17s`; source-flip `226.77s`; writer `727.52s` (`docs/superpowers/journals/2026-07-14-gy-n10-stage-4.md:2519-2524`). A later final closeout records writers `3660.436012s` and `1613.412167s`, and check `87.343036s` (`docs/superpowers/plans/2026-07-20-gy-n11-honest-confidence-ledger.md:787-788`).
- N11: final writers `1173.279650s` and `1111.911306s`; independent check `898.666254s`; source-flip `844.533s` (`docs/superpowers/plans/2026-07-20-gy-n11-honest-confidence-ledger.md:757,771-773`).
- CG1 full census: `4695.04s`; design-generation/N4 behavioral rederive: `1329.57s`; second-domain rederive: `263.20s` (committed GY-N10 journals; exact catalog anchors will be validated before entry).
- Atlas disposition check: `11.61s`; status governance: `43.900s`; combined Python governance: `138.461s` (`docs/plans/active/atlas-slices/DS19-false-substrate-strangle-wave-journal.md:152`; `DS4-status-grammar-rebinding-journal.md:1947,2035`).
- Full dashboard Vitest: `77.73s` and `181.12s`; full ESLint cold `~19 minutes` and cached `5.93s`. Only the exact numeric receipts, with approximation explicitly represented, may enter the catalog; killed 90-second attempts are non-receipts, not samples.
- No committed complete duration was found for Playwright visual or the browser a11y wave. They remain explicitly unmeasured until run through Part A's timed-suite path.

## Progress ledger

- Task 1: complete (`f4fc44d73`).
- Part A: complete and independently approved through `923f5ca33`.
- Part B: round-1 Important fixes complete; fix-only independent re-review pending.
- Part C Gate 0: pending.
- Part C implementation: not authorized before Gate 0.
- Final replay: not priced before source freeze and reviews.

## Part A — measured budget catalog and reporting surface

- TDD RED: `.venv/bin/python -m pytest tests/repo_quality/tools/test_timing.py tests/repo_quality/tools/test_unified_cli.py -q` failed during collection because the new catalog/report APIs were absent. The focused suite became green after the catalog parser, literal-p95 drift guard, separately named `(tool, mode)` lane projection, and `report-timing --include-unmeasured` surface were added.
- The catalog stores only literal completed samples and recomputes `measured_p95_ms` with the shared percentile function. `recommended_timeout_ms` is exactly `2 * measured_p95_ms` (GY §3.5.7 E9's historical `>2x` stop rule), with no rounding/slack. Existing per-tool `summaries`, `tool_count`, and their denominators remain unchanged; `lane_summaries` is the separate catalog projection.
- Fresh Atlas governance receipt: `tools/quality/testing/run_timed_suite.py --lane atlas.python-governance` ran `uv run --extra test --with 'jsonschema>=4.25' python -m pytest architecture/atlas_surfaces/test_frontend_disposition_register.py architecture/atlas_surfaces/test_status_retirement_inventory.py -q`; exit `0`, `30` tests passed, duration `160233.242ms`. The repository `.venv` lacks `jsonschema`, so the first direct `.venv` attempt was an honest collection non-receipt; the locked temporary `uv` environment supplied the declared checker dependency without editing project dependencies.
- Fresh frontend and browser lanes are recorded only when their runner records exist. The full ESLint and Vitest lanes were started with distinct JSONL paths; no approximate historic ESLint duration or killed timeout is used as a sample. Playwright visual and browser a11y remain serialized after those browser-free lanes settle.
- Fresh full Vitest receipt: `tools/quality/testing/run_timed_suite.py --lane frontend.vitest --cwd apps/runtime-dashboard -- corepack pnpm run test:components`; exit `1` (preserved semantic RED), duration `292223.026ms`. This is a completed measurement and is added to the literal sample set without converting the suite result to green.
- Fresh Playwright visual receipt: `tools/quality/testing/run_timed_suite.py --lane frontend.playwright-visual --cwd apps/runtime-dashboard -- corepack pnpm run test:visual`; exit `1` (preserved semantic RED), duration `127124.782ms`. The browser-a11y lane started only after this process had exited, so the browser/fixed-port resource was serialized.
- Fresh browser-a11y receipt: `tools/quality/testing/run_timed_suite.py --lane frontend.browser-a11y --cwd apps/runtime-dashboard -- corepack pnpm run test:a11y:pages`; exit `0`, duration `118287.438ms`.
- Catalog identity ruling: the CG1 receipt ran the historical temporary `/tmp/gy_n10_cg1_l2_census.py`, not the current `check_layer3_gy_n10_cg1_l2_relation_census.py` guard. It is therefore published as `historical.gy-n10-cg1-l2-census:default`; no equivalence to the current guard is claimed. `report-timing` declares this catalog's scope as `requested_expensive_lanes_only`: non-catalogued `check_layer3_gy_*` lanes are explicitly outside this requested expensive-lane set, not silently omitted `unmeasured_budget` findings.
- Fresh full ESLint receipt: `tools/quality/testing/run_timed_suite.py --lane frontend.eslint --cwd apps/runtime-dashboard -- corepack pnpm run lint`; exit `0`, duration `1656678.371ms`. This replaces the unmeasured lane; the historical approximate `~19 minutes` was not used as a sample.
- Independent Part A review of `498351b..6bcc95b` found one Important text-surface gap: empty per-tool summaries returned before rendering the catalog lanes. Fix `dc5ff8505` removed that return and added a missing-log text regression; focused tests, Ruff, and `git diff --check` passed. The fix-only re-review returned approved with no Critical/Important findings.

## Part B — deterministic full and delta review packages

- Pattern closure: the new standalone producer and its binary, length-framed artifact close the
  Part B `producer_missing` and `verification_missing` labels without generalizing the unrelated
  academic expert-bundle builder. Full and delta packages share one renderer (P31); real Git
  object resolution, ancestry checks, hostile configuration controls, and real temporary
  repositories provide behavioral proof rather than marker proof (P29/P32/P33).
- TDD RED was observed in five stages: the first full-package witness failed because the script did
  not exist; delta witnesses then failed because `--prior-findings` did not exist; the Git-admin
  target witness showed that an otherwise valid package could be written below `.git`; and the
  hostile-environment/order-file witnesses showed that inherited Git context or `diff.orderFile`
  could redirect or reorder a package. A final macOS case-fold witness proved that `.GIT` could
  alias `.git` despite lexical containment, so admin ancestry is now also checked by inode. The
  focused GREEN command is
  `.venv/bin/python -m pytest tests/repo_quality/tools/test_review_package.py -q` (`9` passed).
- Every revision is peeled with `git rev-parse --verify --end-of-options <rev>^{commit}` and only
  resolved object IDs cross into the ancestry/diff commands. Git execution uses argument vectors,
  disables external diff/textconv, prompts, pagers, replacement objects, and lazy fetch, and pins
  diff ordering/format controls. Output and checklist paths are realpath-contained in the Git
  worktree while `.superpowers/` remains allowed; `.git` markers, admin/common directories,
  symlink traversal, path escapes, and output/checklist aliasing fail closed.
- Delta checklists are raw length-framed bytes with SHA-256 over those exact bytes. The behavioral
  witness covers CRLF, NUL, `0xff`, marker-like content, shell metacharacters, and no final newline;
  generated Git text alone is normalized to LF. The complete package is gathered before one
  `atomic_write_bytes` call, and both early validation failures and a late corrupt-object diff
  failure preserve an existing valid output.
- Actual branch package from `4b9e76f20..923f5ca33` (branch base through reviewed Part A):
  `251678` bytes, SHA-256
  `11e5850560e6ea110a3ace8386c559a3d2a9cd88ab3432888cad81e2117027ff`.
- Natural Part A re-review comparison: the initial Task-3 package
  `498351be8..6bcc95bff` is `75031` bytes; its fix-only delta
  `6bcc95bff..dc5ff8505`, carrying the earlier Important finding, is `4374` bytes.
  The delta is `5.830%` of the full package (`17.15x` smaller), so the real branch example also
  clears the order-of-magnitude target rather than relying only on the representative fixture.
- Architecture guardrails were run and returned an honest pre-existing deep-import-baseline
  non-receipt (five runtime HTTP imports plus stale removals). Both
  `git diff --exit-code 4b9e76f20 -- src/polisyos/runtime/http architecture/baselines/imports/deep_import.json`
  and the broader `git diff --exit-code 923f5ca33 -- src architecture/baselines/imports/deep_import.json`
  returned `0`: neither Part A nor Part B changed the source/baseline inputs to this gate. No
  governed baseline sync was performed outside this task's fence.

### Part B independent review — round 1 fixes

- Round 1 was not approved: `0` Critical, `4` Important, `0` Minor. The exact checklist is retained
  at `.superpowers/sdd/2026-08-02-gy-infra-2-verification-economics/part-b-review-findings-round1.md`.
  The expanded focused suite first returned five RED witnesses: ignored gitlinks, uncommitted
  attribute influence, filesystem-alias acceptance, and patch bytes duplicated into both the stat
  and patch sections (the purity break was visible in two tests).
- Gitlink completeness now forces `--ignore-submodules=none` and `--submodule=short`. A real local
  submodule advances between the reviewed commits while hostile local config requests
  `diff.ignoreSubmodules=all` and `diff.submodule=log`; name-status still contains
  `M\tvendor/sub`, and the patch contains the stable short gitlink representation.
- Git `2.49.0` supports resolved-tree attributes through `GIT_ATTR_SOURCE`/`--attr-source`.
  Inherited `GIT_ATTR_SOURCE` and `GIT_DIFF_OPTS` are scrubbed, each diff subprocess receives the
  resolved head commit as its attribute source, and global/system attributes are neutralized.
  Because `$GIT_DIR/info/attributes` has higher precedence and Git exposes no ignore switch, any
  nonempty, symlinked, or non-regular info-attributes source fails closed before diffing; the check
  is repeated before the atomic write. This avoids mutating Git admin state while preventing
  unversioned rules from being believed. Same-range hostile-env and uncommitted-`.gitattributes`
  witnesses now produce identical bytes; a nonempty info file preserves the prior output and
  returns a refusal.
- Checklist/output aliasing now uses filesystem identity after lexical comparison. macOS
  case-folded names and cross-platform hardlinks are refused before the checklist is read or the
  destination is replaced.
- Stat, name-status, and patch options are separated. Only the patch lane receives `--patch`,
  `--binary`, `--full-index`, context, and prefix options. For the exact reviewed range
  `923f5ca33..c8c02072a`, the old package was `86787` bytes with a `43186`-byte patch-bearing stat;
  the rebuilt package is `43979` bytes with a pure `380`-byte stat and unchanged `42991`-byte
  patch: a `49.325%` package reduction. Rebuilt SHA-256:
  `ea122fcc8dc155746d7b7536c85d7d0a443ce73ea1d9c17611f3bb2c5987442b`.
- Focused GREEN after all fixes:
  `.venv/bin/python -m pytest tests/repo_quality/tools/test_review_package.py -q` (`12` passed).
  Focused Ruff, Ruff format check, and `git diff --check` also passed.
- Fix commit: `495bb07490ec8b97af508989635aa3927f7c1a5c` (`fix(tools): make review
  packages hermetic`). The committed tool produced the required fix-only delta for
  `c8c02072a4dd673db62dcc2038452b51c2849048..495bb07490ec8b97af508989635aa3927f7c1a5c`
  with the exact round-1 findings as its checklist. Package:
  `.superpowers/sdd/2026-08-02-gy-infra-2-verification-economics/part-b-delta-c8c0207..495bb07.review`,
  `22525` bytes, SHA-256
  `d3823f059dda1891bd3ae80d8d6ef2d926df90fdd544bd5cb52f06cd6a98e119`; embedded checklist
  length `2312`, SHA-256
  `679b7659f5a14cba3814ab07bf09bcdf2983b3f4a2768abaa9d5099200fe1264`.
