# Archived Reports

`docs/archive/reports/` stores curated evidence that future gates, plans, ADRs,
or release decisions may cite.

## Report Classes

| Class | Default path | Committed by default | Retention | Promotion criteria |
| --- | --- | --- | --- | --- |
| Audit or inventory report | `docs/archive/reports/YYYY-MM-DD-<topic>.md` | Yes, after review | Keep while cited by a plan, ADR, gate, or closeout | Owner, date, source inventory or command, and redaction notes are present. |
| Machine-readable evidence | `docs/archive/reports/YYYY-MM-DD-<topic>.json` or `.toml` | Yes, when small and reviewed | Keep while a gate or report cites it | Schema or producer is named, and the file is small enough for review. |
| Raw logs | `_build/**`, `.polisyos/reports/**`, or legacy `_logs*/` | No | Delete or regenerate locally | Promote only a redacted summary, not the full local transcript. |
| Release evidence | `release/**` or `docs/archive/reports/release/**` | Yes, after release-owner review | Keep indefinitely | Links to release fragments, evidence template, or release ledger. |
| Benchmark evidence | `docs/archive/reports/benchmarks/**` | No, unless promoted | Keep until a newer reviewed baseline supersedes it | Methodology, hardware/profile, suite id, and reviewer are recorded. |

## Limits

New curated reports should stay under 2 MiB each. Promoted benchmark summaries
should stay under 1 MiB each. If a run produces many files, keep the raw bundle
ignored and commit one summary plus links to the producer, seed/profile, and
gate that consumed it.
