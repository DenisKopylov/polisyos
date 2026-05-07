# Lex NormPack Authoring Contract

Owner: `team-lex`
Applies to: `src/polisyos/lex/normpack/**`
Last updated: 2026-05-05

## Purpose

This subtree owns Lex NormPack assembly, builtin provider metadata, and the
NormPack extension host boundary.

## Allowed File Categories

- Product Python modules, provider contracts, small reviewed seed metadata, and
  local docs.
- No raw legal corpora, generated packs, local caches, or batch outputs.

## Public/Private Boundary

Public ABI is `polisyos.lex_normpacks` plus legacy compatibility group
`polisyos.norm_pack_providers`. Implementation helpers are private unless
exported by package docs.

## Naming Convention

Use snake_case modules by NormPack concern. Provider modules should name the
jurisdiction or source family explicitly.

## Test Location

Tests live in `tests/unit/lex/` and extension-example smoke tests when external
providers are involved.

## Fixture/Data Policy

Use tiny reviewed fixtures under `tests/_data/lex/` or installable examples.
Do not commit generated production NormPacks here.

## Generated File Policy

Generated packs are local or registered generated artifacts. Do not edit or
commit generated outputs without registry coverage.

## Extension Points

External providers use `polisyos.lex_normpacks`; legacy providers may remain in
`polisyos.norm_pack_providers` only while compatibility policy allows it.

## Deprecation And Shim Policy

Legacy entry-point groups and provider IDs require compatibility notes and a
removal window before deletion.
