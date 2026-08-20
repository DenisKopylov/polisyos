# GY-N12 Cycle 2 — Outward Prior Art

## Receipt, authority and method

Cycle 2 is research data for the GY-N12 specification. It is not an imported
standard and does not override the Custody Time Model, INT-K05, PV-K02,
S0-K05/S0-K07 or INT-K08. Sources were selected for the exact properties in
the task: append-only membership and consistency, two-time correction,
immutable replay and heads, certificate freshness, lineage invalidation,
correction/retraction vocabulary and operational cost. Primary standards,
official specifications, vendor documentation and original research were
preferred. Every adoption below states what decisive PolicyOS property it
changes and what it cannot establish.

Three independent read-only research lanes covered: (1) transparency logs and
immutable-history stores; (2) bitemporality, provenance and executable
lineage; and (3) certificate and scholarly lifecycle. Root independently
checked their sources and reconciled the conclusions against the Cycle 1
substrate census. No runtime or deployment tooling result is admitted: the
Cycle 1 toolchain gate remains in force and GY-DEF22 remains open.

### Attribution and proposition-completeness protocol

Every conclusion in this record has one of three warrants:

- **`external-source fact`** reports only a proposition established by the
  linked external source. The source-to-claim ledger below is the binding
  proposition denominator.
- **`PolicyOS inference`** is root's reconciliation of external facts with this
  repository. It has no external authority and cites its governing internal
  owner: Custody Time Model §§3/4/6, `S0-K05`/`S0-K07`, `INT-K05`/`INT-K08`,
  `PV-K02`/`PV-K07`, or the registered `GY-GAP5` rule.
- **`ratified constraint`** restates only the named internal finding. External
  material cannot amend it.

The “what the field gives” paragraphs are `external-source fact`; every
“verdict”, “limit”, “import decision”, seam table, design constraint and Cycle
3 question is a `PolicyOS inference` unless explicitly marked otherwise. A
mixed paragraph is invalid. The method falsifier is proposition-level: if a
linked page lacks the decisive predicate attributed to it, that claim fails
review even when the source is adjacent, reputable or topically related.

Internal authority owners for PolicyOS inferences are
[Custody Time Model §3/§4/§6](../../system-design-decisions/policy-design-custody-time-model.md),
[S0-K05/S0-K07](../../system-design-decisions/stage0-custody-kernel-ratification.md),
[INT-K05/INT-K08](../../system-design-decisions/int-wave-claim-semantics-ratification.md),
[PV-K02/PV-K07](../../system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md),
and the
[GY-GAP5 registered producer rule](../../plans/active/layer3-slices/GY-engine-subordination.md).

| source claim ID | external-source fact | direct source |
| --- | --- | --- |
| `C2-E01` | Tree heads commit size/root; inclusion proves a leaf in one tree; consistency proves append-only extension of a pinned prefix; proof paths are logarithmic; auditors need not retain the whole live log while operator/monitor storage grows with entries; isolated auditing does not establish global latest/split-view absence and gossip is not standardized. | [RFC 6962](https://www.rfc-editor.org/rfc/rfc6962.html), [RFC 9162](https://www.rfc-editor.org/rfc/rfc9162.html) |
| `C2-E02` | Classical temporal literature distinguishes valid time from transaction time and treats them as separate dimensions. | [Snodgrass/Ahn](https://doi.org/10.1145/971699.318921), [Jensen/Snodgrass 1994](https://www2.cs.arizona.edu/~rts/pubs/TKDEDec94.pdf), [1999 survey](https://homes.cs.aau.dk/~csj/Papers/Files/1999_jensenIEEETKDE.pdf) |
| `C2-E03` | The 2011 SQL/Foundation record exists and is withdrawn; current Part 2 is 2023; implementations document application/business time, system history, two-coordinate queries, and correction by changing/splitting application validity while preserving later system history. | [ISO 2011](https://www.iso.org/standard/53682.html), [ISO 2023](https://www.iso.org/standard/76584.html), [MariaDB](https://mariadb.com/docs/server/reference/sql-structure/temporal-tables/system-versioned-tables), [IBM model](https://www.ibm.com/docs/en/ida/9.2.x?topic=models-modeling-temporal-data), [IBM query](https://www.ibm.com/docs/en/db2/12.1.x?topic=bt-querying), [Microsoft](https://learn.microsoft.com/en-us/sql/relational-databases/tables/temporal-tables?view=sql-server-ver17) |
| `C2-E04` | Event sourcing retains an entry-growing append-only entity stream, replays it to project current state, uses compensating events rather than rewriting old events, and may use snapshots to bound replay as an optimization. | [Azure Event Sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing) |
| `C2-E05` | Datomic retains transaction-basis `as-of`/history under ordinary retraction; excision removes historical datoms while retaining an excision marker/predicate. | [Datomic overview](https://docs.datomic.com/datomic-overview.html), [filters](https://docs.datomic.com/reference/filters.html), [excision](https://docs.datomic.com/operation/excision.html) |
| `C2-E06` | Iceberg has a main current-snapshot head, branch heads, resettable lineage/snapshot-log distinctions and snapshot expiration; Delta has versioned time travel whose retention/VACUUM can remove replay files. | [Iceberg spec](https://iceberg.apache.org/spec/), [branching](https://iceberg.apache.org/docs/latest/branching/), [maintenance](https://iceberg.apache.org/docs/latest/maintenance/), [Delta time travel](https://docs.delta.io/delta-batch/), [VACUUM](https://docs.delta.io/delta-utility/) |
| `C2-E07` | CRLs pay signed batch distribution/storage while OCSP pays responder availability/freshness/caching; both carry effective/freshness/succession distinctions, reason/temporary-hold semantics and `good`/`revoked`/`unknown`; unknown/expired status is not fresh positive status and online revocation commonly has soft-fail weakness. | [RFC 5280](https://www.rfc-editor.org/rfc/rfc5280.html), [RFC 6960](https://www.rfc-editor.org/rfc/rfc6960.html), [RFC 9325 §7.5](https://www.rfc-editor.org/rfc/rfc9325.html#section-7.5) |
| `C2-E08` | A client that negotiated the feature is directed to reject absent/invalid stapled status, but other proof and an insecure fallback are described; rejection is not unconditional. | [RFC 7633 §4.2.3.1](https://www.rfc-editor.org/rfc/rfc7633.html#section-4.2.3.1) |
| `C2-E09` | A no-revocation-available signal exists, chiefly suited to bounded short lifetimes, with weaker compromise response. | [RFC 9608](https://www.rfc-editor.org/rfc/rfc9608.html) |
| `C2-E10` | PROV represents derivation, revision, generation/usage, invalidation and plans, and defines formal ordering/consistency constraints; representing a plan does not execute it. | [PROV-O](https://www.w3.org/TR/prov-o/), [constraints](https://www.w3.org/TR/prov-constraints/), [semantics](https://www.w3.org/TR/prov-sem/) |
| `C2-E11` | OpenLineage represents jobs, runs, inputs, outputs and partial accumulated events. | [object model](https://openlineage.io/docs/spec/object-model/) |
| `C2-E12` | Actual dependencies must be covered by declared dependencies; unregistered reads can yield incorrect incrementality; Skyframe invalidates reverse transitive closure with all-or-nothing dependent rebuilds; actions declare inputs/output names/command/environment; remote cache separates an action-hash→result-metadata map from a CAS of output files, and untracked external tools can cause wrong shared cache hits. | [Bazel dependencies](https://bazel.build/concepts/dependencies), [Skyframe](https://bazel.build/reference/skyframe), [remote caching](https://bazel.build/remote/caching) |
| `C2-E13` | Dagster can propagate asset updates and run partition backfills. | [automation](https://docs.dagster.io/guides/automate/declarative-automation), [backfills](https://docs.dagster.io/guides/build/partitions-and-backfills/backfilling-data) |
| `C2-E14` | Publishing systems preserve linked original/notice metadata, distinguish concern/correction/retraction/withdrawal/removal, reserve physical removal for exceptional cases, propagate machine-readable status, and identify the supplying publisher/transport role rather than silently replacing the original. | [COPE](https://publicationethics.org/sites/default/files/retraction-guidelines-cope.pdf), [NISO](https://www.niso.org/publications/rp-45-2024-crec), [Crossref participation](https://www.crossref.org/documentation/crossmark/participating-in-crossmark/), [Crossref updates](https://www.crossref.org/documentation/register-maintain-records/maintaining-your-metadata/registering-updates/) |
| `C2-E15` | SQL Server history grows under update/delete load, adds storage/query cost, and retention can remove old history. | [Microsoft retention](https://learn.microsoft.com/en-us/sql/relational-databases/tables/manage-retention-of-historical-data-in-system-versioned-temporal-tables?view=sql-server-ver17) |

`C2-E01`–`C2-E15` are source facts only. Every “therefore PolicyOS should” move
below is separately labeled as inference and remains provisional until Cycle 3.

The complete external-fact **use** denominator is 21 blocks. This is distinct
from the 15 proposition rows above: one proposition may be used in several
places, but every use must cite its row. The census is frozen for this Cycle 2
record:

| use block | location | proposition rows |
| --- | --- | --- |
| `C2-U01` | §1 field mechanism | `C2-E01` |
| `C2-U02` | §1 required-submission limit | `C2-E01` |
| `C2-U03` | §1 split-view limit | `C2-E01` |
| `C2-U04` | §2 bitemporal field | `C2-E02`, `C2-E03` |
| `C2-U05` | §3 event sourcing | `C2-E04` |
| `C2-U06` | §3 Datomic | `C2-E05` |
| `C2-U07` | §3 snapshot formats | `C2-E06` |
| `C2-U08` | §4 certificate lifecycle | `C2-E07`, `C2-E08`, `C2-E09` |
| `C2-U09` | §5 PROV | `C2-E10` |
| `C2-U10` | §5 OpenLineage | `C2-E11` |
| `C2-U11` | §5 Bazel | `C2-E12` |
| `C2-U12` | §5 Dagster | `C2-E13` |
| `C2-U13` | §6 publishing lifecycle | `C2-E14` |
| `C2-U14` | cost: transparency | `C2-E01` |
| `C2-U15` | cost: bitemporal | `C2-E03`, `C2-E15` |
| `C2-U16` | cost: immutable stores | `C2-E04`, `C2-E05`, `C2-E06` |
| `C2-U17` | cost: certificate status | `C2-E07`, `C2-E08`, `C2-E09` |
| `C2-U18` | cost: lineage/recompute | `C2-E10`, `C2-E11`, `C2-E12`, `C2-E13` |
| `C2-U19` | cost: publishing status | `C2-E14` |
| `C2-U20` | Cycle 3 limit: isolated transparency | `C2-E01` |
| `C2-U21` | Cycle 3 limit: per-entity/per-branch history | `C2-E04`, `C2-E06` |

Completeness invariant: the set of external-fact use blocks in the document
must equal `C2-U01`–`C2-U21`, every use cites at least one `C2-E*` row, and
every cited row contains the decisive proposition actually used. Adding an
external-fact sentence without extending both denominators is the falsifier
and must fail review. This closes the method at the set level rather than by
adding exceptions for individual citations.

## Result in one page — PolicyOS inferences

These are Cycle 2 inferences governed by CTM §§3/4/6, S0-K05/S0-K07,
INT-K05/INT-K08, PV-K02/PV-K07 and GY-GAP5; none is an external-source fact.

1. A semantic epoch is a **scoped, content-bound projection**, not a third
   clock. Valid/effect time answers when a fact applies; transaction/knowledge
   time answers what the system had recorded; the epoch selects the fixed
   model/rule/schema/data/interpretation basis resolved at explicit native
   coordinates.
2. RFC 9162-style inclusion and append-only consistency proofs are the right
   proof algebra for a controlled prefix. A compact offline proof bundle is
   proportionate; a public Certificate Transparency service, universal log,
   maximum-merge-delay policy and global gossip network are not.
3. A Merkle proof establishes integrity only for **admitted leaves relative to
   an accepted head**. It cannot prove that a required release was submitted
   or that every production run crossed the recorder. Complete membership
   still requires independent reconciliation to each canonical source
   denominator.
4. Event sourcing, Datomic and snapshot table formats offer useful native
   persistence and replay patterns. None supplies the required portable
   completeness proof, and retention/excision/rollback features can violate
   permanent custody if treated as the canonical history.
5. Certificate and scholarly lifecycles both separate historical authenticity
   from current reliance. Unknown or stale status is not positive status; a
   retracted object normally remains identifiable and linked. Neither field
   supplies PolicyOS's exact-lineage authority cascade.
6. W3C PROV supplies interoperable derivation/invalidation vocabulary but not
   owner adjudication or automatic recomputation. Build-system lineage shows
   that a recipe can drive recomputation only when its declared dependency and
   environment closure is complete.

## 1. Append-only transparency logs

### What the field gives — external use `C2-U01` → fact `C2-E01`

[RFC 6962](https://www.rfc-editor.org/rfc/rfc6962.html) and its successor
[RFC 9162](https://www.rfc-editor.org/rfc/rfc9162.html) define Merkle-tree
transparency logs. A signed tree head commits to a tree size and root hash.
An inclusion proof establishes that a leaf belongs to that pinned tree. A
consistency proof establishes that the first `m` leaves of a later tree are
exactly the earlier tree: the later head is an append-only extension rather
than a rewritten prefix. Proof material grows logarithmically with tree size,
so an auditor can verify a retained member and a head transition without
retaining the operator's whole live store.

**PolicyOS inference — PV-K07/GY-GAP3.** This can change GY-GAP3's decisive
property. If the family opening,
canonical leaf bytes, release identity, model/rule/input identities, verifier
disposition and verifier provenance are committed before admission, deletion,
substitution, reordering or post-hoc prefix narrowing fails against a retained
earlier head. The portable offline bundle needs at least:

- log/proof-domain identity and canonicalization version;
- family-native member bytes or their content commitment;
- leaf index and tree size;
- inclusion proof to the accepted head;
- earlier and later accepted heads plus their consistency proof; and
- signer/verifier provenance and the declared family-basis commitment.

**PolicyOS inference — P37/S0-K05/PV-K07.** Location outside the transcript is
not enough. An accepted head must freeze the accepting owner, proof-domain/log
identity, signature, prior anchor, admission cutoff, witness or consumer-
receipt basis, verifier provenance and its admission provenance class. At
least one accepted anchor must be held across a custody boundary the transcript
writer cannot rewrite. Replacing the transcript plus every head writable by
the same actor must fail against that independent anchor. If no such anchor is
available, the strongest result is consistency relative to a supplied head;
whole-history authenticity is `not_established`. An unknown external copy is a
typed limitation, not evidence that the presented head is globally latest.

### What it does not give — fact and inference separated

**External use `C2-U02` → fact `C2-E01`:** transparency proves submitted-leaf inclusion
and prefix consistency; it does not claim a required-submission denominator.
**PolicyOS inference — P37/PV-K07/GY-GAP5:** a release family still needs a
complete immutable declaration reconciled by its owner. A production run
omitted before admission is indistinguishable from a run that never occurred
unless a production-boundary receipt or independently complete launch/emission
denominator exists.

**External use `C2-U03` → fact `C2-E01`:** RFC 9162 does not make an isolated verifier
omniscient. Split-view
detection depends on independent parties comparing heads or copies; the RFC
does not standardize universal gossip.

**PolicyOS inference — CTM §3/S0-K05/S0-K07:** tree timestamps establish no
Custody Time Model role beyond the integrity/receipt context assigned by the
family. Inclusion establishes historical membership, not current validity,
admissibility or publication authority.

### Import decision — PolicyOS inference

**Adopt the proof properties, not the service topology.** The Cycle 3 candidate
is family-scoped canonical digests, retained accepted heads, inclusion proofs
and old-to-new consistency proofs behind one reusable verifier protocol.
Reject a public-log service, global event stream, universal signed-head clock,
global freshness policy and the claim that Merkle membership alone proves a
complete denominator.

## 2. Bitemporal data models

### What the field gives — external use `C2-U04` → facts `C2-E02`/`C2-E03`

Classical temporal database work separates valid time—when a fact is true in
the modeled reality—from transaction time—when that fact is current in the
database. Jensen and Snodgrass describe them as orthogonal dimensions in
[Temporal Specialization and Generalization](https://www2.cs.arizona.edu/~rts/pubs/TKDEDec94.pdf)
and survey their distinct accountability roles in
[Temporal Data Management](https://homes.cs.aau.dk/~csj/Papers/Files/1999_jensenIEEETKDE.pdf).
The historical taxonomy begins with Snodgrass and Ahn's
[A Taxonomy of Time in Databases](https://doi.org/10.1145/971699.318921).

ISO records the withdrawn
[SQL/Foundation 2011 edition](https://www.iso.org/standard/53682.html) and the
current [ISO/IEC 9075-2:2023](https://www.iso.org/standard/76584.html).
[MariaDB's system-versioning documentation](https://mariadb.com/docs/server/reference/sql-structure/temporal-tables/system-versioned-tables)
identifies the SQL:2011 temporal feature directly. Concrete bitemporal
implementations combine application/business-time periods with system-
versioned history. IBM describes application time as real-world validity and
system time as when a transaction changed the row, and supports queries at both
coordinates in
[its bitemporal model](https://www.ibm.com/docs/en/ida/9.2.x?topic=models-modeling-temporal-data)
and [Db2 query semantics](https://www.ibm.com/docs/en/db2/12.1.x?topic=bt-querying).
Microsoft's
[system-versioned tables](https://learn.microsoft.com/en-us/sql/relational-databases/tables/temporal-tables?view=sql-server-ver17)
retain prior row versions and reconstruct transaction-time state.

A correction can therefore backdate or split the domain-valid interval while
the later system-time version preserves when the database learned or recorded
the correction. A bitemporal query answers, in effect: “what was applicable at
valid coordinate V according to the history visible at transaction coordinate
T?”

**PolicyOS inference — CTM §3:** those two external axes do not establish a
third epoch clock. PolicyOS semantic-version selection remains a separate
content/authority question resolved below.

### Epoch verdict and limit — PolicyOS inference

Reconciliation of external two-axis facts `C2-E02`/`C2-E03` with the ratified
CTM §3 relations/query-coordinate model yields the provisional Cycle 2
inference that an N12 epoch is **not a third temporal axis**. It is a discrete,
scoped equivalence class over the complete fixed semantic basis resolved at explicit
native coordinates. Persisted `epoch_ref` is a replay selector with content
and predecessor commitments, not a clock. The resolver must receive applicable
valid/effect coordinates, transaction/knowledge cutoff and the authority
context needed by the family. The current epoch head is the latest applicable
owner-admitted semantic successor, not the maximum timestamp.

Bitemporality alone cannot say whether a rule change is semantic, whether a
renumbering with an unchanged logic hash is annotation-only, whether evidence
is authoritative, or whether a certificate remains publishable. Those are
owner-adjudicated semantic predicates. History retention policies also can
delete system-time rows, so database time travel cannot be the sole PV-K02
custody proof.

### Import decision — PolicyOS inference

Reuse Fabric's valid-time/transaction-time semantics and explicit query
coordinates. Derive an immutable `epoch_ref` from the complete admitted
semantic basis. Reject a new epoch timestamp, a global `as_of`, “latest row”
as head, or chronology order as a proxy for applicability.

## 3. Immutable history, event sourcing and time travel

### Event sourcing — external use `C2-U05` → fact `C2-E04`

The [Azure Event Sourcing pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
uses an append-only per-entity stream as source of truth; current state is a
projection obtained by replay, and snapshots reduce replay cost. Corrections
are compensating events rather than mutation of old events.

**PolicyOS inference — CTM §4/§6:** this fits family-native append history and
materialized current projections.
It does not define portable signed heads, Merkle inclusion/consistency,
split-view resistance or required-submission completeness. A broker or global
event stream must not become the chronology/currentness owner, and a universal
event schema would directly violate the Custody Time Model.

### Datomic — external use `C2-U06` → fact `C2-E05`

[Datomic](https://docs.datomic.com/datomic-overview.html) retains immutable
datoms ordered by transaction and exposes transaction-basis `as-of` and
history views. Ordinary retraction preserves historical facts. Its
[excision operation](https://docs.datomic.com/operation/excision.html),
however, deliberately removes matching datoms from history; only evidence of
the excision operation remains.

**PolicyOS inference — CTM §3/PV-K02:** Datomic can supply trusted-store replay,
but not portable proof of a pre-excision member unless a commitment was
retained elsewhere. Transaction `t` is store visibility, not an epoch or
`DesignProblem` authority head.

### Snapshot table formats — external use `C2-U07` → fact `C2-E06`

[Apache Iceberg's specification](https://iceberg.apache.org/spec/) uses
immutable file snapshots and `current-snapshot-id`; branches have independent
lineage heads. Its snapshot log may differ from parent lineage because current
state can be reset, and
[snapshot expiration](https://iceberg.apache.org/docs/latest/maintenance/)
removes time-travel material. Delta Lake likewise offers
[versioned time travel](https://docs.delta.io/delta-batch/) while
[retention/VACUUM](https://docs.delta.io/delta-utility/) and missing historical
files bound how far replay remains possible.

**PolicyOS inference — CTM §4/§6/PV-K02:** these formats are useful query
projections over a pinned census. They do not
natively provide signed portable inclusion/consistency proofs, immutable
family declarations or permanent historical custody. Their storage,
compaction, manifest and retention costs are appropriate for analytical state,
not substitutes for the smaller proof bundle.

### Import decision — PolicyOS inference

Keep family-native append records and optional materialized projections. Share
only canonical commitment, inclusion/consistency and replay protocol. Never
make an expiring snapshot table, retractable projection or generic event store
the sole custody record.

## 4. Certificate lifecycle and revocation

### What the field gives — external use `C2-U08` → facts `C2-E07`–`C2-E09`

[RFC 5280](https://www.rfc-editor.org/rfc/rfc5280.html) certificate revocation
lists are issuer-signed status snapshots with issue/freshness coordinates,
revoked entries, reason and effective invalidity information. CRL numbers and
delta CRLs express succession and incremental status. Revocation need not be
permanent: `certificateHold` and `removeFromCRL` make reason and lifecycle
state material.

[RFC 6960](https://www.rfc-editor.org/rfc/rfc6960.html) OCSP responses are
signed `good`, `revoked` or `unknown` assertions with `producedAt`,
`thisUpdate` and optional `nextUpdate`. `good` is deliberately narrow; it does
not prove every other validity predicate. `unknown` is not positive status,
and an expired response does not establish current status. Network-dependent
revocation often soft-fails; [RFC 9325 §7.5](https://www.rfc-editor.org/rfc/rfc9325.html#section-7.5)
records that weakness, while [RFC 7633](https://www.rfc-editor.org/rfc/rfc7633.html)
directs a client that negotiated the feature to reject missing or invalid
stapled status, but permits other validation and describes an insecure fallback.

[RFC 9608](https://www.rfc-editor.org/rfc/rfc9608.html) permits a no-revocation-
available signal, mainly where short lifetimes bound exposure, but explicitly
accepts weaker compromise response.

**PolicyOS inference — custody signature rule/PV-K02:** short-lived credentials
can reduce a freshness window but cannot satisfy the continuing-honesty
obligation of a long-lived public PolicyOS signature.

### Import decision and mismatch — PolicyOS inference

Borrow the separation between issued object, effective invalidity, recorded
status, freshness window and current query. Keep every authentic certificate
and admitted status transition. An issuance-coordinate query may verify old
authenticity; a current-authority query requires a fresh canonical owner
status. Non-receipt, `unknown` or stale status becomes `not_established` or
`revalidation_required`, never inherited green.

CRL/OCSP mechanisms do not discover exact PolicyOS dependents or decide which
semantic perturbations matter. Decision Validity remains the status owner;
Claim Ledger remains the public-claim history owner; the derivation recipe and
owner-adjudicated impact set drive the cascade.

## 5. Provenance, invalidation and recomputation

### Representation versus operation — external use `C2-U09` → fact `C2-E10`

The W3C [PROV-O Recommendation](https://www.w3.org/TR/prov-o/) represents
entities, activities, agents, derivations, revisions, generation, usage and
invalidation. The
[PROV constraints](https://www.w3.org/TR/prov-constraints/) and
[formal semantics](https://www.w3.org/TR/prov-sem/) constrain ordering and
consistency. A `prov:Plan` can name a recipe.

The external model does not execute a plan or claim to determine PolicyOS
materiality, authority or recursive revalidation.

**PolicyOS inference — S0-K05/PV-K02:** PROV is a useful interchange vocabulary
for exact derivation lineage. Its availability-oriented invalidation predicate
cannot be collapsed with PolicyOS normative invalidity, which must retain the
entity for historical verification.

**External use `C2-U10` → fact `C2-E11`:**
[OpenLineage's object model](https://openlineage.io/docs/spec/object-model/)
similarly represents jobs, runs, inputs, outputs and partial accumulated
events. It does not claim that every production execution was observed.

**PolicyOS inference — S0-K05/GY-GAP5:** an OpenLineage observation cannot
establish source authority or complete production membership.

### Executable-lineage analogue — external use `C2-U11` → fact `C2-E12`

Build systems show what “the derivation certificate is the recipe” requires.
[Bazel's dependency model](https://bazel.build/concepts/dependencies)
requires actual dependencies to be covered by declared dependencies, and
[Skyframe](https://bazel.build/reference/skyframe) rebuilds the reverse
transitive closure of changed recorded inputs. Skyframe explicitly warns that
unregistered reads can produce incorrect incremental builds. Bazel's
[remote-cache model](https://bazel.build/remote/caching) says actions declare
inputs, output names, command line and environment variables; its action cache
maps action hashes to result metadata, while a separate content-addressable
store holds output files. It also records that tools outside the workspace can
be untracked and produce wrong shared cache hits under the same action hash.

**PolicyOS inference — P37/P38/GY-DEF22:** a revalidation recipe is safe for
reuse only if its actual input/tool/code/environment dependencies are covered
by the recorded closure. An influential omitted dependency is the PolicyOS
analogue of an incorrect incremental/cache hit; this is not a claim made by
Bazel about PolicyOS authority.

**External use `C2-U12` → fact `C2-E13`:** Dagster's
[declarative automation](https://docs.dagster.io/guides/automate/declarative-automation)
and [partition backfills](https://docs.dagster.io/guides/build/partitions-and-backfills/backfilling-data)
can recompute affected downstream partitions.

**PolicyOS inference — S0-K05/Decision Validity:** “latest materialized” does
not establish `current_valid`, admissible or publishable.

### Import decision — PolicyOS inference

Bind a content-complete recipe and exact input certificate set. Compute an
affected reverse lineage closure, then let each canonical owner adjudicate the
reaction. Automatically rerun the bound recipe only after that adjudication.
Unknown dependencies or environment profile make revalidation
`not_established`; this links the N12 cascade directly to GY-DEF22's
reconstructible profile identity. Reject filename proximity, event arrival,
declared dependency presence and “latest materialized” as gate predicates.

## 6. Scholarly correction and retraction

### What the field gives — external use `C2-U13` → fact `C2-E14`

The [COPE Retraction Guidelines](https://publicationethics.org/sites/default/files/retraction-guidelines-cope.pdf)
distinguish correction, expression of concern and retraction according to the
state of the evidence and continuing reliability. Retraction corrects the
literature rather than deleting history: the original normally remains
identified, linked and clearly marked. Physical removal is exceptional and
should leave bibliographic metadata and an explanation.

[NISO RP-45-2024](https://www.niso.org/publications/rp-45-2024-crec)
standardizes machine-readable transmission of retractions, removals and
expressions of concern through publishing infrastructure. It is a propagation
protocol, not the adjudicating authority.

[Crossref Crossmark](https://www.crossref.org/documentation/crossmark/participating-in-crossmark/)
links update notices and exposes publisher-supplied types including
correction, clarification, expression of concern, partial retraction,
retraction, withdrawal and removal. Crossref
[discourages silent in-place replacement](https://www.crossref.org/documentation/register-maintain-records/maintaining-your-metadata/registering-updates/)
because it obscures history. A Crossmark status is still supplied by the
publisher.

**PolicyOS inference — P37/S0-K05:** presence of that institutionally supplied
status is not PolicyOS adjudication.

### Import decision and vocabulary mapping — PolicyOS inference

Preserve the external native status and provenance, then map it only through a
verified canonical-owner disposition:

| external signal | pre-adjudication ceiling | possible owner reaction |
| --- | --- | --- |
| annotation/editorial note | annotation or `review_required` | `annotation_only` |
| correction/corrigendum | `review_required` | `annotation_only`, `reissue` or `supersede` |
| expression of concern | `contested`/`review_required` | no premature green or invalidation |
| retraction | `contested`/`review_required` | `invalidate` or `withdraw` current reliance |
| withdrawal | retain native lifecycle meaning | owner-specific `withdraw` or other disposition |
| removal | availability limitation | separately adjudicated epistemic reaction |

Do not copy a publisher's vocabulary as a universal PolicyOS enum: “withdrawal”
and “removal” differ by publisher and lifecycle stage. Preserve the authentic
old member and append linked notice/status. Downstream correction is governed
by exact lineage and PolicyOS authority, not by transport of the external
label.

## Comparative mechanism cost

External sources give qualitative cost shapes, not a PolicyOS implementation
estimate. The “PolicyOS price” column is explicitly inference; exact path and
artifact economics remain the measured pre-replay exercise in the design spec.

| mechanism | external-source cost fact | provisional PolicyOS price inference |
| --- | --- | --- |
| transparency proof (`C2-U14` → `C2-E01`) | operator/monitor retains an entry-growing tree; inclusion/consistency paths grow logarithmically rather than requiring the verifier to retain the whole live log | retain canonical member/proof bundles plus independently held accepted anchors; signing, anchor custody and denominator reconciliation are extra costs absent from a plain hash chain |
| bitemporal history (`C2-U15` → `C2-E03`/`C2-E15`) | [Microsoft retention guidance](https://learn.microsoft.com/en-us/sql/relational-databases/tables/manage-retention-of-historical-data-in-system-versioned-temporal-tables?view=sql-server-ver17) says update/delete-heavy history can grow storage and tax temporal queries; retention recovers cost by deleting old history | reuse Fabric's existing two-time store; add semantic commitments rather than a third temporal table; PV-K02 proof material cannot share a destructive retention policy |
| event sourcing / immutable stores (`C2-U16` → `C2-E04`–`C2-E06`) | append history grows with events/snapshots; replay is bounded by snapshots; excision/expiration/vacuum trade storage for lost historical material | family-native stores may compact projections, but permanent commitment/proof custody remains separately priced |
| certificate status (`C2-U17` → `C2-E07`–`C2-E09`) | CRLs pay batch distribution/storage; OCSP pays responder availability, freshness and caching; short lifetime trades refresh issuance for a bounded exposure window | offline replay favors retained signed status snapshots; current publication still pays owner-side freshness/adjudication and cannot soft-fail green |
| lineage and recompute (`C2-U18` → `C2-E10`–`C2-E13`) | lineage capture stores dependency edges; Skyframe walks/rebuilds the affected reverse transitive closure and notes all-or-nothing dependent invalidation; partitioned backfill can bound work | persist complete recipe/input/profile closure; recompute only the owner-adjudicated affected closure; broad or undeclared dependencies create either replay storms or false reuse |
| scholarly status (`C2-U19` → `C2-E14`) | correction status requires durable notices and metadata propagation through multiple systems | preserve native notice plus owner admission and exact-lineage cascade; transport cost is lower than adjudication/recompute cost and cannot replace it |

No source supplies a repository-specific byte or wall-time estimate. Assigning
one here would be a P36 extrapolation. The implementation phase must measure
member volume, update rate, affected-lineage fan-out, proof-bundle size and the
deployment-artifact intersection before choosing storage or replay thresholds.

## Cross-mechanism seam tests — PolicyOS inferences

| seam | result |
| --- | --- |
| epoch versus bitemporal axes | projection over fixed semantics at explicit coordinates; not a third clock |
| integrity head versus authority head | Merkle head commits a prefix; family/currentness owners derive current authority separately |
| admitted set versus complete set | proof covers admitted leaves; canonical denominator reconciliation establishes completeness |
| historical authenticity versus current reliance | retain member/proof; append status and exclude from current decision front as adjudicated |
| store time travel versus custody | useful projection/replay; retention/excision means it cannot be the sole authenticity record |
| provenance versus recompute | graph/plan describes lineage; complete recipe plus orchestrator and owner adjudication execute it |
| status transport versus authority | signed/editorial signal is evidence; canonical owner resolves, verifies and admits it |
| recorder failure versus run completeness | completed run remains a governed result; chronology claim becomes incomplete/`not_established` until a recoverable receipt reconciles the gap |

## Cycle 2 design constraints carried forward — PolicyOS inferences

- Define two distinct “head” nouns: a **commitment head** proves an append-only
  prefix; a **native authority head** is family-derived current state. The
  former can be shared; the latter cannot be centralized.
- An **accepted anchor** is neither of those heads by self-declaration: it
  freezes accepting owner, proof domain, signature, prior anchor, cutoff,
  witness/consumer-receipt basis and verifier provenance, with at least one
  holder outside the transcript writer's mutation authority. Otherwise whole-
  history authenticity is `not_established`.
- Every family adapter supplies a canonical member encoder, native scope key,
  complete-denominator resolver and head policy. The common verifier cannot
  infer these from timestamps or fields.
- GAP3 and GAP5 need source-denominator reconciliation in addition to Merkle
  proof. GAP5's single production emission boundary must yield either a durable
  receipt or an explicit run-bound custody gap; the independently complete
  source denominator must retain both. A best-effort recorder alone cannot
  support “all production runs.”
- Epoch resolution consumes owner-native valid/effect and visibility
  coordinates and returns a content-bound semantic reference or
  `epoch_scope_unresolved`.
- Validity status and certificate freshness remain under Decision Validity;
  public claim transitions remain under Claim Ledger. Chronology supplies
  proof and admitted perturbation evidence only.
- A derivation recipe is executable only with a complete input/tool/profile
  closure. GY-DEF22 is therefore part of semantic replay, not adjacent
  packaging hygiene.
- Native retention may be bounded for projections, but accepted heads,
  membership/consistency bundles and historical authority records needed by
  PV-K02 cannot be vacuumed, expired or excised.

## Research limitations and Cycle 3 questions — facts and inferences separated

- **External use `C2-U20` → fact `C2-E01`:** transparency systems cannot prove global
  freshness or absence of an unknown external copy to an isolated offline
  verifier. **PolicyOS inference — P37/PV-K07:** the specification must name
  its accepted anchor/witness basis and limit the claim to it.
- **PolicyOS inference — GY-GAP5:** no reviewed external mechanism establishes
  completeness across a production operation that can complete with no durable
  or recoverable receipt. Cycle 3
  must test whether a production-boundary receipt fits the existing run owner
  while preserving GY-GAP5's additive/non-blocking recorder rule. INT-K08 adds
  only that every negative terminal remains a completed member and missing
  custody cannot become green; it does not supply recorder non-blocking behavior.
- **PolicyOS inference — Cycle 2:** the shared proof algebra is plausible;
  whether its policy-bearing adapters amount to one chronology **owner** rather
  than four ledgers behind a library is not
  settled by prior art. That is the Cycle 3 decision.
- **External use `C2-U21` → facts `C2-E04`/`C2-E06`:** reviewed stores support per-
  entity/per-branch histories. **Ratified constraint — CTM §6/INT-K05:** any
  Cycle 3 unification that requires uniform payload or uniform authority head
  is refuted.

## Independent research receipt

The three lanes agreed on the material boundary: shared proof algebra is
plausible; family-native denominators and authority heads remain mandatory.
They independently identified two non-obvious negative cases now carried into
the closure basis: (1) an accepted Merkle prefix can still omit a never-recorded
production run, and (2) a complete-looking derivation recipe can still omit a
tool/environment dependency and manufacture a false reuse/revalidation pass.

Reviewers received the P40 bucket rule in writing before review: classify every
finding as `NEW_CLASS` or `SAME_CLASS_ONE_LEVEL_DEEPER`, against design, record
or research method, and stop ladder-repair on the second same-class finding.

- The negative-basis review returned clean.
- `C2-ARCH-01` (`SAME_CLASS_ONE_LEVEL_DEEPER`, design, blocking) found that an
  anchor merely stored “outside” the transcript was still a declared P37
  predicate. The rewrite now requires a frozen accepting owner/domain/
  signature/prior/cutoff/witness/provenance basis across a writer-independent
  custody boundary, with `not_established` when absent.
- `C2-RECORD-01` (`NEW_CLASS`, record, blocking) found that recorder non-
  interference had been attributed to INT-K08 beyond its warrant. The rewrite
  attributes it to GY-GAP5 and retains INT-K08 only for completed negative
  terminals and no false green from missing custody.
- `C2-METHOD-01` (`SAME_CLASS_ONE_LEVEL_DEEPER`, research method, blocking)
  found external fact presented as architecture authority. The method-wide
  attribution protocol now separates external fact, PolicyOS inference and
  ratified constraint.
- `C2-METHOD-02` (`NEW_CLASS`, research method, blocking) found missing
  bitemporal and lineage/recompute cost. The comparative cost ledger now prices
  every mechanism qualitatively and forbids unsourced repository estimates.
- `C2-METHOD-03` (`NEW_CLASS`, research method, blocking, with three same-class
  instances) found proposition-incomplete sourcing. The repair is one source-
  claim denominator and falsifier, plus corrected SQL:2011, RFC 7633 and live
  Bazel sources; no per-instance exception remains.
- `C2-METHOD-04` (`SAME_CLASS_ONE_LEVEL_DEEPER`, research method, blocking)
  found that the first ledger still summarized topics rather than enumerating
  every external proposition/use. The widened repair expands every proposition
  row, adds the complete 21-block use census and makes an unregistered fact a
  denominator failure. It also records the Bazel action-cache/CAS distinction
  exactly rather than using “content-addressed result” as a proxy.

Return review is clean on all three bounded deltas:

- architecture/record/attribution: `C2-ARCH-01`, `C2-RECORD-01` and
  `C2-METHOD-01` closed;
- economics and warrant receipt: `C2-METHOD-02` closed; and
- proposition/use completeness: `C2-METHOD-03` and the deeper
  `C2-METHOD-04` closed after the reviewer reconciled all 15 proposition rows
  to all 21 use blocks, including the exact Bazel action-cache/CAS distinction.

Cycle 2 is independently delta-clean. The architecture conclusion remains a
provisional input to Cycle 3, not a unification verdict.
