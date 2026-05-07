# Legal Batch Authoring Contract

Owner: `team-data-forge`
Applies to: `src/polisyos/data_forge/domains/legal/batch/**`
Last updated: 2026-05-05

## Purpose

This subtree owns offline legal-domain batch extraction, normalization,
classification, graph building, quality checks, and publication helpers.

## Allowed File Categories

- Product Python modules, small config constants, and local docs.
- Jurisdiction and pattern helpers under package-owned subdirectories.
- No large corpora, raw scraped documents, or generated run output.

## Public/Private Boundary

Public use flows through Data Forge domain APIs and documented batch commands.
Internal extractors, prompts, and graph helpers are private unless exported by
the package README.

## Naming Convention

Use snake_case names by pipeline stage or legal concept. CLI modules stay named
`cli.py` or `__main__.py`; prompt modules must be explicit about ownership.

## Test Location

Tests live in `tests/unit/data_forge/legal_batch/`.

## Fixture/Data Policy

Use small reviewed fixtures under `tests/_data/data_forge/` or test-local
fixtures. Do not commit production legal corpora here.

## Generated File Policy

Batch outputs are local or promoted artifacts. Commit generated summaries only
through generated-artifact or archive-report contracts.

## Extension Points

Data Forge domain plugins use `polisyos.data_forge_domains`; this batch package
is a builtin implementation, not an external plugin root.

## Deprecation And Shim Policy

Moved batch modules require tests for old callers and a shim entry when the old
import path remains supported.
