# Independent v3 callback delta review: native freshness source copy

## Decision

**GO to apply v3 for focused verification.** The concrete blocker in the `cf070` candidate is fixed: v3 defines `_probe_walk_error(error: OSError) -> None` immediately before `_copy_isolated_probe_source`, and it raises a contextual `OSError` with the original exception chained. The new `os.walk` callback and the permission-error test use the same error text. This is a static review; I did not apply the patch, run tests, invoke a generator/native wave, or mutate Git.

This GO is limited to applying v3 and running the focused tests/importer checks, followed by the required generated-reference renderer check. It does not establish native freshness or output equivalence; those remain pending the frozen native wave.

## Delta and identity

- V3 patch: `LOCAL/raw/native-freshness-source-copy-v3.patch`, SHA-256 `e07acb5ed5e1b4acbd8b3a128e8ca361c75314d23bc7c9f80743d9554acbb161` (59,778 bytes).
- V2 `cf070` artifact remains separately preserved at `LOCAL/raw/native-freshness-source-copy.patch@cf070cb08c40de592a3e0f4419e7ac82e646ac3a91c1056f08b65ce5616f3c92`.
- Author note: `LOCAL/dx0-native/source-copy-engineering-v3-20261010.md@077bcbad775f697a7a37f3fd7fad5c287e0a313b92f2f60ef33d4b410c2875ea`.
- Textual diff against v2 adds only the typed callback definition and adjusts the affected unified-hunk line offsets. The four source preimages still match: guardrails `5d30de37ed02c5e346458e62e00b2772e7ba0eed501cf8282f72d3058bf9b4f6`; test `6cbdbe384c2ea300ffdfed7bdd460fa2a696e5ea22179cf6135db64d9d4a61d2`; manifest `0a79005a1d37c38ea759509215205284698b4bb12ecabb42c29e70196486eb6a`; trust checker `3cc47926a168f903a0dd6921eaa131b2d335ef850e8586e7cfbf2ae5837a5ac5`.
- The patch still changes four paths. `docs/reference/generated-artifacts.md` remains the required renderer companion and is not in the patch.

## Callback control and prior gaps

The v3 callback raises `OSError("unable to enumerate selected probe source: …")` from the incoming walk error. That matches the regex expected by `test_family_source_copy_fails_closed_on_directory_enumeration_error`; the prior undefined-name failure is removed. The existing measurement path maps setup `OSError` to `UNRUN`, while direct copier callers receive the error.

The two other prior gaps are unchanged from the previous delta review: the copier now retains environment/Hugging Face-shaped Python files selected by the canonical trust source walker, and the declared pnpm runtime trees bind file contents plus symlink provenance/targets in before/after inventories, refusing external targets. This review did not execute those controls.

## Limits and P40

**P40: SAME_CLASS_DEEPER.** The callback completes the same widened source-enumeration mechanism; it does not create a new class or justify a per-path repair. Keep arbitrary ambient/absolute child reads, source-copy atomicity under concurrent writers, and mutations changed-and-restored between runtime inventory snapshots `not_established`. Hold source writers during the frozen wave and do not claim OS-level isolation.

After applying v3, run the focused tests and importer checks, regenerate/check `docs/reference/generated-artifacts.md`, then proceed to the frozen native wave with complete outputs. Until those receipts exist, native source completeness and generated-output equivalence remain `not_established`.
