# ADR-0084: Formal BNF grammar for canonical variable names + seed 200 vars

## Status
Proposed

## Date
2026-02-28

## Context
PolicyOS merges causal graphs from multiple discovery methods, literature priors, and
dataset catalogs. Each source uses its own naming conventions: OpenAlex extractions
produce free-text variable names ("GDP per capita (PPP, 2017 USD)"), World Bank
indicators use dotted codes ("NY.GDP.PCAP.PP.KD"), and PCMCI outputs use positional
column labels ("var_0"). Without a canonical naming scheme, the graph reconciliation
step (Phase 0) spends significant effort on fuzzy matching and produces ambiguous
merges. A formal grammar for variable names, backed by a seed vocabulary, eliminates
ambiguity and enables deterministic alignment.

## Decision
1. Define a BNF grammar for canonical variable names:
   `<name> ::= <domain> "." <concept> ["." <qualifier>]* [":" <unit>]`
   where `<domain>` is a controlled vocabulary (ECON, HEALTH, EDU, GOV, ENV, SOCIAL),
   `<concept>` is a snake_case noun phrase, `<qualifier>` adds context (per_capita,
   log, lag1), and `<unit>` is an optional SI or domain-standard unit.
2. Publish a seed vocabulary of 200 canonical variable names covering the six domains,
   stored in `data/dataset_catalog/seed_variable_alignments.yaml`.
3. The `variable_canonizer` module validates incoming variable names against the grammar
   and maps known aliases (from dataset metadata) to canonical forms.
4. Variables that fail grammar validation are flagged as `NON_CANONICAL` and require
   analyst confirmation before entering the causal graph.
5. The seed vocabulary is versioned and extensible; new canonical names are added via
   PR review, not ad-hoc insertion.

## Consequences
### Positive
- Deterministic variable alignment across discovery methods, literature, and datasets.
- Grammar validation catches malformed variable names at ingestion time.
- Seed vocabulary provides a shared ontology for cross-study comparison.
### Negative
- Initial mapping of existing dataset columns to canonical names is a manual effort.
- The grammar is opinionated; edge cases (composite indices, ratios) may require
  awkward encodings.
- Seed vocabulary of 200 variables covers only the most common constructs; long-tail
  variables require ongoing curation.
