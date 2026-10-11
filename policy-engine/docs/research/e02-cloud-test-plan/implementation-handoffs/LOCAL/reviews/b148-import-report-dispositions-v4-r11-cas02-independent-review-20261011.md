# B148 import report dispositions V4 r11 CAS-02 independent review

## Verdict

**GO for the r11 candidate delta against the independently reviewed r10 source.** The corrected CAS-02 tests now exercise the owned publication/rollback seam and pass in a fresh isolated source composition. This is not G's independent acceptance or a formal B148 adjudication. `closure_ids` is empty.

## Exact boundary and source identity

- Candidate is pinned to base commit `cd5651c3a6897f12d32212e3521e73bb570f137b`, tree `bb7186c24000b54fdb0ab8ce8d16b55c3658995c`, parent `c19e502ddfa9dec45e5de72b380003250a2d676c`.
- Current worktree at review time was branch `codex/e02-unified-local-20261009`, HEAD `91dfa30d18aa089984f71d48099491cccc9d1afa`, tree `2e1f270436b96c320085eeb27c0af595dd402dba`. Candidate source remained virtual and exact-base-pinned; no product source or index/history path was edited by this review.
- r11 patch `LOCAL/raw/b148-import-report-dispositions-v4-r11-cas02-recovery-oracle-20261011/candidate.patch` @ `d2a8ef3e24cac4e0008d068b9263615b14c2b054ab2f089ca5bea07cec198f70`; manifest @ `82fdf25cf61fc3fb299ad96e362f2921bddb2e15df9fa6cf769bedc855fb113d`.
- I independently compared the two unified patch sections: both have 12 paths; 11 non-CAS sections are byte-identical to r10, and the only differing section is `policy-engine/tests/unit/remediation/test_cas_02.py`. r11's preimage hashes for all 12 paths match `git show cd5651c3…:<path>` (including the two expected-absent files); all 11 non-CAS postimage hashes match r10 exactly. This confirms the r10 source-review boundary remains intact.
- Whole-mechanism review reused from `LOCAL/reviews/b148-import-report-dispositions-v4-r10-independent-review-20261011.md` @ `ad5a1b42634b6eacc1083b9461cb0f573a94347122f587d8f998756f6277ea07`: that review passed the import producer/report and CLI consumers (36 and 9 tests respectively) and isolated its remaining two CAS-02 failures to an unhashable-ID assertion and an obsolete failure-injection seam.

## CAS-02 behavior and deciding evidence

The prior-generation test now injects one `OSError` at the actual publication boundary: `os.replace(staging_root, export_root)` in candidate `_publish_directory_generation`. It asserts the injection occurs exactly once, no staging or previous-generation sibling remains, and every prior regular-file member has exactly the same bytes after the failed replacement. Source inspection confirms the owner catches the failed swap, restores `previous_root` to the live target, then the export `finally` removes staging. This is the real producer path; the previous `shutil.copy2` fault never reached it.

The mid-publication recovery test also fixes the `ArtifactID` set-comprehension `TypeError`: it compares canonical string identities for the recovered `published_refs` and `integrity_verified_refs`. The test first injects a failure after the first blob member, verifies the incomplete artifact remains unreadable while the owner transaction is pending, then removes the fault and performs an exact retry. It asserts the durable owner-intent disposition, both returned ref sets, and both recovered payloads.

Fresh independent run used a small exact-base source sandbox, not the current dirty package overlay: it archived `core/artifacts` and package initializers from cd565, overlaid only candidate `_transfer_ops.py` and `store.py`, then ran the exact r11 CAS-02 test file. Loaded candidate source hashes matched the manifest; all external `polisyos` dependency modules loaded by the tests matched cd565 (`DEPENDENCY_BASE_MISMATCHES []`). Command from `policy-engine/`:

`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b148-r11-independent-review/run_candidate_cas02.py`

Exit 0; 18 tests passed. Complete output: `LOCAL/raw/b148-r11-independent-review/candidate-cas02.stdout.txt` @ `c4e5785592591e8646c3694a4b6ae0b7e33056f555cd52cbac00cde6a221eec0`; runner @ `7be01a2f61a93638141328f3284813d4aff5d0a73c22ecb58e46305c9196dd45`.

I also ran the property-removal control in a separate exact-base scratch source tree. It kept the r11 test unchanged at the exact candidate test hash `e93cc5988daa523bc75c7080c33c9d7370427d524262c413d26f5f2f0f045eea` but removed only the `try/except` that restores the previous generation after the staged-to-live `os.replace` fails. The test then failed specifically because `.reused-export.previous-*` remained. This is a meaningful remove-the-property/keep-the-test control, not a marker assertion. Command from `policy-engine/`:

`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b148-r11-independent-review/run_rollback_removal_control.py`

Expected control exit 1; full output `LOCAL/raw/b148-r11-independent-review/removal-control.stdout.txt` @ `a98d5e84c21dd6e72835edf6f157c0c9756bab9dc0fa56d32ec720bc6728697a`; runner @ `3c9aac4fe619f2611f7ba0712c6511a421cfd27650d55b894e0b88f5d3253add`.

The exact-entry failure of the older injection is retained at `LOCAL/raw/b148-import-report-dispositions-v4-r11-cas02-recovery-oracle-20261011/baseline-obsolete-fault-seam.stdout.txt` @ `f633590fa885eec8e0ff692b786e08f83c9b7114eb79ce9a01c7ee21ced424c2`: it shows the old `copy2` injection did not raise. r11 repairs that test to target the code-owned swap. Because the affected test file is in this slice's denominator and changed by the candidate, this is not eligible for a P41 inherited label. No whole-CAS gate or composed-runtime result is claimed here.

## P40 and limits

P40 bucket: **same CAS-02 whole-generation rollback class, one level deeper at the actual atomic publication boundary**. r11 changes only the test oracle; no product behavior beyond the r10 reviewed source is introduced. The fresh run is bounded to the 18-test CAS-02 file. The other r10 suites, canonical changed-test Ruff/format checks, baseline seam output, and author's patch-application check are separate retained evidence; no native full repository gates, full B148 composed replay, or production/currentness claim is made by this review. Root must still perform the composed freeze and required broader replay.

`closure_ids`: `[]`. This note is an independent candidate review, not a formal closure proposal.
