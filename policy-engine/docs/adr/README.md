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

`index.md` is the human navigation page. Repository SOTA Phase 5 validates the
ADR directory through `workspace repository-sota-closeout`, while generated ADR
index validation remains a follow-up until ADR front matter is normalized.
