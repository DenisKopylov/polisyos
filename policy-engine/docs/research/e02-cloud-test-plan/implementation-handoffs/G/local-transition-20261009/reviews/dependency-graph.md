# E02 local-transition DAG and merge-footprint review

Review base: G `dee58973f7673299070b7c7374f419b0adb8175c` (tree `4caee698bd9a6c61277a1608bb38376b669f0372`), branch `codex/e02-integration`, read-only. The incoming-head list is pinned by `ref-census.json` (SHA-256 `c9e3a90c06fc0debb24bdaf7ea8f145fb7a0598330414bec5dda7e1d3f2b6397`); it names ten changed heads. I also included the requested unchanged C10 and C13 heads; C11 is already represented once at its newer census head. The review reads exact Git commit/tree identities and handoffs. It does not infer source ownership from summaries or ref spelling.

## Finding

Keep `dee58973` as the integration base. There are three distinct cases:

1. **Exact current-G descendants / path-safe source carriers:** C06 DFK (`6c565c…`, source `3a0d55…`), C06 CAN (`328d91…`, source `2762ce…`), and C05's G-only proposal (`42987b…`) descend from exact G. They preserve history and can be integrated with ordinary append-only merges after G chooses their explicit public contracts. Their source edits are tiny, while their receipt-bearing topic tips are much larger because they carry docs.
2. **Older-G descendants with no changed-path overlap:** C10 (`8997d7…`), C11 (`f42540…`), C13 (`1c8c3f…`), ORCH02 coordinator (`d9a4b6…`), and ORCH04 coordinator (`91f458…`) branch from G `0321633c…`, which is an ancestor of current G. Full-history merges are structurally feasible: the complete tree walk found no changed-path intersection against current G's 59-path post-032 delta. Source capability acceptance remains separate; merge only after exact source/cumulative-footprint review and preserve each branch's source pins.
3. **Foreign or stale own-base / prepared branches:** C05 recovery (`eee090…`) and C12 recovery (`fcf164…`) do not descend from current G and diverge from the published `main` base. Against that common base, their current topic tips carry 458 and 350 changed paths respectively, with 6 and 5 path collisions against G, and every collision has a different final blob. Do not merge either whole branch or cherry-pick a leaf by summary. The prepared B source/handoff objects are present locally but unreferenced; the full prepared handoff tip differs from current G across 5,022 paths (one divergent README collision), despite a bounded 18-path source/test/companion slice. Re-express only an accepted, exact source delta on current G.

Thus, *structurally mergeable* is not synonymous with *code accepted*, *capability complete*, or *finding closed*. No formal G closures are implied by any author's recommendation or receipt.

## Whole-tree denominator

For each pinned topic head, the calculation used `git merge-base <G> <head>` and then enumerated **every** path with `git diff --no-renames --name-status <merge-base> <endpoint>` for both G and the topic. Intersections were calculated from the complete path sets; each intersecting path's endpoint blob IDs were compared. Categories in the table are mutually exclusive: tests, docs/`_build`, release/config, product source, other. The full exact counts, path intersections, blob identities, trees, source parents, and local-only object checks are in adjacent `dependency-graph.json`.

| Topic | Exact source candidate → receipt head | Common-base delta at receipt tip | Intersections with G delta | Read |
|---|---|---:|---:|---|
| C05 source | `5ccbfa15` → `eee090e3` | 458 = 397 docs + 44 product + 15 tests + 2 config | 6, all divergent | Hold whole head; see supplier and public-facade contract below. |
| C05 G proposal | `42987be6` → same | 31 docs | 0 | Exact-G docs-only proposal; it is not source implementation or acceptance. |
| C06 DFK | `3a0d5549` → `6c565cd6` | 181 = 178 docs + 1 product + 1 test + 1 config | 0 | Exact-G child; source candidate itself is 3 paths. Preserve whole topic if accepted. |
| C06 CAN | `2762cec3` → `328d91df` | 85 = 81 docs + 2 product + 1 test + 1 config | 0 | Exact-G child; source candidate itself is 4 paths. Preserve whole topic if accepted. |
| C12 source | `a47ec396` → `fcf164eb` | 350 = 287 docs + 45 product + 15 tests + 3 config | 5, all divergent | Hold whole head; required producer, encoder, request, and served-reader dependencies are absent from G. |
| C10 | `e6854a70` → `8997d7f5` | 372 = 357 docs + 8 product + 4 tests + 3 config | 0 | Source delta is 15 paths; later 357 paths are documentation/receipts. Bounded source can be reviewed separately from served capability. |
| C11 | `03698439` → `f425407e` | 483 = 460 docs + 12 product + 9 tests + 2 config | 0 | The source candidate's G-032-to-source footprint is 271; the current receipt tip adds 212 paths. Neither number can be substituted for the other. |
| C13 evidence | G `0321633c` → `1c8c3f3e` | 69 docs | 0 | No code delta; receipts remain qualified to G-032 and preserve packaging failures. |
| ORCH02 coordinator | `50feba75` → `d9a4b671` | 175 docs | 0 | Metadata/evidence only; source acceptance and closure IDs explicitly absent. |
| ORCH04 coordinator | `be3e513e` → `91f458f3` | 232 docs | 0 | Coordination/custody only; no product source. |
| L01 update | `25333d87` | 18 docs | 0 | Metadata/evidence update; authentic input limitations remain. |
| L02 update | `c3b17101` | 35 docs | 0 | Metadata/evidence update; authentic served positives remain unrun. |

The source-candidate footprint is not always the tip footprint. For C05 and C12, the declared own-base candidate diffs are 134 and 91 paths, but the exact source candidates compare to current G's common ancestor at 221 and 248 paths; their receipt-bearing topic tips compare at 458 and 350. These are different denominators, not contradictions. C10's 15 and C11's 271 are source-candidate footprints; 372 and 483 are current receipt-tip footprints. Do not report a leaf's small diff as the complete branch or source history.

## Cross-cutting blockers and what is actually missing

### C05: selection and compatibility, not absent Git objects

The 14 supplier paths are not 14 absent files. Exact G, CAT, and C05 trees contain 13 of them with different blobs; `data_forge/domains/catalog/_resources.py` exists only in G. Preserve that G-only resource behavior. Choose the other 13 pathwise by symbol/contract and keep the canonical `CatalogSelectionError` binding. Four public-facade companions are required because the proposed loader imports public `polisyos.ir.FetchRequest`; the owned patch alone leaves that import unavailable. The recorded apply checks prove applicability only. After a written supplier table and four-facade choice, apply the proposal to current G, then run the affected source consumers and public import tests. C10 still needs the admitted `CatalogRunProfile` and refusal/output preservation on the actual service route. This is a local G contract/source decision; it does not need a restarted cloud owner.

### C10/C11: code-bearing slices versus the served feature

C10's source proves bounded recursive routing/checkpoint mechanics and owner-store binding; its branch adds 15 source/test/release paths. Ordinary RunDetails parsing, DTO/facade/generated client, fresh persisted GET reader, constructor census, and browser-positive companions remain missing. C10 should precede any dependent served consumer work, but keep `consumer_missing`/`verification_missing` explicit until those companions exist.

C11's exact B114 source and cumulative prior fixes are reviewable on the source pin; do not reduce its source history to the last four-path commit. Broader E/F actual Node/Search composition remains separate: the exact selected receiver APIs do not match the supplied join fixture, and the required frozen vector-search profile is unavailable. That does not invalidate bounded B114 source evidence. Core DTO/served reader and selected join/profile must be settled before asserting a full orchestration capability. The actual C11 source candidate is a G-032 descendant; normal merge can preserve all commits, but accepted source and unrun joined route must remain separate.

### C12: a real dependency chain, not just a missing production input

G lacks `legal/embedding_projection.py` and the required `kernel/embeddings.py` generation/encoder/index identity APIs. The candidate also needs existing Legal read-API and `lex.knowledge` facade exports. Its current served `LexSearchRequest` carries no immutable profile/intent or trusted encoder, and the caller does not pass them; broad error-to-empty projection could erase `LegalQueryProfileError.code`. Before a current-G port, select the DFI→CAT→Legal producer ancestry, exact encoder/profile contract, request-intent binding, trusted C10/A service path, and response/error surface. Then port against current-G preimages and test missing/stale/mixed generation plus served refusal. L01/L02 do not provide production pairing/currentness: their matching read-only descriptors and control-loader negatives are bounded facts, while live serving root/currentness and authentic POST/N5/CAS/GET remain `not_established`/`UNRUN`. Portable source work should continue without claiming that authentic evidence.

### C06 and packaging

DFK requires a G decision between adopting the bounded schema-FQN census with public CLI/lifecycle/manifest/version companions, or selecting a canonical generic parser owner. CAN needs a Core/IR decision: preserve or refuse unsupported `Mapping` values for existing `ArtifactWriteOptions`, including authority, tenant context, same-input closure and warnings; keep strict history rejection and avoid a new duplicate DTO. These are exact-G source branches with no code path collision, but the exposed contract and companion are still G's decision.

C13's package evidence is not a waiver. The existing packaging test and `ops/cloud/gcp/package_repo.sh` must include all eleven existing required assets while retaining production exclusions. Fix the actual resource chain; do not weaken the test or call the current archive results PASS. Re-run packaging after source freeze.

## Local-only/unreferenced input checks

- B prepared source `1e18a965` and handoff `a0ee451f` resolve as commit objects (`1e18` tree `e711617c…`; `a0ee` tree `67725797…`) but neither is contained by a current local, E02, or `origin` ref. PR55's visible topic remains `origin/codex/e02-B-current-coordination` at `53b14a6e…` (tree `568e2e42…`). The handoff names G980 as the source integration base and declares an 18-path forwarded source/test/companion delta; its native gates are still UNRUN and code acceptance HELD. Current G shares merge base G980 with the local object, but the complete B handoff tip carries 5,022 paths relative to that base and conflicts on `policy-engine/src/polisyos/foundry/methods/compiler/README.md`; do not merge or publish that unreferenced whole topic. Recover the bounded source into current G only after fresh exact-source intake and required verification.
- The fetched local origin snapshot contains 150 `codex/e02-*` refs. It has no exact `ORCH01` or `C01`–`C04` topic ref. This is a ref-availability statement only; it does not establish that supplier commits are absent. C05's compared supplier trees and ancestry are locally available, so no new owner chat is required for the 14-path choice.

## Recommended append-only intake order

1. Keep all input refs/source pins immutable. Integrate the exact-G docs-only C05 proposal `42987…` by fast-forward first if its custody metadata is useful; it is a source decision packet, not the implementation.
2. Merge the exact-current-G DFK and CAN topic histories one at a time after their narrow contract/surface decisions and non-author reviews. DFK→CAN is a convenient order; their code deltas are disjoint. Re-run only affected census, public-option and consumer checks after each actual contract change.
3. Merge C10's full receipt-bearing branch from G-032, preserving its history, after source review; then merge C11's full branch, also preserving history. No path collision was found with the current G delta, but each new contract/API companion may require fresh defining-property tests. Keep the joined Search receiver/profile as a separate unmet capability until exercised.
4. Integrate ORCH02/ORCH04 coordinator, C13, L01 and L02 documentation/evidence as independent metadata-only merges, always preserving their source-qualified pins and explicit FAIL/UNRUN/`not_established` states. They do not accept code or adjudicate findings.
5. Keep whole C05/C12 branches out of G. Resolve C05 suppliers/facades and C12 producer/encoder/request/served-reader contracts in a unified current-G composition, then create small current-G commits from selected postimages, review the actual integrated diff, and run its affected consumers.
6. Treat B's unreferenced `1e18/a0ee` as recovery material, not as a publishable branch. Reconstruct a new exact-current-G candidate from its 18-path source slice only after executor/admission recovery, exact source checks and reviewed companions. Do not synthesize a “green” result for missing native tests.
7. Repair the real packaging companions, complete contract joins, freeze the resulting G source, finish independent source reviews, then run the single expensive integrated replay. After any contract modification, repeat only directly affected consumer/defining-property checks; avoid restarting broad per-agent waves.

Code source acceptance, finding adjudication, and formal closure stay as separate decisions. The source reviewers' bounded GO verdicts are not G acceptance. Every failing gate must retain its exact owner/source/output and must not be inherited or cleared by topic merge alone.

## Integration-branch observation during this review

The shared integration worktree was clean at `dee58973` when this audit started. During the audit, another integration activity advanced it to `e92487c58d77481f05450085e2b78f6e2478b512`; `origin/codex/e02-integration` still pointed at `dee58973`, and status showed a clean attached branch ahead by 28 commits (merged history contributes to that count). The full `dee58973..e92487c` path denominator is 328, all under docs/handoffs, with zero product, test, or release/config paths. The five first-parent intake commits cover L01, L02, ORCH02 coordinator, C05 G-proposal, and C13 evidence. I did not create or alter these commits. The merge table and ancestry findings above remain pinned to `dee58973`; re-check ancestry from `e92487c` before the next intake, and do not re-merge those five carriers.

## Read-only boundary

This audit only read refs, commits, trees and committed handoffs, and wrote the two adjacent ignored reports. It ran no product tests, installed no dependencies, accessed no production payload, created or moved no refs, and changed no tracked source. `dependency-graph.json` stores the exact computed per-topic counts and all collision path/blob comparisons; it is the machine-readable denominator behind this report.
