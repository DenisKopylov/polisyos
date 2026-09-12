# Measurement plane completion journal

Status: Stage 1 research in progress; no mechanism changed.

Lane: `codex/measurement-plane`, base `307dabcb4`. Local ordinary git; no push,
prune, guardrails sync, register or ledger edits. Root serializes git and the
four shared instruments. Row 1 surveys alone; then rows 2+3 and 4+5 may overlap.

Name admission: `git worktree list | grep measurement-plane` exited 1 with no
output; `git rev-parse --verify codex/measurement-plane` exited 128 (`fatal:
Needed a single revision`). Target path did not exist. The requested
`git worktree add /Users/deniskopylov/polisyos/.worktrees/measurement-plane -b
codex/measurement-plane 307dabcb4` completed; `git status -sb` read back
`## codex/measurement-plane` with a clean tree.

Evidence policy: complete deciding output and removal probes retained; large
outputs in gitignored `**/raw/`, cited by path and SHA-256. Tracked inputs are
cited as path@commit. Search predicates must expose their counterexample and
run case-insensitively. ASTs establish definitions and calls. Every set-level
count names its full path/file-type denominator and independent cross-check.
Unreadable members remain ambiguous.
