# Group A analysis receipts

Research only; no adjudication, closure, status change, register row, or task registration.
Source baseline: `63bdb9640`. Worktree: `/Users/deniskopylov/polisyos/.worktrees/group-a-analysis`.
Branch: `codex/group-a-analysis`. Only root performs Git mutations; no push or prune.

Reports live in `docs/superpowers/specs/2026-09-11-group-a-*.md` (paths relative to
`policy-engine/`). Instruments and complete deciding outputs live below this journal.
Oversized output belongs in an ignored `raw/` directory and is cited by path and SHA-256.
Tracked evidence is cited as `path@commit`; register text is a claim under audit, never
evidence about source behavior. Unreadable inputs are recorded as ambiguous.

Pattern pass: P29/P32/P35/P36/P37/P38 apply to the evidence method. Derive complete
denominators twice, inspect delivered vocabulary with AST, distinguish declarations from
executed evidence, and describe the exact boundary of each measurement. P39 keeps the
receipt proportional to the question. This lane does not alter the pattern register.

## Entry receipt

2026-09-11, from `/Users/deniskopylov/polisyos`:

```text
$ git status -sb
## docs/raw-evidence-ignore
exit 0
$ git worktree list | grep group-a-analysis
[no output]
exit 1
$ git rev-parse --verify codex/group-a-analysis
fatal: Needed a single revision
exit 128
$ git worktree add /Users/deniskopylov/polisyos/.worktrees/group-a-analysis -b codex/group-a-analysis 63bdb9640
Preparing worktree (new branch 'codex/group-a-analysis')
[file checkout progress omitted: not a deciding measurement]
HEAD is now at 63bdb9640 govern(debt): restore the lost group-A rulings, and revert a close the ledger refused
exit 0
```

Readback in the new worktree: `git status -sb` printed
`## codex/group-a-analysis`, exit 0.
