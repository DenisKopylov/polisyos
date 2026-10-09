# Carrier and transport audit — ORCH02, ORCH04, C13

Audit date: 2026-10-09. Read-only review from G checkout `/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos`.

## Decision

- **ORCH02 coordinator `d9a4b671…`: GO for a metadata-only merge.** The carrier is 11 commits after G base `0321633c…`; its net delta is 175 added files (3,804,972 blob bytes), all under `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/`. There are no product `src/`, `tests/`, architecture, tools, lock, or ops changes. Its own final handoff says `source_acceptance_issued=false`, `formal_closure_ids=[]`, and `integrated_PASS=false`. Merge it as custody and source-qualified evidence only. Do not merge the separate C05/C06/C12 candidate-topic tips based on this carrier's presence.
- **C13 receipt `1c8c3f3e…`: GO for a metadata-only merge, with its G032 source pin kept prominent.** Two commits, 69 added files (2,337,113 bytes), all below the C13 handoff/evidence directory. No product source or test path changed. The receipt is tied to G `0321633c…` / tree `fd0b6e71…`, reports no G source acceptance and no formal closure. It is useful evidence; it is not the final portable replay.
- **ORCH04 coordinator `91f458f3…`: HOLD for a wholesale merge as-is; its unique evidence is valuable and source-scoped, but it duplicates the entire post-032 G documentation snapshot.** Four commits, 232 added files (2,320,839 bytes), all under docs. The coordinator embeds 59 byte-identical copies of files already present in current G `dee58973…` (56 nonempty blobs plus three empty output files), under `evidence/current-G-observation/source/`. It also has duplicate captured outputs inside the carrier: 75,429-byte `stdout.txt`/`observations.json`, 11,198-byte environment-origin outputs, and a 49-byte fsck stderr. Since the common base is G032, a three-way merge will keep G's canonical paths and also add these copy paths; it will not replace/delete the originals. Ask the carrier owner to replace the 59-file snapshot with `path@sha` references and deduplicate identical outputs, then accept the compact coordinator/evidence delta. This is a documentation-custody issue, not a reason to reject its reported source results.

The three coordinator commits are independent siblings off G032; none is an ancestor of the others. Their changed path sets do not overlap relative to G032. C13 can be merged independently before ORCH04. All three audit targets are **documentation/evidence carriers**, not accepted source branches.

## Exact G and carrier pins

At review: G branch `codex/e02-integration`, HEAD `dee58973f7673299070b7c7374f419b0adb8175c`, tree `4caee698bd9a6c61277a1608bb38376b669f0372`, clean and tracking the same local `origin/codex/e02-integration` SHA. G032 is `0321633c0e6d9a87bccfbbe889a4998934c52dd3`, tree `fd0b6e711d872afe4f74c371d28b01862af0ae7e`. G032→current G changes 59 paths, all documentation; there are zero product source/test/architecture/tool/ops changes in that interval. No network fetch was performed for this audit; “remote ref present” below means the existing local remote-tracking ref points to the named SHA.

| Carrier | Existing origin ref / exact head | Tree | Parent / ancestry from G032 | Net delta from G032 |
|---|---|---|---|---|
| ORCH02 | `origin/codex/e02-C-orch02-recovery-coordination` / `d9a4b671c99bf6a5435fde4fc873092e03b451b0` | `48ded41b6b62bb0000627b30ba78441844c0a58a` | 11 commits; merge-base G032 | 175 docs/evidence additions |
| ORCH04 | `origin/codex/e02-ORCH04-recovery-20261008` / `91f458f37c67fb3620b0107735535629a8b60ede` | `0eb25a86f537d1fbcc62eb108e3b211aa6974de4` | 4 commits; merge-base G032 | 232 docs/evidence additions |
| C13 | `origin/codex/e02-C13-recovery-20261008` / `1c8c3f3e068a2bd86dc88d4918621149aaf3179c` | `010cec28d2884d626ba7e7ed5ef101fcbacc2ccf` | 2 commits; merge-base G032 | 69 docs/evidence additions |

C13 is not an ancestor of ORCH04's coordinator head in the fetched graph, although ORCH04's handoff names the exact C13 receipt. They are separate carriers; preserve that distinction in integration history.

### Leaf source and receipt refs named by carriers

The listed source and receipt commits exist in the current G object database; source trees, receipt trees, and the published branch tips match the exact SHAs in the carrier JSON. Their existence does **not** mean G has accepted their code.

| Slice | Source commit / tree | Published receipt head / tree | Existing origin tracking ref | Qualification |
|---|---|---|---|---|
| C05 | `5ccbfa15c5671623a4c1ff7a3145460c5ca5a857` / `9633ae3e5fdbdcc6a6a76af3d7ef29bdaa12fd09` | `eee090e345d1121d3d53cdd93a7ab32f818d5ef7` / `4a9af5064f47b795bfb5d00533b19f2e39bcb1c9` | `origin/codex/e02-C-orch02-c05-recovery` | 119 scoped native passes; full architecture family still has failures; G-port remains proposal; 14 supplier paths held. G acceptance false. |
| C06 DFK | `3a0d5549606087c1d4e8d344ed474c0dfb4cbe5d` / `1e2e7c6ca7948f3c2b771af431bd0d73510fec3a` | `6c565cd65899d91bda370416651555eee143e194` / `c2740b7eb4e0b49cf30fec1582545bea54593a79` | `origin/codex/e02-C-orch02-r2-c06-dfk-g` | G-based candidate; 45 scoped tests plus Git CLI/removal evidence. Not source-accepted. |
| C06 CAN | `2762cec321d0cc78874abb986736dab54e2fb189` / `70051ecf56771a59c0ecc468e975e7878b66f728` | `328d91dfee230aeb67ad1168e83b2ece8183d725` / `f499af13ffb094745d0f58a9013b768a953c2390` | `origin/codex/e02-C-orch02-c06-can-r2-g-compatible` | G-based source; detailed handoff has 50 named checks plus 11 separate actual-CAS residual witnesses. Compatibility/Core/API choice remains with G; do not sum unlike waves into one acceptance count. |
| C12 | `a47ec396228d3a8be63cb6c2c5ad3a1f17ee20e7` / `2e40b42e506b5dbae790f809368c308631cdaac4` | `fcf164eb1c5bb54786462e67ba2537313b33b90d` / `e0ad136df2f004bc87cdb596c3955a88913b3ff1` | `origin/codex/e02-C-orch02-c12-recovery` | 58 scoped checks; type repair delivered, architecture remains red and invocation evidence is limited/ERROR. No G acceptance. |
| C10 | `e6854a70a6d2ae9e4df82351925d7cabe1e9e5e8` / `6506a68152d7a957fc7762e9846a72e7ab98d557` | `8997d7f5f72f9e09ef928ac13e9dab4c9ffdcb6e` / `124dc6e5746716ade61e5d9d6d8633009db48315` | `origin/codex/e02-C10-recovery-20261008` | Fresh current-head/CAS and capsule results are bounded; ordinary persisted served/browser positive remains absent. Reserved to G. |
| C11 | `03698439abfb1cb59f763397a182d8e0e393d40d` / `dde25e8efa4a8ce5322bdcad176720fa0894a635` | `f425407e9f2228300905831d44bf179bb797e69d` / `85c1e39a351cde922f3af3c5a220eab6cad84e72` | `origin/codex/e02-C11-recovery-20261008` | Fresh bounded native/GP checks; selected wider connected receiver is UNRUN; source acceptance reserved to G. |
| C13 | G032 `0321633c…` / `fd0b6e71…` | `1c8c3f3e068a2bd86dc88d4918621149aaf3179c` / `010cec28d2884d626ba7e7ed5ef101fcbacc2ccf` | `origin/codex/e02-C13-recovery-20261008` | Read-only source receipt only; G032 profile. |

The four ORCH04 historical unpublished commit IDs reported as unavailable (`e2122918…`, `a92f5793…`, `f9903d8e…`, `996dea4e…`) are also absent from this G object database. Treat this as “not locally present and unavailable on the tested channels reported by the carrier,” not global nonexistence. Do not invent replacements from summaries.

## What the evidence says

### ORCH02

The final handoff explicitly records `selected_integrated_composition=null`, `broad_portable_C13_replay=UNRUN_await_selected_G_freeze`, `source_acceptance_issued=false`, empty formal-closure IDs, and `integrated_PASS=false`. It includes exact source/DAG receipts, independent bounded reviews, admission/readback records, and owner packets. It is safe to preserve as documentation, while all four candidates remain separate source decisions. Its latest published tips are source-plus-receipt topics, not the metadata coordinator branch; merging a leaf ref would bring unaccepted implementation code.

### ORCH04 and C13

ORCH04 pins canonical source G032/tree `fd0b6e71…`. C10 and C11 source/receipt commits are independently available on existing origin tracking refs and exact tree pins match. The earlier four refs and full export are not locally recoverable from the paths tested here. The coordinator reports an ordinary export at `/workspace/ORCH04-export/ORCH04-recovery-20261008.tar.gz`, plus `EXPORT-RESULT.json` and `POST-EXPORT-CHECK.json`; those three exact paths do not exist in this local G environment. The tracked handoff supplies no direct downloadable URL or archive SHA to verify here. Thus the stated 5,816-member archive integrity result remains a coordinator receipt, not a G-side archive readback.

C13 check table is source-qualified to G032/tree `fd0b6e71…` for each test. It records: GCM query/CAS 1 PASS; current DoWhy native 20 PASS; genuine locked worker 25 PASS; Node client 9 PASS; dashboard contract 1 PASS; dashboard typecheck/build PASS; installed source-wheel 3 PASS and rebuilt-sdist-wheel 3 PASS with 911 observed origins per profile and zero origin violations. Native packaging is **6 FAIL / 4 PASS**, and the actual extracted GCP archive wheel build fails because `metrics_map.yaml` is missing. GP readiness is import-only, not GP numerical verification. Portable replay and the complete API/issuer/consumer census are UNRUN pending G-selected source freeze. The exact source wheel, rebuilt wheel, and sdist files named under `/workspace/ORCH04-evidence/c13/...` are not present in local G.

Therefore the 6/4 package failure and the missing archive asset must remain visible. The installed wheel/sdist results do not establish that the GCP archive is publishable, and C13's `PASS` labels do not close C10/C11 composition or source acceptance.

## Recommended integration handling

1. Merge ORCH02 carrier as docs/evidence only; keep its source candidates and quality failures in the G queue.
2. Merge C13 receipt independently as docs/evidence only; retain source `0321633…`, profile-specific counts, `6 FAIL / 4 PASS`, and UNRUN boundaries. Do not describe it as a new final-composition replay.
3. Ask ORCH04's canonical coordinator to republish a compact carrier that points to current G docs by `path@sha` rather than embedding the 59-file snapshot; remove exact duplicate captured outputs or justify them as separate deciding evidence. Keep the 173 unique ORCH04 handoff/evidence files and exact per-leaf source pins. Until then, merge only a reviewed subset if a specific receipt is needed, with an explicit pointer to its unchanged original path.
4. Do not merge the ORCH02 leaf source heads, C10/C11 implementation commits, or any wider source branch merely because the carrier reports bounded GO. G code acceptance and finding closure are separate and remain unissued.

No tests, dependency installs, fetches, ref updates, product edits, merges, or cleanup were performed. Git inspection and read-only JSON/path checks only. Working tree remained clean.
