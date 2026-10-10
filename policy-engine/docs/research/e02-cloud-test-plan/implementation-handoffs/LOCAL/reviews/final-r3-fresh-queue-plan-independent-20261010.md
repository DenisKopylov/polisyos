# R3 fresh-queue plan delta review

Read-only comparison of R3 plan bytes with the R2 counterparts. No tests, queue execution, manifest preparation, or Git commands were run.

## Plan identities

| Plan | R2 SHA-256 | R3 SHA-256 | Commands |
|---|---|---|---:|
| Primary | `ceff2fd9dc3f8706117e86f63a05ffc1e945958174717e4279ca65ecc8e58ed4` | `4a825bbc495f13efacadc835c88d86da138fdf6f092d5952659ced2fe016164e` | 19 |
| Supplement | `d1187408584f427a25dcb04ef62ea528756dd537ac62fcd9c207aad873c8cd02` | `121f240ddac113351ee80f2360a620961ab56edc7bba7e3b5041422e48e60d45` | 11 |
| Capture self-test | `7cee5538169a888bf8b6c4c3e8ef31c6a2a6a8a7618559c5310f11714260c957` | `a9a88b0a510a92617b83ae34144147940f9a86c17fcf6e527af4b6cb1ec45245` | 1 |

All R3 commands remain `UNRUN`. The primary, supplement, and self-test remain plan-only. The primary’s `source_scope.final_commit` and `final_tree` are null and expressly defer the source freeze to the root invocation.

## Delta and ownership checks

After normalizing the R2 raw-output root and plan references to their R3 counterparts, the primary and supplement have no command, selector, environment, or source-check differences; only their titles change. The self-test has no remaining content difference after path normalization. Thus all 19 + 11 + 1 argv vectors match their R2 versions apart from R3-owned output paths and R3 plan/manifest references.

The R3 supplement names the R3 primary as `base_plan`. Its composition records the R3 primary, R3 supplement, the two historical current-source plans, and R3 self-test. The R3 self-test points its runtime manifest context at `composed-mac-final-source-inputs-20261010-r3.json`.

The three fresh output roots are absent at review time:

- Primary: `.../raw/composed-mac-final-replay-20261010-r3/base`.
- Supplement: `.../raw/composed-mac-final-replay-20261010-r3/supplement`.
- Self-test: `.../raw/composed-mac-final-replay-20261010-r3/tools/capture-selftest`.

Every absolute output path declared by each plan is beneath that plan’s assigned root (19-command primary: 94 distinct output values; 11-command supplement: 54; standalone self-test: 4). No output crosses into an R2 root. The six old plan files remain present: R2 primary, R2 supplement, current-source replay, its supplemental light-gap plan, external-consumer plan R2, and self-test R2. Existing R2/current-source output paths remain separate; some planned directories are absent because their commands were not run. R3 does not repoint or claim those old paths as its outputs.

## Caller boundary and verdict

The existing explicit manifest caller accepts one primary plan and repeated additional plans, checks path symlinks and duplicates, hashes all supplied plan bytes before and after preparation, then reads back the produced manifest. It does not enforce a nine-plan count. GO for the R3 plan delta, conditional on the stated caller invocation supplying all six preserved plans plus all three R3 plans explicitly. The supplement’s embedded composition lists its five-plan subset; the root’s nine-plan call must remain the source of truth for binding the additional preserved R2/external plans.

No R3 queue or final source-input manifest has been executed or verified here. This is a plan-only review, not a runtime receipt or source-freeze result.
