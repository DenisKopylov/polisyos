# ADR Rules

Architecture Decision Records capture irreversible or hard-to-reverse
decisions. Plans may propose decisions, but accepted architecture lives here and
in the machine-readable contracts under `architecture/`.

## Required Shape

Use `template.md` for new ADRs. Every ADR must include:

- status;
- date;
- context;
- decision;
- consequences;
- related decisions.

## Relations

Use explicit relation labels:

- `Supersedes`: this ADR replaces an older decision.
- `Extends`: this ADR keeps the older decision and adds scope.
- `Extended by`: an older ADR can point at the newer extension.
- `Related`: useful but non-authoritative connection.

## Numbering

Use the next numeric identifier in `docs/adr/`. Do not reuse identifiers and do
not renumber historical ADRs.

## Index

`index.toml` is the machine-readable ADR inventory. Regenerate the human pages
and stale-link report after ADR changes:

```bash
python3 tools/quality/validation/generate_adr_index.py
```

Repository closeout wiring is checked with
`uv run polisyos-tools workspace repository-sota-closeout --contract-only`.

Generated outputs:

- `docs/adr/index.md`
- `docs/adr/by-topic.md`
- `docs/archive/reports/ADR_STALE_LINK_REPORT.md`
