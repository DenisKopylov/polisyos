# Independent review: bounded authentic read-only helper

**Verdict: NO-GO for the helper as documented until the selector-validation and redaction defects below are corrected.** Its honest limitation is otherwise clear: exit `3` reports only the bounded matches, with profile/currentness/closeout still incomplete. This is a static review only; I did not execute the helper, call HTTP, open a database, run tests, or modify source.

## Reviewed inputs

- Helper: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/final_authentic_read_only_check.py` — SHA-256 `fe969c37647e79019fea3f3674a5130d2bd766d4def6bc88001fac8cddc304d0`.
- Readiness note: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/final-authentic-read-only-command-readiness-20261010.md` — SHA-256 `ef002a3e2f330559efc6b7a9e27ee1e8c0ccd83a595ff527c5a7f69314971350`.
- Source anchor supplied for this review: `f52809e8210714131f53c7b90bd53a9215c69d69`.

## Findings

1. **Medium — malformed artifact refs can be reported as matched (P32/P38).** At helper lines 91–94, `_ref_matches` accepts any two dictionaries and compares `.get()` for four fields. Thus two malformed dictionaries with those fields absent compare equal (`None == None`) and return `True`; extra keys are also ignored. The production contract is stricter: `ArtifactRef` requires `artifact_id`, `kind`, and `media_type`, permits an optional profile hash, and forbids extras (`src/polisyos/core/artifacts/manifest.py:241–255`). The helper accepts raw JSON from stdin and environment rather than validating either side against that type, so it does not itself preserve the typed-ref guarantee. Validate both present refs as `ArtifactRef` (allowing its legitimate omitted/`None` profile default) and refuse malformed-present values before identity comparison. A missing context ref should remain a mismatch/refusal, never be treated as an absent profile.

2. **Medium — refusal output can disclose private absolute paths.** The outer handler at lines 286–287 prints `str(exc)`. The direct `selected_root.resolve(strict=True)` at line 149 and `_sha256(path)` open at line 84 can raise `OSError` whose text includes the absolute root/member path; that reason is serialized to stdout and captured by the documented `tee`. Other named-file resolution paths are already converted to fixed reason codes, so this leak is avoidable. Map all path-related `OSError`s to stable redacted reasons; do not serialize exception text containing filesystem names.

3. **Low/medium — the JSON Pointer parser accepts malformed selectors.** At lines 43–63, it checks only the initial slash, decodes `~1`/`~0` without rejecting invalid `~` escapes, and accepts array tokens through Python `int()`. For example, a token such as `~2` can resolve a literal key, and list tokens such as `01` or `+1` are accepted although they are not canonical JSON Pointer array indices. This can select a different declared member while the output reports a successful physical check. Reject invalid escape sequences and require the canonical array-index grammar before traversal.

## What the helper does establish

The path check is sound against a static traversal or symlink escape: it requires a relative member path, resolves it strictly, requires the resolved path to remain under the resolved selected root, and rejects non-regular files (lines 66–78). It rejects duplicate manifest/member paths, hashes file contents in bounded chunks, reads only the one selected manifest and two selected members, and performs no HTTP call, database access, directory census, or write. Internal symlinks resolving within the selected root are accepted. Path resolution and later opening are separate operations, so this is not race-free against concurrent filesystem replacement; that remains a diagnostic-only limitation and must not become an authority/currentness claim.

The helper reads response JSON from stdin; it does not establish that stdin came from a fresh authenticated GET. The readiness note's curl pipeline is an external acquisition step, and the helper correctly labels source currentness and the serving profile as not established and returns exit `3` even when the bounded comparisons match. Keep that boundary explicit. Also describe the two pointer-selected members as bytes read from those manifest descriptors: this helper separately compares the context's manifest hash and typed refs, but does not itself prove that those two descriptors are the payloads resolved by the snapshot/trace refs.

## Pattern and P40 classification

P05/P32/P37/P38 apply: the code must validate the typed selector and measure the selected-member property, not treat dictionary shape or a permissive pointer as proof. **P40: same selected-view/selector integrity class one level deeper**, so widen the single intake boundary to strict ref validation and standards-conformant pointer parsing rather than patching individual members. The path disclosure is a separate output-redaction issue. Currentness/profile absence is an explicitly declared bounded limitation, not a finding that the helper should silently promote.

## Verification boundary

Evidence consists of static source inspection and the matching SHA-256 values above. No runtime result or fresh-HTTP authenticity is claimed. Required next check after correction: exercise a valid profileless and profiled `ArtifactRef`, malformed-present/missing/extra-field refs, invalid pointer escapes/noncanonical list indices, outside-root symlink/path cases, and failure paths that must not print the selected absolute root or member path; then verify the actual curl-fed invocation remains exit `3` for matching bounded inputs and still marks profile/currentness incomplete.
