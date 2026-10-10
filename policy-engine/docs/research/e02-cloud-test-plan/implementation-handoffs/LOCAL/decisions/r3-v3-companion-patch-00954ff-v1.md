# R3 / V3 companion patch (unapplied)

Status: patch-only author handoff. No target file was modified, and no tests were run against the proposed diff.

Base label: 00954ff836642ca3c2dca4032fcd1b83019bdfd0 (tree label cf422a9a79c3ffd43bd09817edbcd806db1d7570). The patch is tied to the three exact pre-patch file hashes recorded in the companion JSON.

Patch: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r3-v3-companion-patch-00954ff-v1.patch
SHA-256: eec469a37d1a703c0498b99242ad58b92fe59c7ad1fcdb81633f66b3ca6d00c8
Byte count: 12112

## R3: selected authority-envelope views

The property is that each typed authority-envelope ref consumed by the producer resolves through the CAS owner to the exact selected view, whose bytes, manifest scope, producer, governance and same-input closure all bind to the intended run. The old assertion used profile presence as the proxy. The retained source-backed observation shows the ordinary producer emits six valid default-view refs (manifest_profile_sha256=None) and one explicitly profiled ref among seven; the old unconditional non-None test therefore rejects valid default-view reads. This is P38, not a contract allowing unverified default refs.

The proposed test resolves each actual selected ref with verify(ref), get_manifest(ref) and get_bytes(ref), checks content hash, artifact/schema identity, tenant/cell/run, producer and governance, and compares the typed envelope's same-input closure against the selected manifest closure. It resolves the sibling profile too and proves the same bytes with foreign tenant/cell and missing producer/governance/closure do not bind to the selected owner. A profile-transplanted selected ref is required to fail the same binding verifier. The first explicit profile remains contrasted with the default view; the default ref is accepted only after the same content and owner checks. The existing production-read assertion continues to show those selected typed refs were consumed.

This changes only the R3 test companion, not producer runtime semantics or authority. Source evidence/output retained under LOCAL/raw/r3-v3-observer-wave-20261010/; exact observer stdin was not retained and is recorded as not_established in observer.stdin.retention.json (SHA-256 e9283cd83fd58f33005419daa0b6c2d9376c330f6df159ac7ccfd450085c821d). No reconstructed observer script is claimed.

## V3: fixture publication and full acquisition history

The observed fresh GET returned 200 but had no acquisition history because the test fixture's compiled-cycle artifact omitted tenant_context. The production publisher supplies that binding from an established execution_scope; the fixture already owns the corresponding typed admission.scope. The helper hunk supplies the same conditional typed ArtifactTenantContextInfo to _put_json_artifact_ref, retaining the exact admitted scope and no client-derived identity.

With the compiled artifact bound, the existing source-backed history reader should see both matching terminal action generations. The current single-entry expectation silently drops the earlier quarantined generation when a later reentry succeeds. The proposed served assertion requires both generation 1 (quarantined_no_growth, tied to first_terminal_ref, with no reentry/candidate fields) and generation 2 (reentry_completed, tied to the actual terminal/reentry refs and existing selected candidate/source checks). The successful and quarantined entries retain currentness_status=not_established, authority_purpose=candidate_observation_only, and publication_authority=false; this is observed history, not a claim of currentness or external custody. The explicit unauthenticated GET 401 assertion is unchanged.

This is P40 same-class-deeper: the earlier gap was compiled-artifact scope omission; the newly observed one was narrowing the history consumer to one action generation. The proposed companion spans fixture producer scope through fresh served history over the complete matching head set, instead of repairing one selected row.

## Evidence and limits

The combined pre-patch exact selectors were run once and retained as 2 failures (R3 selected-profile assertion; V3 GET projection contained zero acquisition entries) in the source-composition evidence under LOCAL/raw/composed-mac-current-source-20261010/. The additional observer run and exact CAS/head readback are in LOCAL/raw/r3-v3-observer-wave-20261010/; its readback identifies two latest terminal heads, action generations 1 and 2, for the exact source run/job. These are prior-state observations. This patch has not been applied or executed, so its behavior remains unverified pending the owner's sequential apply and focused verification.

Pattern pass: P38 proxy versus property; P32 resolve/content/scope bind; P29 behavioral test; P40 class-first widening. Public API/schema is unchanged. Residual: no claim here about currentness, same-candidate relevance, acquisition authority or publication authority.
