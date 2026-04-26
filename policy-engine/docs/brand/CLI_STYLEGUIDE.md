# CLI Styleguide

PolicyOS CLI output must use the same trust and provenance vocabulary as the
runtime UI while remaining ASCII-safe, scriptable and readable in low-color
terminals.

## Status Tokens

| Runtime status | CLI token    | Meaning                                                    |
| -------------- | ------------ | ---------------------------------------------------------- |
| `verified`     | `[VERIFIED]` | Lineage/hash was verified; this is not policy endorsement. |
| `pending`      | `[PENDING]`  | Verification is incomplete or queued.                      |
| `stale`        | `[STALE]`    | Evidence, model or baseline changed after verification.    |
| `disputed`     | `[DISPUTED]` | A reviewer or validator flagged the value.                 |
| `untraced`     | `[UNTRACED]` | No trusted lineage is available; reason must be printed.   |

Do not introduce emoji, spinners as meaning, or color-only status signals.
Color is optional decoration; the token is the source of truth.

## Severity

Use OpenTelemetry-aligned severity words for machine-facing output:
`trace`, `debug`, `info`, `warn`, `error`, `fatal`.

Human-facing commands may map them to:

- `ok` for completed checks;
- `warn` for actionable but non-blocking issues;
- `error` for blocked work;
- `audit` for provenance/trust detail.

## Tables

- ASCII borders are optional; aligned columns are required.
- Numeric columns are right-aligned.
- Long hashes truncate deterministically as `sha256:01234567...89abcdef`.
- Tables must have a plain text fallback; no ANSI escape is required to parse
  meaning.

## Provenance Output

Verbose commands that print decision values must include:

```text
value          0.23 ratio
status         [VERIFIED]
hash           sha256:01234567...89abcdef
verified_by    RiskReviewBot@2.0
verified_at    2026-04-16T09:20:00Z
method         lineage_hash_match
temporal       valid=2026-04-15T12:00:00Z tx=2026-04-16T09:20:00Z
```

`[UNTRACED]` output must include `reason_code` and `tracking_issue` when
available. A CLI command must never silently downgrade provenance.
