# Independent read-only review: F offline-resume drafts

Reviewed the current draft files in the G checkout at `76746fececd1a183a516c48f07ce2835baa8a2d1`:

- `integration/reviews/2026-10-07-tenth-wave/F.md`
- `integration/reviews/2026-10-07-tenth-wave/F-criteria-correction.md`
- `execution-prompts/continuation-2026-10-07/F-resume-after-offline-519e.md`

No tracked files, refs, source, or tests were changed. Verdict: **two narrow wording corrections recommended; remaining requested checks pass.**

## Verified

- The full frozen 519e SHA and tree are recorded (`519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82` / `750d28da94f372848fe6b2db5f88db95b94cb57d`) and explicitly distinguished from fetchable identity/ancestry. The docs do not demand recovery of that tree or lineage as a prerequisite. They permit a new append-only candidate from published leaves with its own base/parent/SHA/tree, while retaining lost 519e ancestry as a limitation and not transferring unbound PASS results. The helper clause is bounded to direct helpers and does not make recovery of 519e a gate to reviewing available leaves.
- LA-035 no longer requires an optimizer or normative-owner packet for equivalent relocation of the unchanged historical score. The documents retain the real limitation around constructed/external callers and production use, and reserve owner/objective versioning for a changed score/ranking or new objective.
- No duplicate Gini oracle run is requested. The docs distinguish the old Fraction pairwise oracle from the 64 LA-035 comparisons and distinguish the signed C/PPO refusal route from G acceptance or production calibration.
- `b5a421d83336e0b50ad9a6747f3f7d041d4c1b5a` is consistently given as a full 40-hex SHA and remains classified as the historical first assembled failure (130 PASS / 32 FAIL per profile), not as the corrected result. The cited object itself is not present in this checkout, so I verified the spelling/length and cross-document consistency, not the object’s content hash.

## Corrections

1. `integration/reviews/2026-10-07-tenth-wave/F.md`, paragraph 6, currently says the 244-PASS run was “на `8236...`”. The exact run is bound to `532ca1f5ff78dad58ac00d261aeabff3a99f9aa6` / tree `e157c672ee734a700795bbf921f2e3657aa8e9eb`; `8236d9c368336a5ea20c1586f29aea7321db6536` / tree `724a77c88d4e6699ffead58a5e3e3990fb88640a` is a later source. Suggested correction: “244-PASS run на exact source `532ca…` / tree `e157…`; положительный pairwise oracle и соответствующая положительная hard-Gini арифметика сохранены через `8236…`, но это не весь-source equivalence.”

2. The prompt paragraph 65 correctly identifies the 532ca run and the unchanged positive Gini fragment, but ends with “do not rerun it while the source/test blobs remain unchanged.” The *whole* source and test files did change between 532ca and 8236: `distributions.py` is +29/−7 and `test_gini_science.py` +9/−7. The diff adds runtime domain refusal, changes signed-zero-mean behavior, changes a reward consumer, and updates its negative test; the positive pairwise oracle/formula itself is unchanged. Narrow the condition to “do not rerun while the positive pairwise oracle and its exercised formula/domain remain unchanged; review or test only a changed affected path.” The correction note’s description of the delta is otherwise accurate.

`F-criteria-correction.md` correctly binds the 244-PASS receipt to 532ca and describes the bounded positive-body equivalence through 8236. The 8236 formula-vs-G-767 epsilon distinction and the b5 historical failure classification are consistent across the reviewed files.

Root readback: both wording corrections above were applied to the tracked draft. The old run is pinned to532ca/e157, and reuse is restricted to the unchanged positive oracle/formula/domain; changed whole blobs are not claimed equivalent.
