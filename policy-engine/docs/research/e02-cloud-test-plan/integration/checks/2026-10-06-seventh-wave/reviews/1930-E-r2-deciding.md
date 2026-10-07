# E PR38 r2 — independent source/output identity review

## Scope and pinned identities

This is a read-only evidence/source-output review, not product/code acceptance and not finding closure. I read the committed PR38 r2 entry and `final-handoff-v2.json`, the a9 case/input indices, corrected-wave receipt, independent wave audit, and actual moderate JUnit/stdout objects from Git.

- Documentation candidate: `e9cb425e4dfe888720f93eb84f1667f24a8a92c4`, tree `d884554723bb66e83f5df467fc95766fd90f7bda`.
- Numerical source: `a9f78817c873be5b35a08155f2593b229d9fdbb6`, tree `c02e043c3e1c8222c28aa71187fa8db4e2fdeea7`.
- Wave evidence: `ddcdfd9c220ba57e37c8abf52b976a7184c384f9`, tree `1c5e1bd9ecdd619ae99ae978231aa296875bd1b1`.
- All-54 closeout: `9954f394b470961d9e144a557f3cefeb9e0a67b6`. Verified ancestry a9 → ddc → 9954 → e9; the later refs publish evidence/docs and do not redefine the numeric candidate.

Receipt and independent-audit identities agree: publication receipt is 726,367 bytes, SHA-256 `1b690c7c02fd83846b06bc355738929cf50573fd5590ed16d45decc3e84727ca`; independent wave review is 199,695 bytes, SHA-256 `624103ca6fb8889fcb2285fff17a499741eaa12530f7eed3703434a006ce76f9`. The current-case index (`d807bea5…`) binds source a9/tree c02 and 1,445 cases; the input index (`0f6fb47d…`) binds the same source/tree. I verified the listed 37 JUnit/stdout/receipt references against the ddc Git blobs (declared bytes and SHA-256 all match), and independently parsed the seven raw JUnit XMLs. Their 1,445 case identities/outcomes exactly equal the current-case index (no unmatched or omitted rows).

## Numerical result from raw JUnit

The seven actual suites sum to **1,445 = 1,441 PASS / 4 FAIL / 0 ERROR / 0 SKIP**. The four failures are two native `FRC-01` assertions (`test_calibration_time_roles_are_preserved_from_bound_evidence`, `test_missing_calibration_evidence_refs_stays_typed_blocked`) and two A status/reason packet assertions (`test_missing_ref_tier_and_s6_share_named_missing_ref_reason`, `test_resolved_limited_evidence_keeps_floor_failure_reason`). The last case was an actual setup `FileNotFoundError` in the 5e wave and is a measured assertion failure in a9: expected `floor_not_met`, observed `insufficient_history`. The old 5e raw suites had 1,440 cases = 1,086 PASS / 3 FAIL / 351 setup ERROR / 0 SKIP; all 351 setup errors are absent from a9. The three old assertion failures remain and the fourth is newly executed. This is not a blanket inherited-red attribution.

| Suite | Actual cases | Raw JUnit SHA-256 (bytes) | Raw stdout SHA-256 (bytes) |
|---|---:|---|---|
| `pcl-continuous-persistence` | 96 P | `4956493ea0ca0f6632ee1571445ce7578f91eea20b049ca3b4b466aecd21e036` (14,594) | `650187a4ae2a868d13be275796a0d28ad4257a5afeea46b9e46fc9082e9ae4f9` (160) |
| `ddm-runtime-and-facade` | 82 P | `ee44bc3254aa6d4704d4b588acf660e5c76e809d0e672053798d4ac1b195ded4` (12,578) | `4bed8cc624113743771e380f4fea7f09ec8586d03d46684c5c3a9889a2038305` (160) |
| `bkt-frc-s10-and-adjacent-report-consumers` | 311 P / 4 F | `47db97d2898e824976d7cc1d001a12d15e8a1d14c2163a057f0bb69b7422163f` (65,800) | `c47a9a9751a54f1a6f0eee2589c6621780a08ebdbd7cb6f9d0d7c9bbc2d74e85` (10,316) |
| `cal-and-welfare-consumer` | 311 P | `b0b3de528561d7cc2a585f81857594144e889e2dad3d49711c86b576f7deec87` (50,319) | `5a246a72ab9562b113dbce5d049e77a98605c033aaea141fb5e2c7cfc1256175` (400) |
| `mc-joint-law-support-and-scientist-consumer` | 382 P | `9e95e3371eca4bda0f58c8caa0fbcb4acd66ced62ec9d74b2584eeefee0da354` (64,345) | `0fda2cc2089e30da7ede6bbaf014d1489342b59aa23a8fb7a1774df0bb93b299` (1,131) |
| `doe-salib-and-consumer-factory` | 200 P | `f12504acc9fd13725ea15d38d49ea54c5095f234e1ff2aa0adb2983067710847` (33,167) | `39230757cac5941db12fab15e22ab85a0b9a72c43f6cefe35d42fe11d5438dc5` (1,668) |
| `g-checkpoint10-controlplanestore-companion` | 59 P | `b689662164d4795064d5341fd9256482340172f911dfe4048fc5cc7e723d9018` (10,247) | `028dd49c08f9ca3151612e7dd2db85e156b2c618b6b2899f2dfec4d2027564ae` (80) |

Paths are `corrected-wave-a9/checks/<suite>/pytest.xml` and the same suite's `<suite>.stdout.txt` under the committed PR38 r2 directory. The receipt separates 1,438 native outcomes (1,436 P / 2 F) from the 7 A packet outcomes (5 P / 2 F); it has zero unattributed cases.

## Gate outputs and distinct UNRUN scopes

The importer is PASS. The seven product/global gates all have exit 1 and exact deciding stdout/receipt artifacts under `corrected-wave-a9/checks/<gate>/`; refs below are verified against the evidence commit. `execution-complete.json` also records seven gate codes `[1,1,1,1,1,1,1]`.

| Gate | Deciding result | Receipt SHA-256 / bytes | Complete stdout SHA-256 / bytes |
|---|---|---|---|
| Architecture | FAIL; 21 import rows unadjudicated | `b7c5f03bf81a73714d9e23f05ac0c410746fe65105538b50e8dde21f3dd6e012` / 8,116 | `b9a34d8fa461a74a5aa8bdf90cc0a38bd1de854a98b787a3fdb30418c31fcd31` / 125,505 |
| Runtime API | FAIL; committed OpenAPI 1,489 vs runtime 1,493; generated-client impact unmeasured | `cae5d080d0f41d6c8edee14d179996299388609173e5376fbc62f1468e6f5a35` / 8,150 | `33ea1bab8d94595a8fcd13d69e20181271ef9f843edf00e3293fe1e97d29e1e8` / 13,051 |
| Static invocation | FAIL; 10 regressions, 89 new unresolved, 9,238 unresolved, 140,152 receiver calls; partial coverage, runtime invocation not established | `93de1cad3fe47d670820f30bc83768bd8448304c9589819cdcb1e801c287a234` / 8,396 | `b5a159cf920a5eb7b6a952b4e5241ab401fd1cdce8040bd018d2825de3ea1035` / 9,180 |
| Ruff | FAIL; 7,951 diagnostics, 172 paths, 49 codes over all 317 changed Python inputs | `5b8dc52980dad58131bcb1b4a9bad65dbe02f704b1c59920b1b405d94c823db1` / 45,350 | `a1093d6da7fe2b91ae699e9619a53b1f0771012e8a11de3cc261385d7b5d4d4c` / 5,379,703 |
| Ruff format | FAIL; 156 would reformat / 161 already formatted over all 317 | `1d96281c39e83eee2a85c526b5d5d66b3aee91c562851ab6e3847440d1204a57` / 45,409 | `2d0cba1d1af81cedb36b72fe1f78d8759735364a9ed11b36e7e66ef5e4316a97` / 23,917 |
| Workspace verify | FAIL; doctor PASS then import lint FAIL (21 rows / 17 paths); **13 later stages UNRUN** | `ad64dbef734b06acc912f085a5c22b51c57bfa7a404bc51f28538974b4b872d8` / 8,626 | `04189ab2c39f2326934470029a8ecb0baeab7552788c62e7517bc91bd042ead3` / 7,456 |
| CI parity | FAIL; doctor FAIL on FeedbackSolveResult / `_manifest` ABI, registry and OpenAPI; **23 later stages UNRUN** | `9b3ec8066e84086f691f7a89be08b8116e3913fad8c14f958ffe6d945a69bc31` / 8,549 | `ddb7af0765326b3609afd85e7caba90bbc208c6e5a1ce7226654e81b5c6526e1` / 14,830 |

The 13 workspace-verification successors and 23 CI-parity successors are separate fail-fast workflows and separate denominators. They must not be reported as one combined 36-stage suite or as “13/23 of one suite.” Browser doctor capability does not imply hosted/browser/full-CI acceptance.

## Input denominators (not interchangeable)

No authoritative current input denominator of 309 appears in the r2 plan, current-case index, input index, or wave receipt. The artifacts instead bind distinct populations: actual JUnit selection uses **122 native test files + 2 A packet files = 124 test-file inputs**; source/runtime input list is **7,651** paths; full tracked candidate input list is **15,835**; changed Python Ruff/format denominator is **317**. The all-54 closeout input index separately lists **562 tracked evidence/source records and 220 portable records**; the 13 root-authoritative portable indices bind 213 copied records. These are evidence-publication axes, not substitutes for the wave's test-file denominator or its 1,445 test cases. Do not silently substitute 309.

## Ruff ownership/P41 comparison

The published debt record classifies 7,951 Ruff diagnostics over 172 paths and 156 format changes from the complete 317-path input list as E publication/control utility debt, with no blanket cosmetic exception. I compared that exact current gate denominator with the complete declared `5e3e3727…` → a9 source-footprint list (671 changed paths): 92/317 lint inputs intersect the 671-path delta; 68/172 diagnostic paths intersect it and account for 2,635 of 7,951 diagnostics (2,634 on E handoff paths, one on A); the 104 diagnostic paths outside that delta account for 5,316 diagnostics. On E handoff paths specifically, 169 diagnostic paths have 7,915 diagnostics / 153 format paths; 67 overlap the 5e→a9 delta (2,634 diagnostics / 52 format paths), 102 do not (5,281 / 101). Two other B handoff paths and one A path account for the remaining 36 diagnostics. I also compared the declared sets with Git: all 671 footprint rows exactly equal `git diff --name-status --no-renames 5e a9`, and all 317 Ruff input paths exactly equal the `.py` paths changed from original main base `198076863e143dea9f89f02734b13d50dae3eed5` to a9.

This confirms real E-area lint/format debt and shows the current gate has both delta overlap and diagnostics on unchanged-since-5e inputs. The set comparison establishes completeness only; it does not establish which red was inherited from the required original base. No exact original-base (`1980768…`) full Ruff/format command replay receipt over its complete denominator is present. Therefore P41 remains `not_established`; do not label all lint inherited, all lint caused by a9, or the current gate unrelated/A-owned. The source-footprint comparison is specifically 5e→a9, not a substitute for the required original-base P41 replay.

## Collector role correction and status boundary

The first carrier attempt supplied two absolute external-review paths as candidate-Git review inputs and the collector exited 128 before publishing; the old 6,358-byte source-freeze bytes remain preserved. The corrected typed carrier is 7,951 bytes, SHA-256 `c3cfeb2a9df29d1eb5f2e73da1a8eba940d1ff93569201dfb5a6fa671eae950d`: 6 candidate-Git review records with Git blob/size/hash bindings plus 2 external review records with content/role bindings and exact current a9/tree pins. The independent adapter has 18 refusal controls and verifies the two external records. The canonical collector itself validates the six Git review records only; the separate adapter is the evidence for the two external records. Do not claim the canonical collector validated all eight.

`collection_state=COMPLETE_BOUND` means custody/identity binding completed. It does not mean numerical PASS, code acceptance, full CI PASS, global gate acceptance, or finding closure. The ledger remains 49 partial / 4 held / 1 closed; no status mutation or automatic closure occurred. E's bounded source/code review and G's exact integration admission remain separate from accountable-owner decisions for the 49 limited proposals.

## Disposition for G

**Evidence identity/output reconciliation: GO. Numerical suite: HOLD (4 real assertion failures). Global verification: FAIL (all seven gates). E Ruff/format attribution: P41 not established. Finding closure: none.** This report does not accept E code or change the ledger; it gives G the exact current evidence boundary and the actionable next owners already identified in the final handoff.
