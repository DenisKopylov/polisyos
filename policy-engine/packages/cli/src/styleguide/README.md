# PolicyOS CLI Styleguide

This package mirrors the runtime UI trust and provenance vocabulary for
terminal output. It keeps output ASCII-safe and stable for snapshots, logs and
screen readers.

## Status Tokens

- `[VERIFIED]` means lineage/hash verification completed for the same temporal
  scope.
- `[PENDING]` means lineage exists but verification is still running.
- `[STALE]` means newer evidence or model output exists.
- `[DISPUTED]` means an active dispute is attached.
- `[UNTRACED]` means governance debt is visible and must not be presented as
  verified.

## Rules

- Do not use emoji or color as the only status signal.
- Put severity first, then the trust token, then the human label.
- Use `QUEUED`, `RUNNING`, `BLOCKED`, `DONE` and `FAILED` for progress. Avoid
  spinners as the only activity signal.
- Print temporal scope on any provenance or trust-heavy line.
- Use fixed-width ASCII tables for CI snapshots and copied terminal output.
- Never print raw source text in a public/share context.
