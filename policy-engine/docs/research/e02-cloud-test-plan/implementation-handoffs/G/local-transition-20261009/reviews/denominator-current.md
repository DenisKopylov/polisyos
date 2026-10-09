# E02 current denominator and admission boundaries

Audit basis: current G branch `codex/e02-integration` at `dee58973f7673299070b7c7374f419b0adb8175c`, tree `4caee698bd9a6c61277a1608bb38376b669f0372`; published-main anchor remains `198076863e143dea9f89f02734b13d50dae3eed5`. This is a read-only current-truth index. The complete compact ID-to-route recount is in the adjacent `denominator-current.json`; original criterion prose remains in its canonical source and is not copied here.

## Full recount

Independent machine reconciliation of `closure-decisions/coverage.json` with `connected-closeout-plan-2026-10-08/findings.json` found identical sets of **282 unique IDs**, across **127 bundles** and **291 original criterion occurrences**. The occurrences resolve to 225 pointers in `B_r19` and 66 in `LA_r09`. The connected plan’s independent coverage receipt records 291 original block hashes matched.

| Original unit | Bundles | IDs | Criterion occurrences | Author proposed closed / limited / held / open |
| --- | ---: | ---: | ---: | --- |
| A | 13 | 34 | 35 | 5 / 23 / 1 / 5 |
| B | 25 | 60 | 60 | 47 / 7 / 4 / 2 |
| C | 33 | 54 | 59 | 31 / 12 / 11 / 0 |
| D | 17 | 45 | 46 | 39 / 1 / 5 / 0 |
| E | 22 | 54 | 55 | 43 / 9 / 2 / 0 |
| F | 17 | 35 | 36 | 33 / 2 / 0 / 0 |
| **Total** | **127** | **282** | **291** | **198 / 54 / 23 / 7** |

These are three different ledgers:

- **Author proposals:** 198 closed, 54 limited, 23 held, 7 open. They record the authors’ recommended outcomes.
- **Prior historical ledger:** 9 closed, 260 partial, 12 held, 1 open. It is the pre-existing status, not a new recount or acceptance of the current candidate.
- **Current G adjudication in the connected plan:** all **282 `not_adjudicated`**. The analysis receipt reports `new_formal_closures=[]`; the latest incoming handoffs also report empty closure IDs. No new formal finding closure is established here.

Source admission is another separate decision. G already has bounded source admissions in its history, including the B190 supplier at `f2c102fa2ee588b91b2baaa8c9d1c393699838c0` and F source `852cc3707bfc7dee132ec07a9ed5adcb5911fdf2`. Their accepted code scope does not close a whole finding or change the 282-row adjudication state. **B198** is a prior historical closed regression and also has an author `closed` proposal; the new-sweep row remains `not_adjudicated`. Preserve the historical closure and its regression; do not treat the new-sweep bookkeeping row as reopening. Reopen only for a new defining-property counterexample.

## Complete execution route

Use the existing machine route for every ID, not just the 84 author-limited/held/open rows. In the 282 rows, the next-decision partition is 198 exact-scope adjudications after source admission, 83 named residual decisions, and one selected minimal subject-join implementation. Task links overlap: 206 rows point to Q0, 83 to residual resolution, and one to the minimal producer task; eight rows have more than one route. There are **319 task links** across the **23 tasks**, so route counts must not be summed as if they were findings.

1. Preserve the original criterion pointer, source identity, historical ledger value, author proposal, current G status, and all `next_tasks` for each ID. The JSON index records each row’s original document/line/hash pointers without duplicating source text.
2. Run Q0 for exact original-scope G adjudication once the relevant source is admitted. A proposed-closed row may already have enough code and evidence; verify that against the selected source and actual consumer. Do not automatically rerun work merely because an author proposed closure, and do not automatically close it from the label.
3. Use Q1 to select exact compatible source DAGs, parents, trees, complete path/blob manifests, and canonical owner choices before composing a mechanism. Keep separate supplier/source candidates distinct until their contract, test, generated, and public-surface companions are reconciled.
4. Execute the named mechanisms in `tasks.json` with its dependencies and conditional inputs. Conditional law, authentic source, tenant, workload, or production facts gate only criteria that require them; continue independent portable mechanics and negative controls.
5. Repeat only consumers whose upstream contract actually changed. Freeze the selected source, finish independent reviews, then run the broad portable replay once. Keep read-only production-dependent checks local and only for criteria that require them.
6. Record code acceptance per immutable candidate and finding closure per original criterion. A missing input gets the exact absent artifact/authority owner and a supported bounded path; it does not become a reason to requeue unrelated tasks.

The exact per-ID routes and task dependencies are in `denominator-current.json` and the canonical `tasks.json`. Its tasks span source selection (`Q1`), per-ID adjudication (`Q0`), source verification (`R1`), runtime/source/profile and identity work (`R2`–`R4`, `I1`–`I4`), semantic and producer decisions (`S1`–`S3`), served consumers (`V1`–`V7`), protected authority checks (`T1`–`T2`), and generated/installed surfaces (`Q2`).

## Latest incoming technical deltas — evidence navigation only

The following refs are locally available as remote-tracking refs and are not ancestors of the audited G head. Their handoffs themselves deny G source admission/formal closure. They must be reviewed at their immutable candidates if admitted; the reported results are not silently promoted to G acceptance.

- **L01** `25333d87e3e32795e2e89288d5f2bd70e8e756c9` (tree `760dcf9b09373e36308db5b2a5da7d24aa30489d`), facts candidate `9f6841f877566a70aa559fc490c382a437f5619c`. Three alias-bound cached L6 controls match the September GY content-domain record. This does not establish release, custodian, currentness, or served root. I3’s readiness ref is for another snapshot root; Legal locator/size/mtime agreement is not content or vector identity; B194’s evaluator/law/draw basis is absent; B56 lacks a qualifying named shared workload, with a portable synthetic path available through the selected C01 permit. Authentic consumers remain UNRUN. Finding outcomes did not change.
- **L02** `c3b171010a7ce30b12d1dbd497eb646b9147afa0` (final source-root handoff; evidence `18be88029cc8602709ba821bff51f46e3669c242`) ran against exact G `dee58973`. The loader read three selected actual controls and returned a typed L6 bundle. Missing-Lex-map and forged-hash negatives refused. It does not compare raw final-manifest descriptors or establish currentness; actual serving PID/executable/root/profile/context is `not_established`. No pytest/JUnit ran; authentic POST/N5/CAS/GET remain UNRUN. This is a bounded reader preflight, not authentic runtime acceptance.
- **ORCH02 C06-DFK** source `3a0d5549606087c1d4e8d344ed474c0dfb4cbe5d` is based on current G `dee58973`; receipt `6c565cd65899d91bda370416651555eee143e194`. Its bounded census/CLI adoption evidence includes 45 native PASS, six independent real-Git/public-CLI PASS, and six matched historical-classifier property FAIL. External/ignored/binary/historical absence and installed-wheel/archive membership stay limited or UNRUN; architecture remains FAIL. `source_acceptance=not_admitted_by_G`.
- **ORCH02 C06-CAN** source `2762cec321d0cc78874abb986736dab54e2fb189`, receipt `328d91dfee230aeb67ad1168e83b2ece8183d725`, also uses G `dee58973`. It carries a bounded persisted IR-profile/CAS reader candidate and explicit Core compatibility seams. The handoff distinguishes its 14-case matrix, 50 native cases, and 11 independent boundaries; do not aggregate those into an unqualified whole-package PASS. C02/G compatibility decisions and global architecture remain open; source is not admitted.
- **ORCH02 C05/C12** are source candidates `5ccbfa15c5671623a4c1ff7a3145460c5ca5a857` and `a47ec396228d3a8be63cb6c2c5ad3a1f17ee20e7`, with own-base lineages. Their focused positives and typing results coexist with full architecture FAIL; C05 invocation is unresolved and C12 terminal capture is ERROR. They are not G admissions. The coordinator `d9a4b671c99bf6a5435fde4fc873092e03b451b0` reports no selected integrated composition, broad replay UNRUN, `source_acceptance_issued=false`, `formal_closure_ids=[]`, `integrated_PASS=false`.

## Source boundary and limits

Denominator source pins: `coverage.json` and the full original criteria are pinned by `connected-closeout-plan-2026-10-08/inputs.json`; the plan base is `6f3983466f1eca14b510c4f5006fab5092d418d3`, while current G is later. The per-ID JSON index is derived navigation, not authority. It is not a source-code review, a test receipt, a new scientific/contract decision, or a closure pack. Current incoming L01/L02 and ORCH02 evidence is named separately precisely because those updates postdate the connected plan’s original analysis cut.

Pattern pass: P01/P02/P03 require actual producer → persisted artifact → bridge → consumer/surface; P05/P09 preserve authority and status; P27/P31 keep canonical owners and supplier history; P29/P32/P33 require behavioral positive and adversarial removal; P35 protects the full 282/291 denominator; P37/P38 distinguish declared input from the real predicate; P40 prevents endless instance patches; P41 requires exact slice-base and complete input denominator before attributing an inherited red.
