# Corpus (`polisyos.corpus`)

Last updated: 2026-05-24

`polisyos.corpus` owns internal loaders for repo-owned evaluation corpora.
The initial surfaces are W11.B claim/evidence decomposition annotations and
W11.D universal Policy Design Case fixture loading.

## Role in System

- **Consumes:** annotated Markdown cases under
  `docs/research/universal-policy-design/outcome-corpus/` and committed fixture
  JSON under `tests/fixtures/universal-corpus/`.
- **Produces:** strict in-memory models for annotation and fixture-driven
  validation tools.
- **Used by:** Wave 11/12 semantic evaluation, compilation truthfulness, domain
  breadth, and critic-diversity checks.

## Authority Boundary

Corpus fixtures are evaluation expectations, not runtime authority. They can
verify whether W6-W10 producers emitted truthful outputs, but they cannot
satisfy evidence, legal authority, method validity, participation legitimacy,
projection authority, or closeout by themselves.

W11.B annotations are reviewer-authored evaluation artifacts. They are
authoritative for corpus annotation and compilation-truthfulness comparison
only. They may not satisfy claim authority, producer evidence authority, legal
authority, method validity, participation legitimacy, or projection authority.

## Rotation Policy

Hidden fixtures require explicit loader opt-in. Rotating fixtures are selected
through the manifest's active round, and a case reused across consecutive
rounds is rejected unless the manifest records a durable acknowledgement.
