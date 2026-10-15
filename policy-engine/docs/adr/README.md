# ADR Rules

Architecture Decision Records capture irreversible or hard-to-reverse
decisions. Plans may propose decisions, but accepted ADRs and the
machine-readable contracts under `architecture/` hold accepted architecture.
System-level design proposals and ratification records are indexed separately in
[`docs/system-design-decisions/`](../system-design-decisions/README.md).

## Find And Read A Decision

- Start with the generated [ADR status index](index.md) or [topic index](by-topic.md).
  `index.toml` is the machine-readable inventory; the Markdown index is generated
  from it and is for navigation.
- Read the ADR itself before relying on it. Its status and explicit relations
  (`Supersedes`, `Extends`, `Extended by`, and `Related`) determine how it fits
  with other records.
- `Proposed` is not accepted. `Accepted` records are immutable under the
  [documentation style guide](../style-guide.md#adr-template); corrections or
  replacements belong in a new ADR. For `Deprecated` or `Superseded` records,
  inspect their relations and any named successor before treating them as
  current; superseded records remain as history.
- The generated index preserves `Approved` and `Completed` as distinct labels;
  it does not normalize them to `Accepted`. No status crosswalk is declared
  here, so keep the record's exact status and inspect its decision and
  relations. A status alone is not evidence that the decision is implemented.
- Missing or unrecognized status fields are indexed as `unknown`, not
  `accepted`. [ADR-0001](0001-remove-legacy-foundry-engine.md) through
  [ADR-0004](0004-architecture-boundaries-import-gate.md) declare no status;
  their generated `unknown` labels do not supply a lifecycle decision. No
  status label proves current implementation. This is the `P36`
  authority-by-adjacency hazard; see the
  [failure-pattern register](../reference/policy-design-case-failure-patterns.md).
- A supersession link does not promote its target. Read the successor's own
  status: for example, [ADR-0045](0045-causal-edge-combined-confidence-formula-superseded.md)
  calls [ADR-0064](0064-compute-combined-confidence-noisy-or.md) "current", but
  ADR-0064 is `Proposed`. That link records the historical handoff; it does not
  establish an accepted or implemented replacement. This is the `P36`
  authority-by-adjacency hazard; see the
  [failure-pattern register](../reference/policy-design-case-failure-patterns.md).
- Narrative claims inside an ADR, such as "current" or "migrated", are claims
  in that record, not source verification. To describe behavior as current,
  follow the source snapshot and verification rules in the
  [documentation style guide](../style-guide.md) and state the checked source,
  method, and scope; keep any source drift explicit.
- The generated relation fields come only from explicit relation labels or a
  `Superseded by ADR-…` status value. Narrative words such as “replaces” do not
  declare a direction. The ADR-0045 → ADR-0064 handoff therefore records only
  that ADR-0045 is superseded by ADR-0064; it does not also make ADR-0045 a
  successor of ADR-0064. This is the `P36`
  authority-by-adjacency hazard; see the
  [failure-pattern register](../reference/policy-design-case-failure-patterns.md).
- For the system identity and custody boundary, read the
  [system design decision index](../system-design-decisions/README.md) and its
  ratification records; a ratification is authoritative only for the scope
  named by that record. Cite the exact invariant identifier (for example,
  `S0-K06`) in its
  [Stage-0 ratification record](../system-design-decisions/stage0-custody-kernel-ratification.md),
  then check `authoritative_for` and `may_not_use_for`; this index is a route to
  the finding, not a substitute for it.

## Required Shape

Use `template.md` for new ADRs. New ADRs must include:

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

Use the next available four-digit identifier in the ADR namespace for a new
numbered ADR. Do not reuse identifiers and do not renumber historical ADRs.
Existing records also include legacy `ADR-NNN` and repository-structure
`RSR-NNNN` identifiers; numeric suffixes can overlap across these namespaces
(for example, `0004` and `ADR-004`, or `0129` and `RSR-0129`). Use the full
identifier and filename in links and discussion; never infer identity or a
relation from the digits alone.

## Index

`index.toml` is the machine-readable ADR inventory. Regenerate the human pages
and stale-link report after ADR changes:

```bash
uv run python tools/quality/validation/generate_adr_index.py
```

Every ADR row in `index.toml` must carry a stable `topic` classification.
New ADR files without a topic row fail the ADR generator and docs lifecycle
gate.

Repository closeout wiring is checked with
`uv run polisyos-tools workspace repository-sota-closeout --contract-only`.

Generated outputs:

- [Status index](index.md)
- [ADRs by topic](by-topic.md)
- `docs/archive/reports/ADR_STALE_LINK_REPORT.md`
