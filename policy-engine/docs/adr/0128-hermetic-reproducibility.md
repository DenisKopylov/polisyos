# ADR-0128: Hermetic Reproducibility

## Status

Proposed

## Date

2026-04-18

## Context

Data Forge, Scientist, Foundry, and frontend builds depend on Python packages,
Node packages, Docker base images, model weights, tokenizers, and provider
versions. Golden and differential tests are only trustworthy if these inputs
are pinned and recorded.

## Decision

Make reproducibility hermetic by default:

1. Python dependencies resolve through one product-root `uv.lock`.
2. Frontend dependencies resolve through one frontend workspace lockfile.
3. Docker base images use digests, not mutable tags.
4. Model weights and tokenizers are pinned by name plus hash.
5. ArtifactRefs record producer version, git SHA, lockfile hash, model hashes,
   tokenizer hashes, and provider API version when relevant.
6. CI runs install/build/test commands in frozen-lockfile mode.

## Consequences

- Historical artifacts become reproducible enough for audit and regression
  investigation.

- Model upgrades become explicit governance events.
- Local velocity can still use opt-in unlocked workflows, but publish and CI
  paths fail closed.

## Related Decisions

- Extends: ADR-0118 (release train and SemVer contracts), ADR-0123 (ArtifactRef
  governance metadata).

- Related: ADR-0010 (CAS artifact signing), ADR-0122 (lakehouse snapshots).
