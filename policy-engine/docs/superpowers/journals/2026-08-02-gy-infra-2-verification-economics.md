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
- Part B: complete and independently approved through `1d24793a1`.
- Part C Gate 0: **NEGATIVE** at the clean `1d24793a1` boundary and independently approved through
  `5391639c6`; the one cold attempt failed closed in N10 provenance validation and the structural
  cache preconditions are absent.
- Part C implementation: not authorized; the conditional implementation task is skipped.
- Final replay: not triggered because Part C changed no byte under `src/polisyos/**`.

## Part A — measured budget catalog and reporting surface

- TDD RED: `.venv/bin/python -m pytest tests/repo_quality/tools/test_timing.py tests/repo_quality/tools/test_unified_cli.py -q` failed during collection because the new catalog/report APIs were absent. The focused suite became green after the catalog parser, literal-p95 drift guard, separately named `(tool, mode)` lane projection, and `report-timing --include-unmeasured` surface were added.
- The catalog stores only literal completed samples and recomputes `measured_p95_ms` with the shared percentile function. `recommended_timeout_ms` is exactly `2 * measured_p95_ms` (GY §3.5.7 E9's historical `>2x` stop rule), with no rounding/slack. Existing per-tool `summaries`, `tool_count`, and their denominators remain unchanged; `lane_summaries` is the separate catalog projection.
- Fresh Atlas governance receipt: `tools/quality/testing/run_timed_suite.py --lane atlas.python-governance` ran `uv run --extra test --with 'jsonschema>=4.25' python -m pytest architecture/atlas_surfaces/test_frontend_disposition_register.py architecture/atlas_surfaces/test_status_retirement_inventory.py -q`; exit `0`, `67` tests passed, duration `160233.242ms`. The repository `.venv` lacks `jsonschema`, so the first direct `.venv` attempt was an honest collection non-receipt; the locked temporary `uv` environment supplied the declared checker dependency without editing project dependencies.
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

### Part B independent review — round 2 diff-configuration closure

- Round 2 was not approved: `0` Critical, `1` Important, `0` Minor. Round 1's submodule,
  filesystem-alias, and stat-purity repairs were accepted; the remaining class was arbitrary
  repository-local or worktree-local `diff.*` configuration that the fixed Git argv did not
  override. The exact checklist is retained at
  `.superpowers/sdd/2026-08-02-gy-infra-2-verification-economics/part-b-review-findings-round2.md`.
- TDD RED was observed with the requested local `diff.suppressBlankEmpty=true` probe, a committed
  `*.py diff=hostile` attribute plus local `diff.hostile.binary=true`, and the independent
  worktree-scope driver variant `diff.hostile.xfuncname`. All three same-range rebuilds returned
  success and replaced the existing package before the repair (`3` failed witnesses).
- The repair is a generic fail-closed scope census, not pins for those examples. Before rendering
  and again before the atomic swap, the tool enumerates included/effective `diff.*` keys in both
  `--local` and `--worktree` scope. It permits only exact settings already overridden by the fixed
  argv plus arbitrary driver `.textconv` settings disabled by `--no-textconv`; every other key is
  reported with its scope and refused. This preserves the accepted hostile-config and submodule
  behavior while preventing an unknown driver/output key from silently varying reviewed bytes.
- Focused GREEN after the repair:
  `.venv/bin/python -m pytest -q tests/repo_quality/tools/test_review_package.py` (`15` passed).
  The three adversarial witnesses passed separately; focused Ruff, Ruff format check, and
  `git diff --check` passed. The renderer, package schema, review denominator, and source tree were
  unchanged.
- Fix commit: `6113c5ee856b598e029bcb330851731032171a03` (`fix(tools): refuse unbound
  diff configuration`). The committed tool produced the required delta for
  `078c5257f1d94989bb32e9d02a70d38c600a9305..6113c5ee856b598e029bcb330851731032171a03`
  with the exact round-2 findings as its checklist. Package:
  `.superpowers/sdd/2026-08-02-gy-infra-2-verification-economics/part-b-delta-078c525..6113c5e.review`,
  `10300` bytes, SHA-256
  `ad0fc323d891037817ad65b76ebf7948ab1856fce474c505f480b5e4baf79bc3`; embedded checklist
  length `1448`, SHA-256
  `26f8ed446a8852ce18f773f341e4df1682a09f7acf386de559ec6aaab6bec601`.
- The original round-2 reviewer process returned an honest workspace-credit non-receipt before
  reading the delta. A fresh independent reviewer then authenticated the `10300`-byte package and
  embedded checklist, inspected only the exact fix delta, and returned **approved: `0` Critical,
  `0` Important**. It confirmed generic local/worktree `diff.*` enumeration, fail-closed handling
  for every unsupported key, fixed-argv neutralization for the allowlisted keys, both pre-render
  and pre-replace checks, the two original hostile probes, and the separate worktree
  `xfuncname` variant. Part B is complete; no source or semantic denominator changed.

## Part C Gate 0 — measured NEGATIVE

### Measurement boundary and receipts

- Part C began on attached branch `codex/gy-infra-2` at clean source commit
  `1d24793a193121e1acf8abb794f25a93392c18dc`. The profiler was an ignored scratch harness;
  tracked status was clean before and after the attempt. It did not edit runtime source, tests, or
  governed artifacts.
- `production_data` was exposed to the isolated worktree through an ignored symlink to the main
  checkout. The profiler used that input without writing it, but the symlink and its owner-writable
  target did not enforce read-only permissions. The isolation-local `.venv` initially lacked
  OR-Tools. The command
  `uv sync --offline --extra solvers` returned an honest non-receipt because the locked
  `ortools==9.15.6755` arm64 wheel was absent from the local uv cache. Existing `ortools` and
  `immutabledict` packages were then symlinked from the main checkout's venv and used only for
  imports; their owner-writable targets likewise did not enforce read-only access. The exact link
  targets are captured in the raw receipt.
- Exactly one fresh-process owner derivation was attempted. It exited `1` after
  `160.194786417s`, with peak RSS `3,926,081,536` bytes. The authority path failed closed after
  `147.702943792s` of owner load with `OwnerProjectionError`:

  ```text
  n10_capstone_provenance_unstable:
    n8_owner_validation_failed: catalog_method_denominator_drift
    n10a_owner_validation_failed: stage_gap_triage_drift
      gap_id=n8_transport_tuple_hardcode
  ```

  This is a semantic non-receipt, not a timeout or profiler failure. No second cold attempt was
  made, and the existing validation outcome was not weakened or bypassed.
- Ignored raw receipt: `.superpowers/sdd/2026-08-02-gy-infra-2-verification-economics/gate0-raw.json`,
  `52,494` bytes, SHA-256
  `6042b800f2c001ab5fb3ada76c2c423b91178455581236c780901c1c558866b6`. Profiler source SHA-256:
  `b21aa0560a6e9019a2aa19da367138dae25c600dd8d939bd4249de2ff409d48f`; stdout/stderr SHA-256:
  `270c941ae1b99618a1494533259ca9b325b8d47d01b033dd45db9972ce787e06` /
  `680c2a920e1884662f5eff6ecd298a160eb72153769cb248c426b50622119bbf`.

### Question 1 — what dominates?

The table reports the path actually reached. Nested stages are identified and are not added
together.

| Component | Calls | Measured wall time | Owner-load share | Result |
| --- | ---: | ---: | ---: | --- |
| Owner bundle load | 1 | `147.702943792s` | `100%` | refused |
| N10 capstone envelope | 1 | `146.367557334s` | `99.096%` | refused |
| N10 provenance stability, nested | 1 | `129.938766583s` | `87.973%` | returned `drifted` |
| N10 pre-live validation remainder | 1 | `16.428594s` | `11.123%` | completed before refusal |
| L4 data-state materialization, nested | 1 | `7.434296375s` | `5.033%` | complete |
| Real L4 projection, nested | 1 | `7.189458375s` | `4.868%` | complete |
| `WorldModelRecord` construction, nested | 1 | `1.559069583s` | `1.056%` | complete |
| Production composed WMR | 1 cold + 2 hits | `9.309064459s` cold; `0.000005583s` / `0.000004083s` hits | `6.303%` cold | complete |
| N13b recomputation | 0 | not reached | unavailable | unavailable |
| CredalReference / edge construction | 0 | not reached | unavailable | unavailable |
| Actual DuckDB FTS / CG0 atoms | 0 | not reached | unavailable | unavailable |
| Solver stages | 0 | not reached | unavailable | unavailable |
| Final N11 canonical bytes | 0 | not reached | unavailable | unavailable |

For this real attempt, N10 provenance replay dominates: `129.939s`, or `88.0%` of owner time.
The gate refused before the CredalReference, approximately 792k-edge FTS, CG0, solver, N13b, and
final N11 observers were reached. Therefore this spike cannot honestly claim a new complete-cold
breakdown or confirm the prior single-lane `~2,258s / ~2,265s` attribution; that historical number
remains prior evidence only. The refusal itself is load-bearing: persisting a prior N10 result to
skip it would conceal exactly the current catalog/triage drift that the recomputation detected.

### Question 2 — what is serializable?

| Component | Content-addressed / byte-identical restoration | Gate-0 ruling |
| --- | --- | --- |
| N10 provenance/capstone result | Frozen JSON exists, but accepting it cannot establish that the current owners pass without replaying the dominant check. This attempt proves why: live recomputation found drift. | **Not safely reusable authority.** A cached result would weaken the gate. |
| `OwnerEvidenceBundle` | Its frozen dataclasses can be rendered as deterministic JSON, but `projection_sha256` proves only self-consistency. No loader independently proves the N10/N13b derivation or its real inputs. | `verification_missing`; its only high-value intake is also outside the Part C fence. |
| Composed `WorldModelRecord` | Existing typed CAS support validates bytes and the semantic content hash. The spike wrote `13,218` canonical bytes, SHA-256 `951161fa2dbc47404f45865e378e5e546bc49167d01e843bdf3eac845696b14e`, content hash `sha256:11c3b1cb30a20018b0a6b85335edb23d999e62be53c3a289e7e2961371ff7cbf`, and restored byte-identically. | **Safely persistable**, but only `9.309s`; persisting it would leave the measured dominant validation untouched. |
| `CredalReference` | The frozen edge map and per-edge/reference hashes make a canonical format possible. There is no persisted aggregate artifact, fail-closed loader, producer binding, or verifier cheaper than rebuilding all edges. | Persistable only after a new independently verified artifact contract; not reached in this attempt. |
| DuckDB FTS | The runtime explicitly opens `duckdb.connect(":memory:")`; it is not currently a DuckDB file. A mechanism-only two-row probe copied an in-memory FTS schema to a `1,847,296`-byte file and restored its functions, but did not exercise the real corpus or bind it to a CredalReference. | Technically file-persistable after redesign, but `artifact_missing` and `verification_missing`; the probe is not authority evidence. |
| CG0 atoms | Individual Pydantic objects can be canonicalized, but there is no complete-universe identity or loader proving every atom is bound to the current reference. | Persistable only with a new verifier; not reached. |
| Solver results | Private in-memory results carry no persisted input identity or independently checkable proof, especially for UNSAT/UNKNOWN. | Not safely reusable without replay today; not reached. |

Only the cheap WMR substage passed the byte-identity test. Persisting it would save at most about
`9.309s` per cold process while retaining the measured `129.939s` validation and all unreached
healthy-path work. That is the prohibited partial cache, so it is not built.

### Structural preconditions that independently fail

- The cache named in the task is not the cache responsible for N11's warm hit.
  `FoundryValuePort._world_cache` in `generation_cycle.py` only validates and deduplicates an
  already-supplied `WorldModelRecord` inside one value-port instance. The actual hit/miss boundary
  is the process-local `@lru_cache(maxsize=4)` on `_load_owner_bundle_cached` in
  `tools/quality/validation/layer3_gy_confidence_ledger_contract.py`; it wraps N10 plus N13b and is
  outside Part C's writable source fence. State: `bridge_missing`.
- `_resolve_authority_import_closure(repo_root,
  "polisyos.runtime.quality.confidence_ledger")` resolved exactly `120` modules with closure hash
  `sha256:9def58cbbeb8f55b06b1fc2a88dd016fa401f76ca4cf74affdf6e4da81b2e74a`.
  It omitted every checked dynamic producer: `generation_cycle`, `credal_reference`,
  `grounding_relation`, `intervention_substrate`, and `data_state_substrate`; it cannot represent
  the `tools/**` owner adapter. A key using only that mandated closure could hit after the actual
  producer semantics changed. State: `verification_missing` / P07.
- Trying to resolve closures for the actual runtime producers also fails closed today: several
  encounter the ambiguous `polisyos.foundry.methods.catalog.causal.causal_engine` module/package,
  while `intervention_substrate` reaches the unresolved `polisyos.ir.artifacts.refs` import.
- The existing deployment baseline separately hashes all `src/polisyos/**/*.py`. Consequently,
  an outside-authority-closure mutation under `src/polisyos` changes deployment identity and must
  be refused by witness 5; it cannot also be the hit required by witness 3. A future design must
  define the negative control outside both identities or explicitly separate their semantics.
- Existing CAS atomicity can protect bytes only when the expected artifact ID comes from an
  independently trusted key-to-artifact binding. A self-hashed JSON manifest or DuckDB file can be
  forged with internally consistent hashes and recreates the §3.5.6 trusted-JSON hole (P05/P32).

### Gate-0 decision and economics

Gate 0 is **NEGATIVE** on multiple conjunctive conditions:

1. the observed dominant stage is a mandatory validation that currently detects real drift and
   cannot be safely replaced by stored output;
2. the only byte-identical persisted component measured is cheap and insufficient;
3. the required 120-module key omits the actual producer and data path;
4. the high-value owner-bundle cache boundary is outside the authorized Part C fence; and
5. no valid owner bundle or final N11 bytes exist from this attempt against which a restored result
   could be accepted.

Capability labels are `verification_missing` for reusable dominant state and `bridge_missing` for
the correct cross-process owner intake. The pattern pass closes this iteration against P05/P07
(authority and replay), P29 (live property rather than markers), P31 (correct chokepoint rather
than the cited cheap instance cache), P32 (no trusted self-hashed blob), and P33 (no implementation
taught to the 240x witness). P34 requires retaining the provenance failure present at the
`1d24793a1` Gate-0 boundary as a non-receipt, not attributing it to an earlier boundary that was
not measured and not excluding or repairing it outside scope.

Part C therefore changes no runtime source or test, does not close the GY-DI1 debt row, runs none
of the six implementation witnesses, and triggers no deployment-identity replay. The supplied
before receipts (`1,086 + 951 + 951 + 937 + 975 + 952`) total `5,852s`, or `1h37m32s`. The user's
separate headline says approximately `1h52m` (`6,720s`), leaving `868s` not accounted for by the
six listed lanes; both are retained rather than silently treating the approximation as the
arithmetic receipt. Because no cache was implemented, there is no distinct measured after cycle.
The after state is unchanged by construction: the same `5,852s` listed-lane baseline and the same
approximately `1h52m` user headline remain applicable, but that is an inference from no source or
execution change, not a new measurement. The one `160.195s` failed process is a Gate-0 measurement
receipt, not a comparable full closeout cycle. Corruption counts, flip counts, governance numbers,
semantic denominators, gates, and artifact hashes are unchanged.

### Part C independent review

- The first independent review read the full Part C package for
  `1d24793a193121e1acf8abb794f25a93392c18dc..4c89993340b88bd836238edfe1bdc0f10591c4fd`:
  `16,648` bytes, SHA-256
  `ed0bf0a1cdfb7401161774a0365f876ce29e30eae5295863ba1f1f2ce953f55d`. The reviewer rebuilt an
  exact byte match and authenticated the raw Gate-0 receipt, timing values, WMR identity, closure
  census, and code paths.
- The substantive NEGATIVE was accepted, but the report received `0` Critical, `2` Important,
  and `1` Minor findings: enforced read-only permissions were overstated; the `5,852s` enumerated
  lane sum was conflated with the `6,720s` headline; and the provenance failure was called
  pre-existing without a pre-A/B cold measurement.
- Fix commit `5391639c6` corrects only those reporting claims. The required delta package for
  `4c89993340b88bd836238edfe1bdc0f10591c4fd..5391639c6` carries the exact prior checklist:
  package `6,554` bytes, SHA-256
  `2f48967e06c465b5026d7907ed28d7673b1e0229d95caefec7bdf258f73ce343`; checklist SHA-256
  `45602b3d8c52535f0fda2afe527901931682b81404b08b315bc13135463a2b81`.
- Delta-only re-review closed all three findings and returned approved with no new Critical or
  Important findings. Part C closes negative without runtime/test edits, implementation
  witnesses, gate changes, or replay.

## Final closeout verification before whole-branch review

- The failure/repair register was reopened at the final boundary. Part A closes the single timing
  intake/reporting class; Part B closes the single deterministic package renderer and hostile-Git
  input class. Part C remains precisely `verification_missing` + `bridge_missing`, not an
  implemented capability. P05/P07/P29/P31/P32/P33/P34 therefore support the negative ruling rather
  than licensing a trusted partial cache or excluding the live provenance refusal.
- At clean attached commit `2583dd2ab3003d075ee06ad8f5cd94540274d2aa`, the combined focused
  suite passed: `.venv/bin/python -m pytest -q tests/repo_quality/tools/test_timing.py
  tests/repo_quality/tools/test_unified_cli.py tests/repo_quality/tools/test_review_package.py`
  returned `39 passed` in `11.48s`. The behavioral suite includes real direct subprocess timing,
  the AST-derived all-validator boundary census, missing/over-budget reporting, and hostile real
  Git repositories for full/delta package determinism and fail-closed inputs.
- The source census found `41` `check_layer3_gy_*.py` scripts and `41` files routed through
  `run_timed_entrypoint`. A missing timing-log invocation of
  `python -m tools.cli report-timing --output-format json --include-unmeasured` returned `0` and
  published all `20` requested catalog lanes as measured, with p95 and recommended timeout,
  before any local execution record existed.
- Ruff over all changed Python files returned two diagnostics, both at unchanged baseline lines:
  C401 in `check_layer3_gy_p1_substrate_authority_audit.py` and S110 in
  `check_layer3_gy_workflow_mode_truth_audit.py`. Feeding the exact base-commit versions to Ruff
  reproduced each diagnostic; checking the remaining changed files, plus each affected file with
  only its reproduced baseline rule ignored, returned `All checks passed`. This is a completed
  P34 isolation, not a task-green relabeling.
- A supplemental Ruff-format audit found `37` changed files that the current formatter would
  rewrite; `34` of those exact files were already format-red at the base. Three task-authored
  cosmetic diffs remain: line wrapping in `tools/lib/timing.py`,
  `tests/repo_quality/tools/test_timing.py`, and
  `tests/repo_quality/tools/test_unified_cli.py`. They were discovered after the reviewed source
  freeze and are recorded as cosmetic debt under E11 rather than repricing all reviews. They do
  not change behavior, typing, denominators, or artifacts.
- `uv run polisyos-tools architecture guardrails check` returned `1` on the same runtime-HTTP
  deep-import baseline drift recorded during Parts A/B. The exact isolation command
  `git diff --exit-code 4b9e76f20..HEAD -- src/polisyos/runtime/http
  architecture/baselines/imports/deep_import.json` returned `0`; no baseline sync was performed.
- `git diff --exit-code 4b9e76f20..HEAD -- src` and whole-range `git diff --check` both returned
  `0`. No byte under `src/polisyos/**` changed, so no deployment identity, semantic denominator,
  or governed artifact replay moved. Full backend/CI parity and the expensive GY replay were not
  run: the verified blast radius is tools/docs only, while Part C explicitly closed negative.

## Whole-review Part A evidence reconciliation

- Atlas receipt line 48 is corrected from the single-file collection count to the exact two-file
  command denominator: `30` frontend-disposition tests plus `37` status-retirement tests equals
  `67`; no suite was rerun. The stale 29-test status placeholder lane is removed because its
  historical duration does not identify today's 37-test workload; the exact combined 67-test lane
  retains current Atlas Python-governance coverage.
- The task-supplied completed N11 closeout process walls are bound to exact timing lanes below. They
  are input receipts, not new local executions, and remain distinct from the later committed N11
  measurements already present in the catalog.
  - `quality.validation.check_layer3_gy_confidence_ledger:write`; command `.venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --write`; samples `1086000ms`, `951000ms`.
  - `quality.validation.check_layer3_gy_confidence_ledger:check`; command `.venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --check`; sample `951000ms`.
  - `quality.validation.check_layer3_gy_confidence_ledger:corrupt-field-drift-check`; command `.venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --corrupt-field-drift-check`; sample `937000ms` for the 49-case corruption wave.
  - `quality.validation.check_layer3_gy_confidence_ledger:warm-closeout`; command `.venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --warm-closeout`; sample `975000ms`.
  - `quality.validation.check_layer3_gy_confidence_ledger:cold-rederive`; command `.venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --cold-rederive`; sample `952000ms`.
- Catalog evidence is now positional: each literal sample has one same-position source reference,
  narrowed to the receipt line or range that names that workload and contains that duration.
  Repeated references intentionally bind multiple samples recorded together on one receipt line.

## Historical timing receipt workload normalization

The following lines introduce no new measurements. They make each historical receipt's already-named workload explicit as the exact direct action flag so the catalog can bind one sample to one workload rather than to a pooled prose range.

- `quality.validation.check_layer3_gy_depth_n_universality_contract:check`; command `.venv/bin/python tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py --check --output-format json`; sample `87343.036ms`; origin `docs/superpowers/plans/2026-07-20-gy-n11-honest-confidence-ledger.md:787-788` (the independent depth-N check).
- `quality.validation.check_layer3_gy_depth_n_universality_contract:write`; command `.venv/bin/python tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py --write --output-format json`; samples `3660436.012ms`, `1613412.167ms`; origin `docs/superpowers/plans/2026-07-20-gy-n11-honest-confidence-ledger.md:787` (the two depth-N writer runs).
- `quality.validation.check_layer3_gy_generation_cycle_disposition_ledger:check`; command `.venv/bin/python tools/quality/validation/check_layer3_gy_generation_cycle_disposition_ledger.py --check`; sample `101480ms`; origin `docs/superpowers/journals/2026-07-14-gy-n10-stage-4.md:2547` (the canonical ledger check).
- `quality.validation.check_layer3_gy_confidence_ledger:check`; command `.venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --check`; sample `898666.254ms`; origin `docs/superpowers/plans/2026-07-20-gy-n11-honest-confidence-ledger.md:771-772` (the independent recomputing check).
- `quality.validation.check_layer3_gy_confidence_ledger:source-flip-mutations`; command `.venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --source-flip-mutations`; sample `844533ms`; origin `docs/superpowers/plans/2026-07-20-gy-n11-honest-confidence-ledger.md:756-757` (the 17/17 source-flip lane).
- `quality.validation.check_layer3_gy_confidence_ledger:write`; command `.venv/bin/python tools/quality/validation/check_layer3_gy_confidence_ledger.py --write`; samples `1173279.650ms`, `1111911.306ms`; origin `docs/superpowers/plans/2026-07-20-gy-n11-honest-confidence-ledger.md:771-772` (the two dependency-ordered final N11 writes).
