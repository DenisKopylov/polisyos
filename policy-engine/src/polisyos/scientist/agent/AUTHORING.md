# Scientist Agent Authoring Contract

Owner: `team-scientist`
Applies to: `src/polisyos/scientist/agent/**`
Last updated: 2026-05-05

## Purpose

This package owns Scientist authoring and critique agents, drafting workflows,
reasoning helpers, memory adapters, and tool contracts.

## Allowed File Categories

- Product Python modules, package-local README/AUTHORING/index docs, and small
  typed prompt/contract helpers.
- No runtime state, transcripts, raw LLM logs, or generated evaluation output.

## Public/Private Boundary

Public imports are the documented typed contracts and factories. Underscore
modules, prompts, parser helpers, and orchestration internals are private.

## Naming Convention

Use snake_case modules named by role (`drafter`, `critic`, `supervisor`) or by
tool responsibility. Keep private drafter internals prefixed with `_drafter_`.

## Test Location

Tests live in `tests/unit/scientist/agent/` and Scientist integration tests
when agent behavior crosses workflow boundaries.

## Fixture/Data Policy

Use deterministic in-memory fixtures or `tests/_data/scientist/`. Do not commit
LLM outputs unless they are reviewed golden records.

## Generated File Policy

Agent evaluation reports and traces are local outputs unless promoted as
reviewed archive evidence.

## Extension Points

External authoring agents are not plugin-hosted yet. Tool contracts should be
kept explicit so future extension work can wrap them safely.

## Deprecation And Shim Policy

Prompt format, tool contract, or factory changes require compatibility notes
when old saved artifacts can still be loaded.
