# GY-N12 Cycle 5 — Decision Record

## Boundary, accepted input and toolchain gate

Cycles 1–4 and their qualified unification verdict are accepted inputs. This
cycle does not reopen them. It decides only: the proof profile, the two
owner-bridge prerequisites, the status of the `epoch_ref` inference, delivery
scope, and the institutional anchor-custody question.

The read-only baseline was the attached
`codex/gy-n12-epoch-chronology` branch at
`0febe4748d6eaaa2d4f5464f3df7a893a5dbe27a`, with an empty worktree. Its
merge-base with local `main` was exactly
`1360b1cb592be6a19c162a3ec3ddb5a2e87986c7`. Local Git and dependency-free
tracked-tree/AST reads were the only admitted evidence. No bootstrap,
repository import, runtime, generated artifact, validator, replay or
`research` profile was used. The GY-DI1/GY-DEF22 gate therefore stays closed;
in particular, no result involving the inadmissible `torch==2.10.0` profile
enters this record.

Every count below was derived over a declared complete set by two independent
walks. Git enumerated exact HEAD blobs; the filesystem independently enumerated
the clean worktree. Python AST checks parsed all 2,561 source Python files.
Where the repository has no canonical production denominator, the answer is
`not_established`, not a count guessed from a fixture, directory or API name.
Cycle 5 used no external source: repository counterexamples were sufficient for
5a and 5c.

## 5a — scale measurement and fixed proof profile

### What exists today and at the horizon

There are **zero admitted chronology-proof members in all four families
today**, because all four proof-family producers remain
`absent/unallocated`. That is a count of tracked admitted proof artifacts, not
a claim that no external production event has happened. The production
denominators and growth rates are not in this repository, so production counts
at the explicit calendar horizon **2030-12-31** are `not_established` for all
four families.

The nearest native evidence cannot be promoted into those missing counts:

| family | admitted proof members at 2026-08-20 | complete native evidence measured | production members at 2030-12-31 | canonical native member / aggregate bytes |
| --- | ---: | --- | --- | --- |
| epochs | 0 | the Ukraine source declares two L5 `SchemaRegimeSpec` values and one changepoint; the full L3/L5/N13b plus semantic-facet denominator is not established | `not_established` | `not_established`; source declarations are not epoch artifacts |
| controlled releases | 0 | 23 tracked unreleased TOML fragments, 52,132 bytes, are release-note inputs and not GY-GAP3 controlled-release members | `not_established` | `not_established`; fragment bytes are only a labelled proxy |
| recursive runs | 0 | the source tree has one recursive compile entry definition and zero source calls; the live production boundary and complete run denominator are not established | `not_established` | `not_established` |
| movement rows | 0 | the N13b acquisition registry has two live-fetch entries and no row/byte cap; no complete eligible-row or movement denominator exists | `not_established` | `not_established` |

The epoch literals are at
`src/polisyos/data_forge/domains/ukraine/builders/sources.py:1796-1823`; they are the first
test case, not a complete epoch census. Git and filesystem enumeration both
found exactly 23 `release-fragments/unreleased/*.toml` files and summed the
exact bytes to 52,132. Their policy classifies them as committed release-note
input, not frozen controlled-release transcripts
(`docs/how-to/release-policy.md:39-40,121-122`). The source AST found
`compile_and_run_recursive_generation_cycle` once as a definition and zero times as a
source call; it also found zero source calls to the N13b `admit_epoch` method
and to the passport builder. Recursive budgets cap nodes at 100 and depth at
99, but `max_cycles_per_leaf` has no global upper bound
(`src/polisyos/runtime/quality/recursive_generation_cycle.py:91-99`), so those limits do
not supply a horizon count. Two independent JSON readers agree that
`architecture/policy_design_case/layer3_gy_n13b_acquisition_registry.json`
has two entries, both `live_fetch`, and neither has a row or byte cap.

One complete but **non-family** stress proxy was retained only to set a safe
qualification envelope. The 35-entry catalog source registry has 32 enabled
entries; exactly three declare snapshot caps. Their sums are 2,250,000 rows
and 524,288,000 bytes
(`src/polisyos/data_forge/domains/catalog/batch/source_registry.yaml:495-543`). These caps
do not establish N13b eligibility, one movement row per source row, a
production forecast, or an owner SLO.

### Consumer demand and ceilings

No admitted consumer requests a selective proof. The specified verifier is an
offline consumer of the complete frozen native history. Present call frequency
is therefore zero, while future verification frequency, latency SLO and
storage ceiling are `not_established` for every family. Decision Validity and
Claim Ledger are real epoch downstream owners but do not yet consume an epoch
anchor; GY-PA3 is only the plan-appointed release consumer; run and movement
anchor consumers are not appointed. A proof profile cannot turn those missing
appointments into measured demand.

Consequently, this cycle cannot claim that linear replay meets every owner SLO
“with margin”: no such SLO is evidenced. It can eliminate the algorithm fork
by bounding what v1 will admit and making the first appointed consumer's
benchmark a pre-issuance gate.

### Decision: full-prefix v1, no transparency tree

The fixed v1 profile is
`full_prefix_canon_json_0_2_0_sha256_256_v1`:

- native member bytes remain in each family-native store;
- the proof layer streams the complete cutoff-bound native history in
  family-native order and computes a domain-separated SHA-256 predecessor
  chain;
- canonical proof frames use `polisyos.canon.json@0.2.0` with floats forbidden;
- an immutable member frame binds `format`, `profile`, `proof_domain`,
  `family`, `scope_ref`, `authority_purpose`,
  `native_schema_profile`, `member_ordinal`, `member_ref`,
  `member_content_hash`, `member_admission_basis_ref`,
  `member_admission_context_ref` and `predecessor_commitment`;
- all variable native payloads and coordinates are content refs; the frame
  projects no common status, timestamp, action or semantic payload;
- `member_admission_context_ref` resolves an immutable opaque family-native
  record under `native_schema_profile`. It binds scope, authority purpose, the
  member's admission cutoff/basis, admission-policy/profile version, the P37
  class/result for member-admission predicates, and only the CTM/query
  relations declared applicable by that adapter. The epoch schema requires
  its explicit valid/effect and visibility/knowledge coordinates, `epoch_ref`
  and native predecessor/fork relation; other families do not fabricate them;
- requested cutoff and denominator are **not** member fields. A canonical
  bundle header has exactly `format`, `profile`, `proof_domain`, `family`,
  `scope_ref`, `authority_purpose`, `native_schema_profile`,
  `declared_denominator_ref`, `requested_cutoff_ref`,
  `requested_query_context_ref`, `member_count`, `native_bytes_total`,
  `first_commitment` and `commitment_head`. Its opaque family-native query
  context binds only applicable requested coordinates plus the P37
  class/result for denominator completeness. Currentness, terminality or a
  native-head predicate appears only when that adapter declares it applicable;
  no placeholder is emitted otherwise. Consumer acceptance is added by the
  later signed receipt;
- one length-prefixed canonical member frame is capped at 1,024 bytes and one
  length-prefixed bundle header at 4,096 bytes; and
- verification is streamed `O(n)` / `O(B)` and requires the complete frozen
  native history. It supplies no selective membership response.

The bytes are fixed, not left to an implementation:

1. `C(x)` is `to_canonical_bytes` over a freshly constructed raw mapping,
   list or scalar only; `BaseModel` and dataclass inputs are rejected. The
   complete `CanonSpec` is `name="polisyos.canon.json"`,
   `version="0.2.0"`, `forbid_floats=True`,
   `forbid_nan_inf=True`, `exclude_none=False`, `max_depth=128`,
   `sort_keys=True`, `separators=(",", ":")` and
   `ensure_ascii=False`. Thus canonical `null` is retained. `format` is the
   literal
   `polisyos.chronology.full-prefix.v1` and `profile` is the fixed profile
   name above. Every digest-bearing field is a canonical JSON string
   `sha256:` plus exactly 64 lower-case hexadecimal characters.
2. The domain descriptor is `C` of an object with exactly `format`, `profile`,
   `proof_domain`, `family`, `scope_ref` and `authority_purpose`. Genesis `G`
   is `sha256:` plus lower-case hex of
   `SHA256(UTF8("polisyos.chronology.genesis.v1\0") || descriptor)`.
3. Let `N_i` be the exact native bytes and
   `R_i = uint64_be(len(N_i)) || N_i`. `member_content_hash` must equal
   `sha256:` plus lower-case hex of
   `SHA256(UTF8("polisyos.chronology.native.v1\0") || R_i)`. The common
   verifier recomputes it from the framed bytes; the family adapter proves
   opaque `member_ref` identifies those bytes in its native denominator.
4. `F_i = C(member_frame_i)`. `member_ordinal` is the zero-based integer,
   `predecessor_commitment = G` at ordinal zero and `H_(i-1)` thereafter.
   `H_i` is `sha256:` plus lower-case hex of
   `SHA256(UTF8("polisyos.chronology.member.v1\0") || F_i)`.
5. At `n > 0`, `first_commitment = H_0` and
   `commitment_head = H_(n-1)`. At `n = 0`, the exact canonical values are
   integer `member_count = 0`, integer `native_bytes_total = 0`,
   `first_commitment = null` and `commitment_head = G`. A zero bundle is
   authority-eligible only when the native denominator is `recomputed` or
   `independently_reconciled` as empty; a writer's zero cannot conceal an
   omitted required member.
6. Every serialized record is `uint64_be(byte_length) || bytes`. The bundle is
   framed canonical header followed, for each ordinal, by framed `F_i` then
   `R_i`. `native_bytes_total = sum(len(N_i))`. The bundle content hash is the
   same digest representation over
   `UTF8("polisyos.chronology.bundle.v1\0")` plus the entire bundle. No
   newline, platform encoding or map order participates.

There is no separate header hash. The verifier first recomputes the defined
`bundle_content_hash` over the exact bundle, then parses and checks the
canonical framed header bound by those bytes; receipts may not substitute a
CAS-wrapper hash or choose framed versus unframed header hashing.

The zero-member qualification vector uses
`proof_domain="conformance"`, `family="epoch"`,
`authority_purpose="publication"`, a 64-zero `scope_ref` digest,
`native_schema_profile="conformance.native@1"`, a 64-one denominator digest,
64-two cutoff digest and 64-three query-context digest. Its descriptor genesis
is
`sha256:70b86458fbe5bda54106d0c684165bc7f6096c2ade34e95dbcb14e04e9031af8`;
the canonical header is 773 bytes with framing prefix
`0000000000000305` and explicit `"first_commitment":null`; the empty bundle
is 781 bytes; and `bundle_content_hash` is
`sha256:48f4eed374a1155203437f296bf9f9f309233f7d8ba7c5fdc161c52df259390b`.
This dependency-free conformance vector is not runtime or admitted-family
evidence.

The header changes for a later requested cutoff; an already admitted `F_i`
does not. Thus appending M2 at C2 preserves M1's bytes from C1 even though
M1's member-admission context, M2's member-admission context and the C2
requested-query context are distinct refs. Two independent encoders must emit
identical frames, digests, heads and bundle size for 0, 1 and 2 members.
Substituting native bytes under an old frame, claiming empty against a
non-empty reconciled denominator, changing M1's original admission context or
requiring it to equal the C2 query context fails.

The v1 qualification horizon is the first of **2,500,000 members** or
**4,294,967,296 canonical replay-bundle bytes (4 GiB)**. At the member cap,
the 1,024-byte frame ceiling consumes at most 2,560,000,000 bytes and leaves
1,734,963,200 bytes after the 4,096-byte header for all framed native records.
As a stress witness only, 2,250,000 maximum-sized frames, 2,250,000 eight-byte
native length prefixes, the unrelated catalog's 524,288,000-byte aggregate and
the maximum header total 2,846,292,096 bytes—1,448,675,200 bytes below the
bundle cap. This does not convert that catalog into a movement forecast.

Crossing either numeric cap yields `proof_profile_capacity_exceeded` and fails
closed. It does not silently switch algorithms. The profile is reopened only
if one of these events occurs:

1. a canonical family denominator exceeds 2,500,000 members;
2. its complete canonical replay bundle exceeds 4 GiB;
3. an admitted consumer must verify membership without holding the full native
   history; or
4. an appointed consumer's measured latency/storage SLO is lower than the
   measured full-prefix replay at its declared operating cutoff.

The first appointed consumer must publish that benchmark and SLO receipt before
issuance. A Merkle transparency tree is deliberately out of v1. At four
families with no selective consumer and offline verifiers already required to
hold full history, it adds proof/profile/anchor/verifier complexity without
changing a measured decisive property. It may be reconsidered only at the
triggers above.

## 5b — feasibility against Decision Validity and Claim Ledger

### Decision Validity does not accept an authority-grade epoch trigger as-is

The current wire vocabulary can express
`HISTORICAL_SEMANTIC_REVISION` or `MODEL_INVALIDATION` and a `STALE` result
(`src/polisyos/core/contracts/decision_validity.py:21-74`). Its public event, however,
contains caller-supplied `trigger_type`, `status`, `dependency_keys`,
`source_ref` and an untyped payload
(`src/polisyos/core/contracts/decision_validity.py:178-195`). The service deduplicates,
looks up those supplied keys and applies the supplied status; it does not
resolve an epoch artifact, verify provenance/signature, recompute the
old-to-new epoch relation, or bind a native query coordinate
(`src/polisyos/scientist/validation/decision_validity.py:352-405`).

The envelope has no epoch/certificate dependency kind. The event has no
epoch-manifest/scope identity, native valid/effect plus visibility/admission
coordinates, old/new certificate refs, derivation input/recipe refs,
rule/profile versions, verifier provenance or signature. The isolated
`GroundingCertificateReference` staleness helper has zero source calls and does
not fill those fields. A valid-shaped generic event would therefore be a P37
`consumer_asserted` predicate and a P38 status/source-ref proxy.

Cluster 4 gains named prerequisite **C5-PREREQ-DV-EPOCH-ADMISSION**:

1. N12 persists a content-bound epoch-transition/staleness artifact carrying
   family, scope, explicit authority purpose,
   `requested_query_context_ref`, `bundle_content_hash`, exact parsed header
   and commitment head, old and new epoch/manifest member refs with immutable
   `member_admission_context_ref` values, complete basis refs, affected
   certificate/dependency refs, perturbation disposition, producer identity,
   schema/rule/proof profiles, signature and verifier provenance.
2. Before any mutation or dedupe write, Decision Validity resolves and verifies
   the artifact/prior state, rejects missing/wrong purpose or context, resolves
   the **complete affected packet denominator**, and computes every desired
   owner transition. Empty or unregistered targets fail with no state change.
3. Decision Validity derives event/dedupe identity from the verified artifact
   hash, requested-query context, sorted complete target packet refs and owner
   rule/profile version; callers cannot supply it. Before the first target
   mutation it persists a content-bound pending-batch freeze over the complete
   denominator. Every Decision Validity authority/public read consults that
   index. While pending, an orthogonal content-bound
   `pending_revalidation` limitation makes **every** target unusable in a
   public result, including a target not yet physically updated. Underlying
   owner status/history is preserved and effective authority is the more
   restrictive composition: an `ACTIVE` target may present
   `REVIEW_REQUIRED`, while `WITHDRAWN`, `REVOKED`, `STALE` or another stricter
   result remains that result plus pending and cannot reopen. Writes are
   idempotent. Only after all targets are reconciled does one owner transaction
   write the completion receipt and switch the index to complete. A crash
   leaves the freeze visible; recovery resumes it rather than treating the
   pending identity as completed dedupe.
4. Its envelope registers the exact epoch/certificate dependency. Decision
   Validity—not N12 and not the caller—derives `STALE`,
   `REVIEW_REQUIRED`, reissue or another native status. Reusing
   `HISTORICAL_SEMANTIC_REVISION` is permitted only behind that verified
   admission path; otherwise add an explicit epoch trigger type.
5. Fake verifier, false supplied status, wrong/missing purpose or coordinate,
   authentic-old epoch at a later query, an unregistered dependency and a
   caller-poisoned dedupe key all fail closed. Failure after the first of two
   target writes is observed before retry with one target initially active and
   one withdrawn/revoked: both remain authority-blocked and the terminal
   result remains terminal. Retry brings both to the owner result exactly once
   and only then emits completion.

This preserves the existing classification: the epoch trigger is
`producer_missing`, not `bridge_missing`. The syntax-shaped generic intake is
not the missing producer.

### Claim Ledger can express the transition, but only after Decision Validity

Claim Ledger v2 already has append-only `marked_stale`, `review_required`,
`reissued`, `withdrawn` and `invalidated` actions
(`src/polisyos/scientist/evidence/claims/lifecycle.py:26-57`). The governance bridge maps
raw `GovernanceMonitorEvent` values to those actions and persists a CAS
sidecar, but it accepts a detector-shaped event with an open metadata mapping
and copies affected claim IDs
(`src/polisyos/scientist/governance/continuous/monitors.py:85-105`;
`src/polisyos/scientist/governance/continuous/lifecycle_bridge.py:191-285,417-443`). It
does not authenticate epoch evidence or establish detector truth.

A complete 2,561-source-file AST walk finds one definition and zero source
calls for each of `bridge_governance_events_to_claim_lifecycle` and
`persist_lifecycle_bridge_result`; `mark_dependent_claims_stale` also has zero
source calls. Initial ledger construction is wired, but this lifecycle bridge
remains `implemented_but_not_orchestrated`.

Cluster 4 therefore gains **C5-PREREQ-CLAIM-DV-LIFECYCLE**:

1. chronology never sends raw authority directly to Claim Ledger;
2. after C5-PREREQ-DV-EPOCH-ADMISSION, the bridge resolves a persisted,
   **completed batch receipt** and verified Decision Validity transitions. It
   binds decision lineage, affected claim IDs, old/new ledger refs, run/ref
   context, epoch-transition evidence, authority purpose,
   `requested_query_context_ref` and the referenced old/new epoch member
   frames with their distinct immutable member-admission contexts;
3. Claim Ledger validates the native lifecycle transition and appends it,
   preserving the old claim and public history; and
4. the persisted bridge result binds all source and result refs. Wrong decision
   lineage, raw monitor metadata without the owner result, missing epoch
   evidence and an unverified supplied status fail closed.

The existing bridge vocabulary and persistence can be extended; no parallel
claim ledger is needed. Automatic derivation-recipe execution is still
`absent/unallocated` and stays with each artifact's canonical producer.

## 5c — `epoch_ref` inference attacked from the opposite position

The independent review brief was deliberately the strongest contrary case:
treat epoch as a genuine third temporal axis `E`, argue that CTM's sparse roles
cannot represent it, and exhibit two histories with identical valid/effect and
transaction/knowledge coordinates that a projection would collapse.

The reviewer supplied the decisive counterexample. At the same scope, purpose,
valid coordinate and knowledge coordinate, a retroactive semantic manifest E2
may be current while E1 remains authentic for an earlier certificate.
Alternatively, two same-predecessor manifests may be incomparable at exactly
the same native time coordinates. A query written only as `Q(V,T)` loses the
distinction; `Q(V,T,E)` keeps it. The finding is
**C5C-01 — SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking** against the
existing N13b/N12 coordinate-underbinding class.

The inference **survives under attack, with a mandatory sharpening**. The
counterexample proves that epoch identity is not derivable from valid/effect
and transaction/knowledge coordinates alone. It does not prove an
independently advancing clock or a new CTM time role. The missing discriminator
is content-addressed semantic version plus purpose-scoped owner admission and
native fork/predecessor relations. CTM already requires explicit family-native
query context and separates admission/currentness authority from time.

The binding formulation is:

> An `epoch_ref` is not a primitive CTM temporal role or independently
> advancing clock. It is an explicit content-addressed semantic-version
> coordinate carried in the epoch adapter's applicable member-admission and
> requested-query contexts and bound to purpose-scoped owner admission. It is
> not derivable from valid/effect and
> transaction/knowledge coordinates alone. Historical replay verifies the
> artifact-bound ref. Current resolution recomputes the owner-admitted
> applicable set at explicit scope, purpose and native coordinates: zero
> candidates yields `epoch_scope_unresolved`; multiple incomparable
> same-purpose candidates yield `contested`/`not_established` until the
> canonical owner adjudicates. No timestamp, transaction order, overlay
> counter or proof position selects one.

The falsifier is two distinct complete semantic manifests with the same scope,
purpose, native coordinates and predecessor. Historical replay must keep both
distinct; a current query must obtain owner adjudication or fail closed. If an
implementation chooses one from time/order/proof position, the inference has
been replaced by a hidden third clock and fails.

## 5d — decomposition recommendation

The recommendation is **narrow**: GY-N12 delivers the common protocol and epoch
family through Clusters 1–4. GY-GAP3, GY-GAP5 and GY-GAP6 become separate tasks
that consume the proven protocol and remain owned by their native producer and
denominator chains.

The wide case is real: a protocol with one production adapter can overfit to
epochs. The narrow path therefore requires Cluster 2 to include one
independently reviewed, non-authoritative second opaque conformance witness
using a materially different native record shape. It must prove generic
membership, deletion/substitution/reordering, profile/domain isolation and
old-to-new consistency, plus the inability to mint a native head, acceptance
or authority. It creates no release/run/movement producer, denominator,
persistence owner, currentness rule or acceptance receipt and cannot satisfy
programme end-to-end property J00. That is protocol conformance, not a hidden
GAP adapter.

Narrow sequencing is preferable because Clusters 5–7 are blocked on the
institutional decision in 5e regardless and each currently lacks a distinct
native producer/denominator chain. A wide GY-N12 would couple those sovereign
prerequisites to epoch delivery without providing additional proof-profile
evidence: no selective consumer exists, and genericity can be falsified at the
opaque protocol boundary.

The cost of narrow is a bounded residual: one production adapter plus a
non-authoritative witness cannot prove that all later native adapters are
correct. Each deferred task must rerun the frozen common protocol conformance
suite and its own native denominator/authority slice. The cost of wide is
implementing three absent capabilities, their surfaces and their still-missing
consumers before the shared custody decision; it delays the first complete
epoch chain and expands the single review denominator.

Routing is:

- Clusters 1–4 / GY-N12: consume the Foundry-owned GY-DEF22 identity; deliver
  the fixed common profile, epoch adapter, full semantic epoch resolution,
  OpenWorldRisk/cascade, and the two named owner bridges. Cluster 3 remains
  conditional on 5e.
- Cluster 5: GY-GAP3 plus GY-PA3 for controlled-release production,
  denominator and consumption.
- Cluster 6: GY-GAP5 plus the generation-cycle owner for the production
  boundary, receipts/gaps, terminals and enumeration.
- Cluster 7: GY-GAP6 plus N13b/N7 and DS7 composition owners for complete
  eligible rows and movement.
- Family surfaces stay with their task. Common proof conformance stays with
  GY-N12.

The accepted 128-property closure basis remains the programme-wide basis. A
narrow GY-N12 may not claim 128/128: the 9 release, 11 run and 11 movement
family properties alone are 31 explicitly deferred properties, and
cross-cutting H/J properties must be mapped to their real chain rather than
counted by cluster location.

The complete non-overlapping responsibility partition is below. Counts route
work; they are **not** a closure score, do not imply 97/128 for N12, and do not
promote any current capability label.

| primary responsibility / condition | exact basis IDs | count | no-holder / with-holder status |
| --- | --- | ---: | --- |
| N12 common/profile slice | A01–A07; B01–B03, B05–B08, B10–B17; H01, H02, H04–H06, H10, H11, H14, H16, H17; J05 | 34 | builds/tests supplied-head protocol and owner boundaries in either decision; no-holder does not establish accepted whole history |
| N12 epoch/OpenWorld/cascade slice | C00–C10A; D01–D13A; H03, H07, H18–H22; J01A | 40 | deliverable only to each property's native owner/bridge label; no-holder caps chronology authenticity but does not erase owner-derived epoch/currentness results |
| N12 anchor-dependent slice | B04, B09, B09A; H08, H12, H15; J01, J06 | 8 | `not_established`/blocked at whole-history acceptance without appointment; eligible for implementation, not automatically closed, with the appointed consumer+holder |
| Foundry-owned GY-DEF22 prerequisite consumed by N12 | H09; I01–I06 | 9 | owner remains Foundry N8/N10a; holder decision does not transfer it |
| GY-GAP3 / GY-PA3 | E01–E09; J02 | 10 | deferred; its holder-dependent claims remain `not_established` until its competent consumer uses the appointed holder |
| GY-GAP5 / generation-cycle owner | F01–F10; H13, H13A; J03 | 14 | deferred; producer terminals remain native under either holder decision |
| GY-GAP6 / N13b-N7-DS7 | G00–G09; J04 | 12 | deferred; endpoint truth remains native under either holder decision |
| programme capstone | J00 | 1 | cannot close in narrow N12; requires all four native chains plus their competent acceptance and holder retention |

The exhaustive arithmetic is `34+40+8+9+10+14+12+1=128`. Range notation in
this table includes every suffixed ID printed between the named endpoints in
the frozen basis (for example B09A, C03A and D06A–D06D); the lists are
independently expanded and duplicate-free.

## 5e — anchor-custody decision brief

### Required behavior

A competent **family anchor consumer** must independently resolve the expected
family/scope/cutoff, canonical denominator status, requested native coordinate
and expected prior accepted anchor. It verifies actual canonical bytes,
profile/domain/scope binding, complete accepted lineage, signature and verifier
provenance; recomputes or independently reconciles every decisive P37
predicate; rejects an authentic old anchor used for a later query; and emits a
content-bound acceptance receipt. The receipt explicitly binds authority
purpose, `requested_query_context_ref`, the defined `bundle_content_hash`,
exact parsed header, commitment head, prior accepted anchor, consumer identity
and the immutable member refs/commitments it evaluated. It does **not** require the
requested-query context to equal any member-admission context. The receipt
separates member integrity, denominator completeness, native
authority/currentness and global/latest knowledge. The proof never decides the
latter three.

A **writer-independent holder** retains the exact accepted receipt and frozen
acceptance package outside the chronology writer's mutation authority. It
must:

1. ingest only a competent consumer-signed receipt, never a writer's
   `accepted=true`;
2. retain exact bytes, prior-anchor lineage, consumer identity, family/scope,
   authority purpose, requested-query context, `bundle_content_hash`, exact
   parsed header, commitment head, query/cutoff, profiles,
   verifier/admission provenance and every frozen P37 class; its lookup index
   keys family/scope/purpose/query context and consumer rather than equating
   query and member contexts;
3. prevent the writer from overwrite, deletion, retention-policy change or
   re-originating history;
4. support durable exact-ref readback and independent replay/challenge;
5. expose a typed receipt or non-receipt and fail closed on unreadable,
   expired, missing or divergent custody; and
6. preserve old/withdrawn anchors as historical evidence.

Its decisive falsifier compromises the writer, rewrites an internally
consistent history and every anchor still writable by that writer, then
replays against the holder's retained accepted bytes. The rewrite must be
exposed. Unknown external heads still prevent any global/latest claim.

### Candidate arrangements in this repository's operating reality

| arrangement | actual custody boundary | decision |
| --- | --- | --- |
| local filesystem CAS, local Git objects/refs or local chained audit JSONL | same machine and operating principal as the writer | no boundary; content addressing/tamper evidence cannot establish independent custody |
| commits, branch, tags or release records in the current GitHub repository | an external host location, but tracked CODEOWNERS assigns the enforceable personal-repo owner to `@DenisKopylov`; live ruleset/environment enforcement and bypass authority have no exported receipt | appears separate by location, not by proven mutation authority; `not_established` |
| GitHub Actions artifacts, provenance attestations and releases | workflow declares 180-day artifacts, OIDC provenance and a `release-production` environment, but no run/artifact/protection receipt is tracked and the release workflow holds `contents: write` | intended cross-service handoff, not a durable writer-independent holder |
| keyless Sigstore/Rekor path | could cross to an external transparency service, but current SLSA mode defaults off/local and no chronology-bound inclusion/identity receipt exists | candidate witness only; not a holder today |
| generic S3/GCS CAS | remote location is selectable by environment, but no bucket, versioning/Object Lock, separate credentials or receipt is tracked | deployment and independence `not_established` |
| existing S3 Object Lock audit cold tier | generic audit replication is implemented and conditionally orchestrated; it writes asynchronously and softens replica failure, with retain-until fixed to January 1 of current UTC year + 7; no deployed bucket/policy, independent principal, holder-side acceptance, object receipt, lineage lookup, readback/challenge or chronology intake exists | strongest reuse component only; chronology holder remains `absent/unallocated` and deployed independence `not_established` |
| separately credentialed Object Lock custody using the cold-tier mechanism | holder account/principal and retention policy are outside writer control; family consumer signs before storage; readback/challenge is independently available | a genuine boundary if appointed and receipted |

The tracked repository ruleset explicitly says it is active only when applied;
CODEOWNERS describes the personal-repo exception
(`.github/repository-rulesets/main.yml:3-19,40-47`;
`.github/CODEOWNERS:6-18`). The release workflow's own preflight and 180-day
retention do not prove host immutability
(`.github/workflows/release.yml:50-58,113-129,373-468`). The reusable cold-tier
component is at `src/polisyos/core/security/audit_sink.py:145-209,408-426`, and
RunContext's opt-in wiring is at `src/polisyos/core/run/context.py:297-318`. These are
component and contract evidence, not deployment receipts.

### Honest claim ceiling if no holder is appointed

Without a holder, all families may prove only profile-bound member/content
integrity and append consistency **relative to a supplied head**. A family may
separately reconcile its complete native denominator at a declared cutoff and
its native owner may separately establish currentness/terminality. None of
those facts establishes an authentic accepted whole history.

| family | still deliverable with whole-history authenticity `not_established` | unavailable without a holder |
| --- | --- | --- |
| epoch | derive/replay a complete fixed-semantics manifest at explicit coordinates; reconcile boundary/facet denominator; propagate owner-admitted staleness through Decision Validity | authentic complete epoch history, accepted-anchor lineage, proof-derived currentness or global/latest |
| controlled release | bind each presented release and independently reconcile the required-release denominator at cutoff; detect mutation relative to the supplied head | consumer-accepted transcript, PV-K07 issuance, whole-history/global-latest claim |
| recursive run | bind presented events to exact problem/graph/cycle and preserve producer-owned terminals; conditionally reconcile a complete live-boundary denominator once it exists | “all production runs” from a projection, proof-derived terminal/head, whole-history/global-latest claim |
| movement | bind each eligible row to exact passport/problem/run/re-entry/endpoints and reconcile movement/no-movement/gap once its denominator exists | movement from adjacency/silence, independent movement authority head, whole-history/global-latest claim |

Historical authenticity of a particular signed member is not erased by the
missing current holder. What remains unavailable is the stronger claim that
the supplied origin/prefix is the complete consumer-accepted history and was
not replaced before that origin.

### Decision requested and recommendation

If only one institutional appointment is made, appoint a cross-family
**Chronology Anchor Custodian** as the neutral retained holder, not as a
semantic authority. Reuse the S3 Object Lock cold-tier mechanism behind a
separate account/principal and compliance retention policy; accept only
family-consumer-signed receipts; export content-bound put/version/retention
receipts; and provide independent readback/challenge. The chronology writer
must not control the holder account, deletion, retention or receipt log.

This appointment unblocks the largest common edge: one custody boundary can
retain accepted anchors for all four proof domains without becoming a parent
scope or authority owner. It does **not** make one generic consumer competent
for four families. Decision Validity can become the epoch consumer after the
5b prerequisite; GY-PA3, the generation-cycle chain and the N13b/N7
composition chain must each establish their native acceptance predicate in
their own task.

The alternatives are:

- appoint an epoch-only Decision Validity/publication custodian. This closes the
  narrow first chain sooner but repeats the institutional holder decision for
  GAP3/5/6; or
- deliberately appoint no holder. Then Clusters 1, 2 and the non-authenticity
  portions of 4 remain deliverable, Cluster 3 is skipped, Clusters 5–7 remain
  blocked at whole-history authenticity, and every affected surface must carry
  `not_established`.

The requested user decision is therefore: **appoint the shared neutral holder,
appoint an epoch-only holder, or deliberately proceed with no holder and the
claim ceiling above**. No artifact can make this appointment for itself.

## Review rule and Wave-1 disposition

Every Cycle-5 reviewer receives this rule before review: classify each
observation as `NEW_CLASS` or `SAME_CLASS_ONE_LEVEL_DEEPER`, then identify
`design`, `record` or `research_method` and blocking/cosmetic. On the second
finding of a class, widen the mechanism or state a bounded residual and run its
falsifier; do not patch another instance. Findings in this research phase
consume no implementation round.

The frozen Cycle-4 closure basis is unchanged. Cycle-5 review is delta-only,
content-bound and capped at 28KB per serialized packet. The initial design
delta was 21,136 bytes / SHA-256
`11cc34b0a88f852e5b1b79fadfae5959c2500b486ce4df2d0d733341525ed522`.
The initial journal no-index packet was 27,966 bytes / SHA-256
`aa8effd86dca78c29e302503ed1d255a061e356118a54f6775c90289eec50698`;
its raw file was 27,192 bytes / SHA-256
`8e94bd0205e46375b2e806f03cd1f7694530995743206cbb5e7e27f83e20c9cf`.
All three reviewers independently reproduced their target.

Wave 1 was **not clean**, with five blocking buckets and no cosmetic finding:

- **C5D-R1 — SAME_CLASS_ONE_LEVEL_DEEPER / design:** exact proof encoding,
  genesis and member-admission versus bundle-query binding were underdefined.
- **C5D-R2 — SAME_CLASS_ONE_LEVEL_DEEPER / design:** Decision Validity could
  persist an unverified dedupe key or expose partial multi-packet mutation.
- **C5R-J01 — SAME_CLASS_ONE_LEVEL_DEEPER / design:** purpose/admission context
  was not bound through frame, transition, receipt and holder lookup. Duplicate
  witnesses were folded; the repair widens every epoch-bearing layer.
- **C5R-J02 — SAME_CLASS_ONE_LEVEL_DEEPER / record:** the generic audit
  component's maturity was promoted to chronology-holder maturity.
- **C5R-J03 — SAME_CLASS_ONE_LEVEL_DEEPER / record:** E/F/G subtraction did not
  partition all cross-cutting H/J responsibilities or holder conditions.

The Wave-1 repair packet introduced the immutable-member/bundle split,
purpose-scoped context binding, verified full-denominator batch admission,
explicit component/capability labels and the 128-ID partition above. It was
then frozen as the Wave-2 baseline rather than treated as clean.

## Wave-2 return review and widened repairs

The Wave-2 design delta was exactly 9,959 bytes / SHA-256
`0e65d31ee5f93689bd9f1060da84937f2ae75cd4d2f50f6730e6cfc71f13d0f6`.
The Wave-2 journal delta was exactly 17,368 bytes / SHA-256
`9684981c6b21290799327d331e8dce0181bc5fc065a77d0f1400d8275c44d121`.
The design reviewer and both journal reviewers reproduced their targets.
Wave 2 was **not clean**, with three folded blocking design classes and no
cosmetic finding:

- **C5D-R1-W2 / C5W2-J02 / C5R2-J02 —
  SAME_CLASS_ONE_LEVEL_DEEPER:** the exact-profile class still left digest
  representation, native-byte recomputation and the zero-member state
  underdefined. This was the second class occurrence, so the property is now
  widened to byte identity and verifier recomputation for every cardinality
  and native payload, with exact descriptor/digest/null/genesis rules.
- **C5R-J01-W2 / C5W2-J01 / C5R2-J01 —
  SAME_CLASS_ONE_LEVEL_DEEPER:** one universal context both rebuilt CTM's
  refuted envelope and required immutable C1 member admission to equal a C2
  query. This was the second context-binding occurrence, so the design now has
  two typed opaque roles: sparse family-native
  `member_admission_context_ref` per member and
  `requested_query_context_ref` per bundle/consumer decision.
- **C5W2-J03 — SAME_CLASS_ONE_LEVEL_DEEPER:** completion-only receipt did not
  fail closed during a crash after one of multiple Decision Validity writes.
  The widened owner property persists a denominator-wide pending freeze before
  mutation and makes every authority/public read consult it.

The falsifier set is 0/1/2-member independent encoding, native-byte
substitution under an unchanged frame, an asserted-empty header against a
non-empty reconciled denominator, M1@C1 plus M2@C2 with distinct query context,
a family schema with no epoch/fork, and a two-target crash observed before
retry.

## Wave-3 return review and widened repairs

The Wave-3 design delta was exactly 14,134 bytes / SHA-256
`4c31dc007e9d31a549f75cd86307966b5de9f30723ae20c16c7a1f353a27d22a`.
The Wave-3 journal delta was exactly 17,321 bytes / SHA-256
`927e5405ccb4bc28c3c5bb22ab59bdbd7aa640829e30afaddef6ccd9b7331770`.
All three reviewers reproduced the exact target assigned to them. Wave 3 was
**not clean**, with four folded blocking classes and no cosmetic finding:

- **C5D-R1-W3 / C5W3-J01 / C5R3-J01 —
  SAME_CLASS_ONE_LEVEL_DEEPER / design:** the exact-profile property did not
  pin the full `CanonSpec`/raw input and named a separate header hash with no
  preimage rule. The repair pins `exclude_none=False` and every other
  canonicalizer option, rejects model/dataclass inputs, adds the zero golden
  vector, and removes the redundant header hash in favor of the defined full
  bundle digest.
- **C5R-J01-W3 — SAME_CLASS_ONE_LEVEL_DEEPER / design:** the requested-query
  context still made currentness universal. It now always carries denominator
  completeness but carries currentness/terminal/head predicates only when the
  family declares them applicable; no `not_established` placeholder is
  fabricated for an inapplicable movement predicate.
- **C5D-R2-W3 — NEW_CLASS / design:** a pending batch projected every target
  as `REVIEW_REQUIRED` and could weaken a withdrawn/revoked result. Pending is
  now an orthogonal authority limitation composed monotonically with the
  preserved owner status.
- **C5W3-J02 — SAME_CLASS_ONE_LEVEL_DEEPER / record:** the Wave-2 record said
  four folded buckets but enumerated three folded classes. The count is now
  three.

The added falsifiers reproduce every named digest at zero/one/two members,
verify a movement query without a synthetic movement currentness/head field,
and crash a batch containing an active plus withdrawn/revoked target. The
eventual clean terminal receipt remains detached because recording it would
change the bytes it reviewed.

## Wave-4 substantive review result

The Wave-4 design delta was exactly 7,863 bytes / SHA-256
`4c2bc4b3a1a4ad4f2c3bf517b15c1eafca68da9b177c3922eea675ea248aa551`.
The Wave-4 journal delta was exactly 11,431 bytes / SHA-256
`4206c4e562fe87a0b59fd1dd732d377b11da0d96cf08523d54e1d9cf8fcb7e7a`.
The design reviewer and both independent journal reviewers reproduced their
exact targets and returned **CLEAN-4** with zero blocking and zero cosmetic
findings.

All three independently reproduced the zero-member genesis, 773-byte header,
`0000000000000305` frame, 781-byte bundle and bundle digest. They also
confirmed that no separate header digest remains, context predicates are
family-native and sparse, pending revalidation cannot weaken a terminal owner
status, the Wave-3 receipt is exact, and the responsibility partition remains
128 unique IDs with no omission or duplicate.

This closes Cycle-5 substantive specification review. The only subsequent
tracked changes are this review receipt and the design status line. Their
terminal status-only review remains detached: recording that clean receipt
would change the bytes it reviewed.
