# Decision: issued-artifact identity and review-output custody

**State:** virtual companion patch only; unapplied. This is a failure/repair-register
maintenance proposal, not a product change, test result, formal closure, or G
acceptance.

## Boundaries and pattern pass

- Assigned base: commit `f8ff8a9e241badab03fdb4d584d36934970e4e15`, tree `9641b8e4b4eb90078d03ebd6740e9d229aee58e0`.
- Register target: `docs/reference/policy-design-case-failure-patterns.md`, SHA-256
  `a64956e284b411276a16a612afffb1fb42daf03ffef8f7ef1c3f3f9bc25d0349` at the assigned base; it was unchanged in the worktree.
- Proposed patch: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/artifact-identity-pattern-companion-20261011/artifact-identity-pattern-companion.patch`, SHA-256 `b1dd76862a27d509e8f7e950af93b552e923ea9911c996878bd9f66658740cd5`.
- Primary existing patterns: **P30** (provenance and discoverable identity), **P35**
  (evidence/citation boundaries), and **P40** (bucket the recurring class and widen
  instead of opening another repair round). **P38** already supplies the relevant
  address-versus-identity discriminator. No new pattern ID is proposed.
- P40 bucket: **SAME_CLASS_DEEPER**. The repeated issued-artifact changes and the
  review-output collision share one underlying gap: a mutable path is being used as
  if it named an immutable issued artifact/output. The later writer/colliding
  reviewer is a deeper ownership boundary of that class, not a separate per-file
  repair. The proposed rule widens to all issued artifacts and reviewer outputs.

## Observed evidence

1. **Native V14 artifact revision.** The preservation receipt at
   `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-v14-final-artifact-preservation-20261011/receipt.json`
   (`@577578d0eb742a01160bc615add6fc0dd8ddf2e5166c2df843ce84ab1a6eeaf9`) records earlier draft digest
   `68dc6732a9d4655d797889df19828bb043a0cf1e67fb179c72c12d6c9741139d` and a
   later protected patch at
   `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-v14-final-artifact-preservation-20261011/native-import-cycle-eager-graph-v14.patch`
   (`@718fdf05053cb989f45cfdd2d7f65d0e5160e7d244521a2deaf389ddc48dbed2`). The
   receipt says the earlier draft was superseded before application and makes no
   runtime-receipt or G-acceptance claim. The receipt protects the later artifact;
   this packet does not claim the earlier bytes were recovered.
2. **S3 V6 assigned-to-final revision.** The frozen-artifact receipt
   (`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/s3-frozen-artifact-preservation-20261011/receipt.json`,
   `@936295a1889a2d5ee678f05deaa926c2e6bef0148ce73711e826694f87997db0`) records assigned digests `546595c0ff2063478c4ffa217125074eda778c5bf987fe82a75adf35df6b2a2c` and `ad845b0b9eb9cb37b2f4f3e2e1371dd6a0a504b7c0be5a8a7238d6ecfa1e511b` as
   unavailable overwritten bytes, never applied or accepted. It protects the extant
   patch `b4b2d3f055cec85917100eff6ce71a0017b69d8d48252f2581db3c77eaca4191` and
   note `6016b7f7973b4c58864068ee2e3ca90c1e236b25601b76b909c1a88a20743465`.
   Those later bytes are not substituted for or described as recovery of the
   assigned versions.
3. **PAG V5 revision.** The independent review
   (`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/reviews/pag-v5-wholechain-strict-gate-companion-independent-20261011.md`,
   `@619290d60c9aa1a0087ba2b75666b3d8c5878bae0a3979b08b1b7576dc12d45e`) explicitly distinguishes earlier intake digests `9fccecb6d4561405b331be7f36def21cf1f1cd3f20480ac9e7ab23209f17a270` /
   `8702e30b262ea9ac01c2ecdae2ca3f0e3ae0696775dfff6f2291d25f9e6f15bf` from the bytes read for that review: patch
   `414455712389b7005c3fc3038dd98a72b838def875c64492b049dff4fd6a9b21` and note
   `88d995a44163b7c4400ea40cfbd8c3b4b92663a92a341cedad92e33f163e5583`. The
   separate erratum (`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/pag-v5-v4-run-denominator-erratum-20261011.md`,
   `@22a5e55b23ce4cacb1a39817fbd44014554d89d17f4a1d3ab24139cfa03f02ff`) says it does not edit or restore the old note. This proposal
   preserves that distinction; it does not review the unavailable earlier bytes.
4. **Shared independent-review destination.** The collision receipt
   (`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/s3-v6-review-output-lease-collision-20261011/receipt.json`,
   `@3fa077269a7030621e257b3dbea9ceccdb10966e493840698b0caea09e4d19c7`) records two reviews targeting
   `LOCAL/reviews/s3-default-fabric-profile-bridge-v6-independent-20261011.md`;
   backend bytes `7766b6c2133682c682fbc0a7bed7b8888ae7a180a1f509cf3d7694c1028953ee`
   had overwritten the frontend's reported
   `c88884be8a590a1b5d1cb9db720184ab4762ba5c49b76f76506de4426fc3f2c5` at that
   shared path. `frontend-recovery.json` (`@c19fa1ff6ed8a1d753f496be92d34c2d971d3c8f407e18d9623702bbff326831`) records exact recovery from
   the original reviewer write payload under a unique frontend path with the same
   digest. The receipt says source changes were zero. Recovery is claimed only for
   that original payload, not as proof that shared-path writes are safe.

## Proposed closure move

The patch adds one maintenance rule beneath existing P30/P35/P38 guidance. The
issuing writer must publish a final version, stop edits, read the exact bytes back,
and record role/owner/version/path/hash. An independent reviewer re-reads those
bytes and binds the output to that identity. Any later byte change creates a new
identity: a prior review stays bound to its original bytes and cannot be cited for
the new version until those bytes are reviewed. Each reviewer gets a unique output
path keyed by reviewer and reviewed-input identity before the first write. Unavailable old bytes remain explicitly unavailable; preserve only
available irrecomputable receipts, and cite tracked source by `path@sha` rather
than copying it into a report.

The falsifier is a post-readback rewrite at the old path without rebinding the
review, or a second reviewer offered the same output destination. The rule fails
if the stale review is still accepted for the changed bytes or either result is
lost. No automated guard is claimed by this documentation-only proposal; no tests
or product commands were run. The patch is meant to prevent repeated instance
repairs by binding the whole issued-artifact/output class.

## Source references

- Root `AGENTS.md` and `docs/reference/operations/handoff-and-platform-review.md`
  were read, along with the complete failure/repair register. No applicable
  nested `AGENTS.md` exists under the docs target; the discovered nested files are
  limited to `tools/` and `architecture/`.
- The preservation and recovery records are cited above by path and SHA-256; their
  contents are not copied into the patch.
