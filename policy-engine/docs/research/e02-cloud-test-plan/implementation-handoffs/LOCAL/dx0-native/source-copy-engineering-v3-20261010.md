# Native source-copy patch v3

Status: patch only; not applied or tested. This version fixes the review blocker in v2: `_copy_isolated_probe_source` passed `_probe_walk_error` as the `os.walk` error callback, but the function definition had been lost while replacing the adjacent pnpm helper block. V3 defines the typed raising callback immediately before the copier; an enumeration error becomes `OSError` and the existing measurement caller maps setup errors to typed `UNRUN`.

- V3 patch: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-freshness-source-copy-v3.patch@e07acb5ed5e1b4acbd8b3a128e8ca361c75314d23bc7c9f80743d9554acbb161` (59,778 bytes).
- Prior `cf070` candidate preserved byte-for-byte: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-freshness-source-copy-v2-cf070cb08c40.patch@cf070cb08c40de592a3e0f4419e7ac82e646ac3a91c1056f08b65ce5616f3c92`.
- Exact preimages: `tools/devx/architecture/guardrails.py@5d30de37ed02c5e346458e62e00b2772e7ba0eed501cf8282f72d3058bf9b4f6`; `tests/repo_quality/tools/test_architecture_phase3.py@6cbdbe384c2ea300ffdfed7bdd460fa2a696e5ea22179cf6135db64d9d4a61d2`; `architecture/generated_artifacts.toml@0a79005a1d37c38ea759509215205284698b4bb12ecabb42c29e70196486eb6a`; `tools/quality/validation/check_trust_claim_posture.py@3cc47926a168f903a0dd6921eaa131b2d335ef850e8586e7cfbf2ae5837a5ac5`.

Static verification used the local preimage bytes: all four hashes matched, each unified hunk reconciled, proposed Python postimages parsed, and AST inspection confirmed the callback and pnpm inventory definitions resolve. No source write, patch application, test, generator, Git mutation, or native wave occurred.
