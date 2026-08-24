# GY-N12 Cycle 6 — Final Research and Implementation-Plan Record

## Boundary and toolchain gate

Cycles 1–5 and their qualified unification verdict are accepted inputs. This
pass does not re-derive them. It settles the epoch-only holder contingency,
reconciles GY-DEF22 execution with owner authority, tests GY-GAP2 as a fourth
deferred candidate, registers the Cycle-5 bridge findings and produces the
Clusters 1–4 implementation plan.

The research gate remained closed throughout: local Git, complete tracked-tree
byte/AST walks and direct source inspection only. No bootstrap, `research`
profile, runtime import, generated-artifact execution, replay, writer, network
probe or governed artifact supplied evidence. In particular, no
`torch==2.10.0` result is admitted.

## Merge receipt

The lane began clean and attached at Cycle-5 commit
`787a41e26beaede4efbfa23ac94f14df355341ff`. Before mutation:

- worktree:
  `/Users/deniskopylov/polisyos/.worktrees/gy-n12-epoch-chronology`;
- branch: `codex/gy-n12-epoch-chronology`;
- authorized slice base:
  `1360b1cb592be6a19c162a3ec3ddb5a2e87986c7`;
- exact local `main` tip:
  `0dda8be515c588b326bb5253ca40eb825f0d46f2`; and
- short status: empty.

The guarded non-rebase merge produced
`7445bd48cc58bca24f8531660303176f651f632e` with parents
`787a41e26beaede4efbfa23ac94f14df355341ff` and
`0dda8be515c588b326bb5253ca40eb825f0d46f2`. The immutable slice-base
relation was checked before the merge. All later guards bind the exact merge
commit and parent identities, never the moving `main` ref.

## Registration-identifier census

Two complete, independent tracked-tree readers agreed:

1. `git grep` over the tracked tree; and
2. a `git ls-files -z` 9,922-file byte walk with independent regex extraction.

Both returned exactly `GY-DEF1` through `GY-DEF22` and
`GY-GAP1` through `GY-GAP7`, with no numeric hole. The next free
identifiers are therefore `GY-DEF23` and `GY-GAP8`. A filesystem
walk independently confirmed the same sets. GY-DEF20/21 live outside the
local GY defect block but still consume their identifiers; adjacency in one
document is not the denominator.

## 6a — epoch-only holder feasibility

### Complete repository evidence

Two independent path/content walks agreed on these complete tracked
denominators:

| predicate | matching paths | result |
| --- | ---: | --- |
| `POLISYOS_AUDIT_COLD_TIER_BUCKET` | 3 | configuration doc, audit sink, one test that removes the variable |
| `ObjectLockMode` | 1 | `core/security/audit_sink.py` |
| `ColdTierBackend` | 3 | two Python modules plus generated inventory |
| qualifying tracked S3/IAM/Object-Lock deployment policy | 0 | 57 `ops/cloud` paths and one HCL file inspected |

`ColdTierBackend` buffers generic audit entries and calls
`put_object` with `ObjectLockMode="COMPLIANCE"` and a retain-until expression
of **January 1 of UTC year + 7** (roughly six to seven
years depending on write date)
(`src/polisyos/core/security/audit_sink.py:145-209,408-426`). It discards the
S3 response. There is no persisted object-version/ETag/retention receipt,
holder index, `get_object`, retention query or challenge interface. Its
configuration contains only bucket/prefix/region, and it uses ambient boto3
credentials. `RunContext` enables the generic chain and optional replicas only
when configured and treats replica shutdown as optional fan-out
(`src/polisyos/core/run/context.py:302-321,450-477`).

The repository absence does not prove an external cloud resource is absent.
It proves that deployment, principal separation and credential independence
cannot be admitted from this lane. Their P37 class is
`not_established`.

### Verdict

The user's contingent epoch-only appointment does **not** activate. The
existing mechanism cannot truthfully be appointed.

- Generic audit cold-tier component: implemented and conditionally
  orchestrated; deployment boundary `not_established`,
  remote reader/receipt `consumer_missing`, end-to-end proof
  `verification_missing`.
- Epoch chronology holder: `absent/unallocated`; deployment independence
  `not_established`.

Compliance mode as a request is not a deployed bucket receipt, and remote
location is not writer independence. A writer-retained adjacent copy or
self-attested witness remains inadmissible.

### Minimum qualifying appointment

A later epoch-only appointment needs all of:

1. an institutionally appointed epoch anchor custodian distinct from semantic
   authority;
2. a holder-account Object-Lock-enabled bucket and policy receipts proving the
   epoch writer cannot change policy, retention, versions, credentials or
   receipt log;
3. a competent epoch consumer that independently reconciles scope, purpose,
   query/cutoff, complete denominator and prior lineage before signing;
4. exact signed-package ingestion plus object version and retention receipts;
5. exact-ref holder readback and independent retention/version challenge;
6. fail-closed Decision Validity, Claim Ledger and surface consumption of
   receipt or typed non-receipt; and
7. the writer-compromise rewrite falsifier against the holder's retained
   bytes.

Cluster 3 therefore delivers acceptance and custody-verification machinery
plus the honest no-holder result. It builds no holder writer and makes no
positive whole-history claim.

## 6b — GY-DEF22 execution and owner reconciliation

Atlas Revision 3.22 supplies the reconciliation: ownership assigns
responsibility for correctness, not the moment or lane of execution. GY-N12
executes the repair; Foundry catalog/discovery remains canonical owner, N8
remains producer and N10a remains consumer. Foundry review of the exact
profile/root/distribution discriminant and falsifier packet is owed before
closure. N12 neither mints a second environment identity nor adjudicates
profile membership.

Both GY-DEF14 branches are retained at distinct predicates:

- ambient plugin discovery is already recorded but non-decisive through
  `method_catalog_governed_provenance_projection` and its two-posture test
  (`foundry/methods/catalog/snapshot.py:746`;
  `tests/unit/runtime/quality/test_second_domain_pack.py:605`);
- execution-profile compatibility is decisive and must name a reconstructible
  profile/root/distribution discriminant. `runtime_backend_identity` currently
  records observed packages but not that admitted closure
  (`foundry/methods/catalog/snapshot.py:397`).

The six fixed falsifiers are:

1. documented `research` plus `torch==2.10.0` names the profile/root/
   distribution mismatch, not catalog or downstream drift;
2. an incompatible in-closure distribution under an unchanged shaped profile
   rejects by recomputation;
3. a second data-generated incompatible profile rejects without a known-name
   rule;
4. an out-of-closure package difference passes;
5. a novel admitted profile and the GY-DI1 profile reconstruct from recorded
   data without code/allowlist changes; and
6. absent/unreadable `production_data/manifest.json` emits
   `production_data_manifest_missing` at the input boundary, never a catalog
   identity mismatch, generation hash change or N10a triage drift.

The sixth falsifier is required by the GY-DEF19 correction: in a fixed source
state, adding only the read-only production-data dependency changed
`substrate_catalog_missing` to `world_model_record_unresolved` while the
apparent generation-contract hashes moved. Comparing two environments had
misattributed that difference to source.

Current GY-DEF22 authority-grade identity label:
`producer_missing`, with `artifact_missing`,
`semantic_test_missing` and `surface_missing` deficits. Runtime-cutoff
authority is `absent/unallocated`; production runtime candidate evidence is
`not_requested`. A test/reference `present` candidate is non-decisive and does
not change that gate. The existing
N8 artifact/N10a consumer and tested ambient quarantine remain real.

## 6c — GY-GAP2 candidate-consumer test

GY-GAP2 fits the fixed full-prefix profile without adding a common field.
Its family adapter would supply opaque native members that reference immutable
per-problem confidence roots/receipts, prospective local caps, assumptions and
owner-reconciled current heads. INT-K04 cap enforcement and aggregate
recomputation remain confidence-owner predicates, not chronology.

The head decision is asymmetric:

- the proof protocol supplies a **commitment head** over the declared family
  prefix;
- it does not supply a new family **authority head**; the confidence owner
  reconciles the vector of existing scope-local heads; and
- INT-K05 keeps every `design-problem:<id>` scope non-resettable and distinct.
  The family is a declaration over roots, never a parent scope or second
  ledger.

The current label `contract_missing` and scheduling state
`blocked_on_product_decision` remain correct. INT-K06 means no admitted
consumer needs a family number today.

The fourth deferred candidate strengthens the wide objection but does not
reverse the narrow verdict. Implementing owner arithmetic would not test
protocol genericity. Cluster 2 instead uses one materially non-epoch,
test-only opaque native shape and the **real** full-prefix verifier at 0/1/2
members. It must reject deletion, native-byte substitution, reorder,
cross-domain/profile replay and inconsistent extension, and expose no native
head, acceptance, denominator or authority API. This is not a GAP2 producer.

## 6d — registered Cluster-4 findings

### GY-DEF23 — Decision Validity authority intake

A complete AST walk parsed all 2,561 source Python files with zero failures.
`DecisionDependencyEvent` has three source calls in two files and
`record_dependency_event` has two; the live service copies caller status,
dependency keys, source ref and payload, writes caller dedupe first and applies
the supplied status
(`core/contracts/decision_validity.py:178-195`;
`scientist/validation/decision_validity.py:352-405`).

Label: `producer_missing` for authority-grade epoch transition;
deficits `artifact_missing + verification_missing + semantic_test_missing`.
It is not `bridge_missing`. Closure is exactly
`C5-PREREQ-DV-EPOCH-ADMISSION`, including complete-denominator pending
freeze and crash-safe public reads.

### GY-GAP8 — Claim Ledger lifecycle orchestration

The same complete AST walk finds one definition and zero source calls for both
`bridge_governance_events_to_claim_lifecycle` and
`persist_lifecycle_bridge_result`. Tests call them, and the component maps
the needed append-only lifecycle actions, but its authority boundary explicitly
disclaims detector truth
(`scientist/governance/continuous/lifecycle_bridge.py:191-443`).

Label: `implemented_but_not_orchestrated`, not `bridge_missing`.
Closure is `C5-PREREQ-CLAIM-DV-LIFECYCLE`: a production call consumes the
completed, verified Decision Validity batch, never raw monitor metadata.
Automatic recipe execution remains `absent/unallocated` with each
artifact's canonical producer.

## Delivery and replay decision

The narrow implementation responsibility is the unchanged partition:
`34+40+8+9+10+14+12+1=128`. Clusters 1–4 own respectively the 9
Foundry prerequisite IDs, 34 common/profile IDs, 8 anchor-dependent IDs and 40
epoch/cascade IDs. The remaining 37 IDs stay with GAP3/GAP5/GAP6 and the
programme capstone. These are responsibility sets, not a closure score; N12
must never report `128/128`.

Before any implementation writer, the actual changed source paths must be
intersected with GY-DI1's derived 96-path deployment closure. An empty
intersection means **zero reissue**. A non-empty intersection triggers one
post-freeze declared wave only after source and reviews are frozen. Current
price inputs, not promises, are 5,387 declared artifact leaves, 911 protected preimages,
47,532,401 bytes and 1,220.234 seconds cold. The exact implementation
procedure and commit boundaries are in the companion plan.

## P40 review rule

Every reviewer receives this rule in writing before the packet:

> Classify every finding as `NEW_CLASS` or
> `SAME_CLASS_ONE_LEVEL_DEEPER` and name the subject:
> design, record, research method or implementation plan. On the second finding
> of one class, stop instance repair and require a structural widening or an
> explicit bounded residual with its falsifier. Findings in Cycle 6 consume no
> implementation round.

Review receipts and repairs are appended here; the final clean detached
receipt changes no tracked bytes.

## Implementation-plan derivation and pre-freeze review

The executable plan is
`docs/superpowers/plans/2026-08-20-gy-n12-epoch-chronology-implementation.md`.
It assigns the exact narrow basis as 9 + 34 + 8 + 40 IDs and gives every one of
the 91 IDs an executable witness plus any retained incomplete label. That table
is a responsibility/claim ceiling, never a score. It also fixes source/test/
interface/command/commit boundaries and a candidate -> declaration -> guarded
apply -> readback transaction before any governed writer.

An initial adversarial plan draft was overwritten before root recorded its
serialized packet hash; its exact packet identity is therefore
`not_established` and no clean receipt is claimed for it. Its blocking findings
are retained because they caused structural changes:

- `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan`: the toolchain and
  terminal commands were not executable as written. The plan now admits the
  exact N8 dependency surface without `research`, asserts torch absence, uses
  one source-first zsh array, gives N8/N10a/epoch candidate modes and adds a
  guarded transition tool before any writer.
- `SAME_CLASS_ONE_LEVEL_DEEPER / design`: common persistence and prefix
  validation risked a new store and acceptance-head conflation. The plan now
  adapts the existing `ArtifactStore`, verifies only a domain-bound commitment
  prefix and keeps family acceptance outside the common verifier.
- `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan`: Cluster 4 lacked native
  complete-denominator registries/APIs, a non-bypassable Decision Validity
  route, completed-batch Claim Ledger persistence/export and the actual N9
  OpenWorldRisk consumer. These were widened as owner-level seams, not patched
  tests.
- `SAME_CLASS_ONE_LEVEL_DEEPER / record`: recipe execution, competent
  deployment evidence, holder/acceptance and whole-history rows were mapped as
  closable. The 91-row table now retains `absent/unallocated`,
  `producer_missing` or `not_established` at each exact positive chain while
  allowing only its fail-closed negative branch to close.

The first journal evidence review targeted the then-current raw journal at
12,163 bytes, SHA-256
`5254ecab720154b4fe7fdeac9052a97bee8d6711f0d067cd28f2fd065c26fe61`.
It returned one
`SAME_CLASS_ONE_LEVEL_DEEPER / record / cosmetic` finding: source computes the
retention request as January 1 of UTC year + 7, not a seven-calendar-year
duration. This record now quotes the expression and its roughly six-to-seven-
year consequence without promoting it into a stronger deployment fact. The
no-holder verdict is unchanged.

### Implementation-plan Wave 1 — non-clean and structurally widened

The first fully serialized plan was split into four sequential raw-line
packets; all four reviewers independently reproduced their assigned packet:

| packet | exact bytes | SHA-256 | result |
| --- | ---: | --- | --- |
| P1 | 26,013 | `2a4caf2908e22c99749e2a4e55f0cbabcd1e8aa596431af6cac92c9d499200ff` | non-clean: four blocking buckets |
| P2 | 21,473 | `ecb1165d3df99c743194f78c7e262ea85c6822d02b4f88a7b10701261c1a9f58` | non-clean: five blocking buckets |
| P3 | 22,316 | `1a9af8b66852fd5c1b055a7587329ed63beb795ef0f36ea4bbc9192ef4298c48` | non-clean: four blocking buckets |
| P4 | 7,507 | `43f1f7526f9b570b87a9d60721ab4e10d8b018d4939ad2a7a8872c3912c10613` | non-clean: four blocking buckets |

The classifications and class-level repairs are append-only:

1. `NEW_CLASS / implementation plan / blocking`: the admission guard expected
   an empty `--show-prefix` from inside `policy-engine`; live Git returns
   `policy-engine/`. The exact guard now requires that value.
2. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: CAS raw-byte
   identity was equated with the domain-separated chronology digest. The plan
   now carries and recomputes both distinct identities and never compares them
   for equality.
3. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: eight wire/
   result types and the public-facade classification were left implicit. Every
   type is now strict and exact; the Foundry/core surface classifications are
   fixed, not conditional.
4. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: a sampled
   nine-call migration and split commits would leave required builders/callers
   broken. The complete measured denominator is twelve call expressions for
   the Cluster-1 migration, and each required-signature migration is one atomic
   commit with a fresh AST set comparison.
5. `NEW_CLASS / implementation plan / blocking`: Cluster 3 had ports but no
   trusted signature/holder-receipt verification seam. It now defines canonical
   unsigned acceptance bytes, detached sidecars and appointment-bound
   acceptance/holder verifiers while production appointments remain absent.
6. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: Cluster 4
   had a pure reducer but no authority producer, persistence or executable Lex
   scope relation. `SemanticEpochService`, its native append/head repository
   and the exact `amended_doc_id -> lex_facts.doc_id` complete relation now own
   collection, persistence and common-proof invocation.
7. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: N13b lacked
   explicit v1-to-v2 table/profile migration and complete callers. Tasks 4.1
   and 4.2 are now one atomic producer/signature/schema boundary over all six
   passport-builder and eighteen overlay-admission call expressions, including
   the two omitted positive suites.
8. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`:
   OpenWorldRisk stopped at a gate field. Its vector identities, query and
   verifier provenance now round-trip through canonical N9 input, owner
   projection, receipt, offline replay and decision-front verification.
9. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: Decision
   Validity pending freeze could be bypassed by RunIndex's stable-directory
   cache. The owner generation/overlay and crash-restart `/runs` falsifier are
   now mandatory.
10. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: Claim
    Ledger repeatedly forked from a packet's original ledger and narrowed
    dependency membership to six ref families. A native current-head store,
    atomic compare-and-advance, complete data-owned dependency-field registry
    and mandatory current-head export read replace both proxies.
11. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: the
    guarded writer omitted source-freeze-to-declaration drift and durable
    armed/fallback custody. Apply now requires zero intervening source/tool/
    target drift, fsyncs preimages and an armed receipt before replacement, and
    recovers an interrupted batch before any new apply.
12. `NEW_CLASS / implementation plan / blocking`: the 91-row table paired IDs
    with convenient but unrelated tests. The entire table was regenerated from
    the frozen property text; an independent static check returns 91 unique
    rows partitioned `9+34+8+40`, with no missing or extra narrow ID.
13. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: changed
    Ruff paths were worktree-root coordinates applied from product root. The
    command now derives `--relative=policy-engine`, rejects a doubled prefix and
    filters deleted files.
14. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: validator
    loops trusted some exits and ignored some semantic payloads. One common
    wrapper now checks the exact expected process status and parses the common
    semantic envelope for every N8/N10a/epoch mode.
15. `NEW_CLASS / implementation plan / blocking`: commit commands contained a
    placeholder and did not stage/read back exact bytes. Every boundary now has
    an exact path array and one guarded stage/cached-diff/commit/branch-content
    readback function; the terminal array is derived only from the declaration.
16. `NEW_CLASS / implementation plan / blocking`: suite timing was prose. A
    dedicated runner now measures without timeout with uptime pairs, binds
    over-60-second suites to reviewed lane-owned ceilings and treats signal/
    timeout as a non-receipt.

No implementation round was consumed: all findings are against the plan and
no production mechanism exists.

Before the next external freeze, root's static audit found that the first
N13b sketch circularly required an admitted passport to derive the epoch that
the passport itself had to bind, that the transition artifact had no canonical
producer/call site, that the Claim bridge exposed a DV-complete/Claim-head gap,
and that validator commands were outside the measured-timeout protocol. Those
were widened respectively into the prepare -> hidden pending -> finalize ->
activate handshake, a signed transition producer invoked before N9, a durable
`claim_bridge_pending` strangle, and one timing wrapper for every heavy
process. Two draft return-review targets were deliberately interrupted after
root changed their bytes; they produced no completed review receipt and no
clean claim.

### Implementation-plan Wave 2A — non-clean and structurally widened

The next frozen plan was split into six raw-line packets. Wave 2A reviewed the
first three sequential packets under the advance P40 rule; all three reviewers
reproduced the exact assigned bytes:

| packet | raw lines | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | 1–602 | 25,474 | `e267fdd23a797d23df7aa6d4248a9ff0636bd7b8f3fdbca141a0193ee9e15587` | non-clean: four blocking buckets |
| P2 | 603–1248 | 25,443 | `457cfed17d0a9e32e161898f75632193abbbefba471347bdbeae06da831a8560` | non-clean: four blocking buckets |
| P3 | 1249–1770 | 25,498 | `8695e5b015bad3ed8bb26be5c79f35dbf4a3c0905c2c3ea5f2130e11651b2d8b` | non-clean: four blocking buckets |

All twelve findings are classed before repair and widen their owning
interfaces rather than adding case patches:

1. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: Cluster
   1 accepted a caller-minted positive manifest DTO and left the two decisive
   digests as ungrammared strings. The pure reducer now accepts raw bytes or a
   typed read failure, the authority entrypoint reads fixed paths beneath the
   source-frozen root, and both domain-separated preimage grammars are exact.
2. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: local
   package facades were called public although the canonical contract admits
   only `polisyos.foundry`/`polisyos.core`. The plan now re-exports through
   those admitted roots and atomically updates inventory, reference and the
   exact public-API release fragment.
3. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: P37
   dispositions were a flat bag. They are now keyed to exact member or query
   subjects under an explicit admission policy; missing/cross-subject or
   non-authority classes fail closed.
4. `SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`: common proof
   `limited` had no proof-only semantics and could rejoin commitment and
   authority heads. Proof status is now only `verified/rejected`; native and
   custody limitations stay in their actual owners.
5. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: Cluster
   3 still accepted caller-supplied authorities, appointments and verifier
   results. A container-owned epoch custody service now resolves scoped
   appointments internally, and the appointed authority reloads and recomputes
   proof plus native admission before signing.
6. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: the
   holder retained refs rather than decisive bytes, generic `ArtifactStore`
   could not supply exact manifest/signature evidence, raw and semantic signing
   identities were conflated, and lineage had no canonical record ref. One
   narrow signed-evidence repository and a complete embedded retention object
   graph close the class; holder readback verifies without writer storage.
7. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: data-only
   free-grow still required one provider per registration/facet string. The
   plan now has three finite native owner-kind adapters and one generic facet
   provider; new domain rows reuse those adapters without code.
8. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: live L5
   regimes had no owner-adjudicated scope relation. L5 now owns a content-bound
   regime-scope data relation and complete receipt; absent/ambiguous scope is
   unresolved and N12 projection data cannot override it.
9. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: N13b's
   activation flag did not cover any of the six union-table member sets. One
   complete native member-to-epoch relation plus generated primary-key joins
   now strangles all six views and fails on a novel unregistered table.
10. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: the
    transition producer named a generic store/signer combination that cannot
    persist or read exact signature evidence. It now uses the same narrow
    signed-evidence repository and a container-owned transition signing
    authority; generic stores cannot issue a receipt.
11. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`:
    OpenWorldRisk replay had refs but no artifact resolver outside the live N9
    port. The resolver is now injected through live, standalone/offline and
    decision-front paths, with a fresh-process deletion/mutation falsifier.
12. `SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`: DV triggered only when
    the native head changed during one HTTP call. The gate now lives in the
    core generation controller and, before every N9 decision, compares the
    packet epoch/current head and both complete denominators against the last
    completed binding. Old packets and same-epoch new adjudications cannot
    receive a no-transition pass.

Wave 2B packets were not reviewed because Wave 2A changed the plan's byte and
line denominator. No finding consumed an implementation round; no mechanism
exists.

### Implementation-plan Wave 3A — non-clean and structurally widened

The rewritten plan was frozen again and Wave 3A reviewed its first three raw
packets. All targets reproduced before and after review:

| packet | raw lines | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | 1–581 | 25,485 | `4a94bad557ec1a148074a8e2504e72a1aa7cbcc4d8469abb6d6a6fd1727af9ac` | non-clean: four blocking, one cosmetic |
| P2 | 582–1211 | 25,470 | `8d6f9ccc21b30fad09b83b5ffecd97240fbe5abcb325af9715ed813e39cacd0d` | non-clean: five blocking |
| P3 | 1212–1765 | 25,471 | `7e7e39132d81a02aa24a4cc18bfdaabdcec5eee6f97e31a417777008639e3a1e` | non-clean: two blocking |

The P40 classifications and widened repairs are:

1. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: the
   permitted external read-only production-data root was rejected as a source
   escape. Tracked source and appointed data are now separate bound roots;
   exact root/custody/source-freeze evidence admits the authorized external
   case and rejects writable, moved, sibling/unappointed or changed targets.
2. `SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`: caller-selected profile
   labels plus caller-shaped installed distributions could relabel a research
   environment, while the shell torch check was a proxy. Foundry now owns a
   purpose-to-profile relation and one fresh-environment sync/receipt producer;
   N8 supplies only purpose and independently reads the bound environment.
   Out-of-closure packages remain non-decisive only under a genuinely admitted
   receipt.
3. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: missing
   and unreadable manifests had contradictory public codes. Both now emit the
   frozen `production_data_manifest_missing`; a separate internal source-state
   field retains diagnosis.
4. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: public
   digest fields and manifest options admitted invalid forms. The ABI now uses
   one SHA-256 semantic type and discriminated present/unavailable plus
   distribution/profile mismatch unions.
5. `NEW_CLASS / implementation plan / cosmetic`: the new public-API release
   fragment was listed under Modify. Cluster 1 now lists it under Add; later
   clusters modify the same exact file.
6. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: acceptance
   and holder appointments were all-or-nothing. They now resolve independently,
   and the result union preserves acceptance-only, holder-only and neither.
7. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: signed
   evidence, acceptance, custody and readback wrappers retained self-reference
   or unnamed bytes. Every chain now has a canonical unsigned statement/record
   without its ref, then exact signed evidence, then a persisted wrapper/ref.
8. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: the
   non-injectable production service existed only in prose. One no-argument
   runtime-quality composition root installs the no-appointment provider,
   `RuntimeServiceContainer` consumes it, and a constructor AST strangle
   forbids other source calls/injectable service parameters.
9. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: custody
   DTOs admitted `verified` with no evidence and mislabeled recomputed failures.
   A discriminated verified/limited/rejected union freezes required halves,
   non-empty limitations/rejections and exact code-to-provenance classes.
10. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: rollback
    depended on a caller prior ref, not an owner index. A concrete append-only
    lineage repository now owns per-scope/domain/purpose records, explicit
    current multi-heads and compare-and-append; an authentic old record remains
    historical but cannot satisfy a later query.
11. `SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`: the new L5 resolver
    left global-latest and hard-coded Ukraine sibling consumers authority-
    bearing. Generation substrate and data-state/L4 now consume the same scoped
    projection; initial Ukraine declarations move to L5-owned data and a third
    regime/new-domain agreement is the structural falsifier.
12. `SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`: the six-view relation
    covered inserted rows but not reused registration rows and raw joins would
    duplicate two-active reuse. Each admission now binds its complete referenced
    member closure and read visibility uses `EXISTS`/semi-join, with pending-
    creator/active-reuser and two-active-reuser falsifiers.

Wave 3B was not issued because these changes moved every later line/byte
denominator. The result remains research/plan correction only.

### Implementation-plan Wave 4A — non-clean and structurally widened

The fourth frozen plan was split into seven raw-line packets. Wave 4A reviewed
the first three; all exact targets reproduced before and after review:

| packet | raw lines | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | 1–544 | 25,468 | `ff776d883b71db11a4783a6e47bca3992952b8bd02c831d132d1b3e7a8c69fa7` | non-clean: five blocking buckets |
| P2 | 545–1207 | 25,475 | `250257c9fa1104088ae20c1ff144899cb4713d3b6f548e057c98c0b13d5fbc49` | clean: zero blocking, zero cosmetic |
| P3 | 1208–1758 | 25,464 | `c1acad92463221dfef6149aad1ef46e8bae4a79f29b99244af767ccd853e221a` | non-clean: three blocking buckets |

The eight classified repairs widen their owning contracts:

1. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: the
   sanitized runner could not find or bind uv/cache inputs. Bootstrap and the
   Foundry producer now require an absolute content/version-bound uv binary and
   an explicit offline-cache root/custody receipt; no `PATH` or default-cache
   search is admissible.
2. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: the N8
   child inherited the tooling `PYTHONPATH`. Tooling and N8 now have disjoint
   `env -i` runners; the latter contains only the receipted environment's site
   and proves every decisive distribution origin.
3. `SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`: instance nonce/receipt
   bytes contaminated the reproducible closure discriminant. The stable
   semantic identity now excludes install-instance fields; two identical
   independent installs share it while retaining distinct receipts.
4. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: data and
   environment receipt refs had no non-circular byte grammar or target marker.
   Exact unsigned statements, raw/domain hashes, 0/1 vectors and an
   environment-retained marker/readback now bind every ref without self-
   reference and reject a receipt copied to another target.
5. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: the one
   admitted receipt was issued before its source existed/froze. Cluster tests
   use candidate fixtures only; the sole admitted environment is built after
   all reviewed source commits and before terminal N8/N10a validation.
6. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: holder
   readback still resolved signature refs through writer CAS. Custody/readback
   now return exact statement, package and signed-evidence bytes; a fresh
   verifier with deleted writer storage uses holder bytes only.
7. `NEW_CLASS / implementation plan / blocking`: native owner APIs erased
   knowledge/admission axes behind hashes. L5, Lex and N13b now receive
   distinct owner-readable sparse coordinate evidence, recompute every ref and
   bind the requested context; retroactive before/after-knowledge queries are
   the falsifier.
8. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: Lex/N13b
   receipts were undefined and L5 omitted its regime-source identity. All
   three strict receipts now bind exact owner snapshots, query coordinates,
   complete ordered assessments, counts/hashes and typed failures; a
   self-consistent narrowed subset fails independent reconciliation.

Packets 4–7 were not issued because these repairs moved their denominators.
No finding consumed an implementation round; the target is still a plan and
no mechanism exists.

### Implementation-plan Wave 5A — non-clean and structurally widened

The fifth frozen plan was split into raw-line packets and the first three were
reviewed sequentially under the advance P40 rule. All three exact targets
reproduced before and after review:

| packet | raw lines | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | 1–532 | 25,465 | `a65f2ca311dfc8ed9b24829e637647e5ba91f50265576692eb3f27aba99e9198` | non-clean: four blocking buckets |
| P2 | 533–1130 | 25,494 | `8cc59338218ba534159ac9c26c6033658285811ffa7cef46447f9e23c003e924` | non-clean: three blocking buckets |
| P3 | 1131–1728 | 25,483 | `d9b969baaac404a38afa988d60250c310e83b8dcff00a757540581f39cad70b8` | non-clean: four blocking buckets |

The eleven findings were bucketed before repair:

1. `SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`: installed identity
   compared only distribution metadata, so a required file could change while
   name/version/direct-URL and marker remained fixed. The Foundry producer and
   N8 reconciler now independently enumerate and hash every required installed
   file plus its lock/source binding; the metadata-preserving file mutation is
   the structural falsifier.
2. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: production-
   data custody evidence sat outside the hashed appointment statement. The
   statement now binds exact root/manifest, custodian, custody evidence,
   Foundry authority registry and appointment-verifier provenance before its
   ref/hash is computed.
3. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: an invented
   offline-cache receipt had no producer or verifier. Cache location/content
   is now explicitly non-decisive transport availability; no cache receipt is
   accepted or serialized, while lock/source and installed-file reconciliation
   carry the product predicate.
4. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: profile,
   reconciliation and failure DTOs admitted contradictory positive/negative
   combinations. Discriminated pass/fail unions, non-empty mismatch evidence
   and one cross-object model validator now make those forms invalid.
5. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: both public
   catalog builders accepted a caller-constructible positive profile wrapper.
   They now accept only an authority request and invoke the single no-argument
   Foundry composition root; positive admission DTOs and pure reducers remain
   package-internal.
6. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: raw
   appointment bytes plus a self-shaped custody ref could appoint any read-only
   root. A Foundry-owned issuer/trust registry, signed appointment evidence and
   canonical verifier resolve only exact refs; production defaults to
   `production_data_appointment_not_established`.
7. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: expected uv
   identity was caller-supplied. The owner registry now binds platform-qualified
   Python/uv source and executable identities; the receipt producer accepts
   paths only and rejects substituted bytes against unchanged owner data.
8. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: custody and
   readback statements still had no persisted receipt-record identity. Each now
   has an unsigned record, exact signed evidence and a final persisted wrapper;
   the challenge binds the exact custody-record ref/hash.
9. `NEW_CLASS / implementation plan / blocking`: a standalone readback challenge
   lacked family/domain/purpose/lineage coordinates and could not resolve its
   appointed holder. A persisted challenge statement now carries the full
   appointment key and the service exposes only its content-bound ref.
10. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: verified
    custody results copied labels without receipt/challenge/appointment/
    verifier evidence and allowed contradictory halves. Exact bound refs,
    non-empty evidence and cross-branch validators replace those forms.
11. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking`: a signed
    acceptance candidate could lose compare-and-append yet masquerade as an
    accepted record. Candidate authenticity, owner lineage append and final
    acceptance are now three records; only a final receipt binding a persisted
    append success is accepted, while a concurrent loser remains authentic but
    non-accepted.

Packets after P3 were not issued because the widened contracts changed every
later denominator. No finding consumed an implementation round; no production
mechanism, governed artifact, writer or replay exists.

### Implementation-plan Wave 6A — non-clean and structurally widened

Wave 6A reviewed the first three packets of the next exact freeze. Every
reviewer reproduced the assigned bytes before and after review and made no
edit or prohibited execution:

| packet | raw lines | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | 1–500 | 22,580 | `e278c2d3762fdf7aff9c25839d1a0b09676ee09d12cfc0f0cf4622911555e7fb` | non-clean: three blocking |
| P2 | 501–1000 | 25,466 | `eddf738c6955a1ed42a5c1074c23ee341c333f931c347d160d49094fe07293fb` | non-clean: two blocking, one cosmetic |
| P3 | 1001–1500 | 18,990 | `49598af8817aed5520a0f219394f20becbcf9d0f31584a2c93d826a29f12dded` | non-clean: one blocking |

The seven classified findings fold into five structural classes:

1. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking` (P1 and
   P2): Foundry trust remained authority-by-reference and caller-selected
   source roots could carry self-consistent fake registries. The production
   composition root now derives its source/Git identity from the imported
   module, admits no source-root request, verifies exact appointment/custody/
   trust/provenance bytes and persists one fixed environment authority capsule
   that a fresh N8 process reopens.
2. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking` (P1 and
   P2): installed files had no independently retained source-artifact/build
   lineage. Exact selected wheel/source/build evidence and bytes are now kept
   in the capsule; expected manifests derive from those bytes, while N8
   independently enumerates the actual tree. Rewriting payload and RECORD
   together cannot preserve the relation.
3. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking` (P1): one
   nested mismatch DTO multiplexed incompatible field states. Each mismatch
   code now has its own strict variant, required evidence and inequality
   validator; missing has no observed fields.
4. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan / blocking` (P3): the
   adapter supplied the same predicate-policy denominator it was judged
   against. The native owner now persists a policy profile; the consumer
   resolves it independently and requires a three-way bijection across the
   complete applicable denominator, policy rules and dispositions.
5. `NEW_CLASS / implementation plan / cosmetic` (P2): public-surface
   regeneration named no canonical writer. Task 1.3 now runs exact source-first
   `architecture guardrails sync --skip-deep-import-baseline` followed by
   `check`; generated rows are not hand-edited.

Later packets were not issued after the first blocking result because the
rewrite changed their raw-line denominator. These are still findings against a
plan, not an implementation round.

### Implementation-plan Wave 7A — non-clean and widened at the class level

Wave 7A reviewed the next frozen first three packets. Each reviewer reproduced
the exact target before and after review, made no edit and kept the research
toolchain gate closed:

| packet | raw lines | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | 1–500 | 22,685 | `2411f8e95cdca00356aa6a62b6a3e2784edac605142a644757621608e63948e3` | non-clean: four blocking |
| P2 | 501–1000 | 24,786 | `2c8dc03fbc7405ea2023414d3f44645a40d4336ddf1eeb01baaaa838e4c9cb06` | non-clean: six blocking |
| P3 | 1001–1500 | 22,537 | `1077f879ff5b795afeebe945386f42c8208e904e8f1fa4e9fcf5167a9a881f5e` | non-clean: one blocking |

All eleven findings are `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan /
blocking`; P40 therefore requires two structural widenings, not eleven local
repairs:

1. **Complete authority-predicate receipt/trust plane.** A fresh root challenge
   was not receipt-bound; trust rows named keys without exact public-key/
   revocation resolution; dirty decisive source bytes could hide beneath an
   unchanged HEAD; the capsule repeated CAS/signature semantics; missing
   artifact/root predicates had no typed result; and C2 let the adapter select
   a valid but lax native profile. C1 now has one strict/frozen DTO base, one
   canonical `ArtifactStore`/`FileSystemCAS` signed-evidence adapter, complete
   owner trust material, a signed nonce-bearing attestation and per-resolution
   receipt, clean Git-tree source authority, and a predicate registry with
   rejected plus not-established branches. C2 now resolves a unique owner
   policy/profile relation from family/domain/scope/purpose/cutoff before it
   reads the adapter candidate; zero-member and two-profile attacks fail.
2. **Complete typed lineage/digest/transform plane.** Raw launchers made stable
   install identity path-dependent; build lineage and several decisive digests
   had no strict preimage/verifier; Python identity stopped at the launcher;
   source mismatch compared an artifact digest with a relation digest; and
   unknown fields could be dropped by non-strict DTOs. The plan now separates
   stable semantic rows from raw instance rows, normalizes only verified
   generated entry points, binds the complete Python runtime, uses a typed
   source→build→wheel record, tags hashes by semantic domain, and validates an
   exhaustive digest registry generically. Expected/observed mismatches must
   share a domain, and an unregistered decisive field is a contract mutation.

Later packets were not issued because this rewrite moved their line and
semantic denominators. The target remains research documentation: no production
mechanism, governed artifact, writer, replay or implementation round exists.

### Implementation-plan Wave 8A — non-clean; open wrappers replaced

The three exact delta packets reproduced before and after review; reviewers
made no edit and kept the gate closed:

| packet | target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 249–730 | 23,367 | `fd2e2aaeec99a731a75091f815a3234532e9b60e94d3fd9743e5c1095988fe5d` | non-clean: four blocking |
| P2 | plan lines 744–1117 | 24,678 | `065687ab3fd3007d942fff48e0444261c8b2f1ff0519b953a9556ea94cf19d52` | non-clean: six blocking |
| P3 | plan lines 1260–1500 then 1637–1713 | 13,193 | `e8adff13527260b5e3f67c6729570a9d74a4a67db723b0227369896e453872cf` | non-clean: two blocking |

Eleven findings are `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan /
blocking`; the signed-evidence import gap is `NEW_CLASS / implementation plan /
blocking`. The repair replaces their classes:

1. **Closed record/result algebra.** Live mutable `ArtifactRef`, arbitrary
   domain/predicate/code strings, `Any`, contradictory status/code pairs and
   bare negative returns are removed. Authority records carry immutable wire
   artifact IDs plus closed semantic domains; predicate/scalar domains and
   codes are enums checked against the owner registry. Admitted, rejected and
   not-established attempts each persist a discriminated receipt. C2 likewise
   has fixed policy-failure leaves, non-self-referential denominator
   statement/wrapper bytes and complete post-resolution result leaves.
2. **Exact evidence and trust.** The signed-evidence record preserves exact
   blob, original manifest and detached signature, then invokes the existing
   verifier with owner-resolved trust. Trust binds computed key IDs, signer
   identity/role and content-bound revocations; build verification has an
   admitted route. The same owner-created opaque mount capability feeds both
   manifest read and root attestation, defeating genuine-root-A/copy-B.
3. **Complete transform/codec denominator.** Every persisted digest row now has
   one strict statement codec, including stable/instance/source binding,
   wheel/source/build and expected/observed Python runtime. The registry is the
   sole executable hash algebra; coverage is by semantic annotation, not field
   suffix. Stable N8 root installation is explicitly non-editable, and sibling
   checkout paths are a falsifier rather than normalized payload.

This remains specification work. No finding consumed an implementation round
and no mechanism, governed artifact, writer or replay exists.

### Implementation-plan Wave 9A — non-clean; authority evidence graph widened

Three exact Cluster-1 ABI packets reproduced before and after review. Reviewers
made no edits and used only dependency-free tracked-tree inspection:

| packet | target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 249–550 | 13,766 | `5f594b5cd05cc0cfb9bb5d7ef4ed68e497fa512e73410ae798d1265ac29df19a` | non-clean: two blocking |
| P2 | plan lines 551–850 | 14,858 | `d2685abdb7af0be3f01d8a3955077e1864abc99f20bf57b9baa8879b038175bc` | non-clean: six blocking |
| P3 | plan lines 851–1169 | 15,276 | `acf151edad45e28d441cc0e4e56c6c7e604f6357a09a930626f4068f0f06be57` | non-clean: one blocking |

Seven findings are `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan /
blocking`; owner-derived runtime observation and the sealed trust snapshot are
two `NEW_CLASS / implementation plan / blocking` findings. They are repaired
as three structural quantities:

1. **One canonical identity/digest grammar.** Record refs now carry the exact
   live `ArtifactID` `sha256:` wire form and a covariant closed domain. Tracked
   TOML stores NUL-terminated prefix bytes as lowercase hex and selects only
   closed preimage/order/handler/phase and launcher-transform IDs. A separate
   root nonce domain prevents statement-hash substitution. Unknown algebra,
   bare IDs and incompatible signature-role rows fail before execution.
2. **Owner-native observation results.** A container-owned Python observer
   resolves the child executable, complete symlink chain, actual runtime root,
   expected-domain runtime manifest and selected-artifact source binding before
   it can seal a positive result. Production-data mount resolution likewise has
   explicit admitted/rejected/not-established outcomes and gives manifest read
   plus attestation the same owner-opened handle. Copied expected rows, an
   unbound runtime redirect, and a present-wrong/writable mount fail without a
   caller status field.
3. **One sealed trust and signed-record graph.** The trust policy is an unsigned
   non-self-referential statement; its receipt binds source cutoff, policy,
   role, exact eligible keys, revocations and verifier provenance. The resolver
   privately seals the sole verifier and rejects absent signer identity. Every
   signed semantic record has a separate binding to its exact blob/manifest/
   signature evidence and trust basis. The capsule holds a complete binding
   index; fresh root access holds its post-capsule binding in the resolution
   receipt. Fresh-process verification rejects missing, swapped, orphan,
   cyclic, wrong-role or self-trusting edges without a reverse scan.

No finding consumed an implementation round. The target is still a plan; no
production mechanism, governed artifact, writer, runtime execution or replay
exists.

### Implementation-plan Wave 10A — signed graph clean; two owner planes widened

The three exact delta packets reproduced before and after review; all reviewers
made no edits and held the research gate closed:

| packet | target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 255–553 | 13,628 | `cd03083da5853b88de41e057cce508bff6ac47bbfb8ed695ad29c4b7f235866a` | non-clean: four blocking |
| P2 | plan lines 705–902 | 10,392 | `fcd3da695906d508535bf605d828299fa032cd18b112227c02c33805e7214a70` | non-clean: three blocking |
| P3 | plan lines 904–1160 then 1325–1385 | 15,866 | `7afe6d70e8bd4a64f88b95c4cbbb7b22cc5a22fd3ebfad27a038c51aba800454` | **clean: zero blocking, zero cosmetic** |

All seven findings are `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan /
blocking`; P40 therefore widens the two repeated quantities:

1. **Independent executable identity algebra.** Digest rows now select separate
   closed producer and verifier implementations, and the verifier must reject a
   deliberately corrupted producer. Prefix bytes equal the domain-derived
   Foundry namespace exactly, not merely a syntactic prefix. POSIX launcher
   normalization has one admitted profile with separate expected-wrapper
   producer and full observed-byte parser/verifier; Windows remains unclaimed.
   Covariance has a checked basedpyright fixture whose invariant mutation must
   fail, rather than a runtime marker test.
2. **Owner-issued roots and non-circular authority construction.** Python sync
   now issues an installation receipt binding the selected artifact to the
   owner-opened runtime root; N8 resolves that receipt, contained paths and the
   actual child chain before it can seal an observation. Trust bootstraps in two
   phases: tracked raw Ed25519 root keys verify source-basis material/revocation
   bindings through a transport-only reader, then Git ancestry establishes the
   cutoff and constructs the sole role resolver/repository. A separate owner
   appointment authority follows the appointment's custody ref and reconciles
   root/custodian/manifest/purpose/policy, so two authentic pairs cannot be
   cross-spliced.

The already-clean mount/nonce/signed-binding graph packet did not change for a
local repair; later ranges moved only because the widened ABI is longer. No
finding consumed an implementation round, and no mechanism or writer exists.

### Implementation-plan Wave 11A — non-clean; three owner algebras widened

The three exact Cluster-1 packets reproduced before and after read-only review.
Reviewers received the P40 bucket rule before review, made no edits and held the
research toolchain gate closed:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 257–610 | 15,905 | `59e1aecc33df86bac1338ed803138c79cc05750d488e93e137f0159ac1dd0c1f` | non-clean: two blocking |
| P2 | plan lines 700–990 | 15,145 | `d852b686f8a0ef3fef5de10eb3459bc646dbc1f9eb3fe4a10f67d89a9b238ee1` | non-clean: four blocking |
| P3 | plan lines 990–1255 concatenated with 1530–1624 | 16,709 | `90ca7f6c4beed40978f16b034772eeae7f87a6b58e5f90fd909586e625cf9363` | non-clean: one blocking |

All seven findings are `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan /
blocking`. They fold into three already-widened quantities rather than seven
case patches:

1. **Closed digest and path algebra.** A digest row still allowed individually
   valid but mutually incompatible preimage/order/producer/verifier values, and
   stable/instance file rows escaped the rooted-path type; the shared validator
   also admitted `.` and NUL. The ABI now uses a discriminated closed digest-
   algebra variant and one empty/dot/absolute/dotdot/noncanonical/NUL-rejecting
   path type across every decisive relative-path field. Generic annotation
   coverage catches a newly added raw path field.
2. **Owner-sealed runtime and appointment facts.** The runtime observer could
   not obtain the installation receipt without reverse lookup, while the mount
   resolver could not compare a requested root with the already-verified
   appointed root. Sync now passes the owner-sealed installation result
   directly; fresh N8 resolves the marker's receipt into that same capability.
   A verified appointment retains its exact verified appointment/custody
   statements, so authentic root-A evidence rejects requested root B before a
   mount capability is created.
3. **Cutoff-bound canonical trust snapshot.** The resolver still accepted a
   caller-selected source/cutoff, and tuple-shaped keys, roles, materials,
   revocations, eligible keys and dispositions could collapse differently in
   the live dictionary/set verifier. The bootstrap snapshot now binds source ref
   plus freeze commit; `resolve()` accepts no source. Every trust denominator is
   unique and canonically sorted before constructing the verifier, with a new
   bootstrap required for another cutoff.

This wave remains plan research. It produced no implementation mechanism,
governed artifact, writer, runtime execution or replay.

### Implementation-plan Wave 12A — non-clean; transport and capability boundaries widened

The three exact Wave-11 repair packets reproduced before and after review;
reviewers made no edits and used only dependency-free tracked-tree inspection:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 250–710 | 20,846 | `4f05d2c24bb3e9d2f9c2768eb2e00e329098f952ac48636208dde895ed67e64d` | non-clean: two blocking |
| P2 | plan lines 800–1185 | 19,161 | `22989ce120e4fdfda05bb573fb4cac1e0e96936914b3605216ded99b1d0411e6` | non-clean: two blocking |
| P3 | plan lines 1780–1990 concatenated with 2215–2300 | 20,548 | `fc4a7318e87e8bcac99785198c8c3e78c0c2de8c791f4237a8dc68c9465144af` | non-clean: one blocking |

Four findings are `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan /
blocking`; the absent strict TOML decoder is `NEW_CLASS / implementation plan /
blocking`. The two reviewers' path findings are one class and receive one
structural repair:

1. **Semantic scalar roles, not path-name matching.** Every non-literal scalar
   in an authority DTO now has an explicit semantic wrapper/metadata role. A
   generic schema walk rejects every bare primitive irrespective of field name;
   a synonym-named path mutation is the falsifier. The digest TOML has a
   transport-only strict wire model and total exact string-to-enum decoder;
   semantic round-trip bytes/hash must reproduce.
2. **One constructible owner-capability kernel.** All positive in-process
   capabilities use one private identity mint and one generic consumer guard.
   Empty construction, `object.__new__`, copied fields, wrong-family values and
   sibling consumers fail. Capabilities have no codec; fresh processes
   re-resolve persisted evidence through the owner.
3. **Frozen bounded runtime-root identity.** V1 names only Darwin APFS and Linux
   ext4. Its root token binds environment nonce, length-framed encoded path
   hashes, filesystem type and opened-handle device/inode/mode/ctime observations
   before/after enumeration and on path reopen. Producer and verifier remeasure
   independently. Other or unstable filesystems are explicitly
   `python_runtime_not_established`, not covered by a portable-copy claim.

These remain specification repairs and consume no implementation round.

### Implementation-plan Wave 13A — non-clean; state removed from capabilities

All three exact packets reproduced before and after review, with no edits or
toolchain/runtime activity:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 257–470, 650–850, 1994–2047, 2560–2570 concatenated | 22,071 | `4a469b13687ec86963e4b1a135cc1eb872c35ed685d87f1a3db3b8f444e9e242` | non-clean: one blocking |
| P2 | plan lines 500–580, 1090–1170, 1240–1550, 1880–1930, 2025–2045, 2545–2555 concatenated | 27,520 | `eff1062259b8f55b880e804c29f1dcf62ec02a07c4cd83a5493bf86bfe63727b` | non-clean: three blocking |
| P3 | plan lines 1020–1170, 2190–2265, 2545–2565 concatenated | 15,361 | `90de04fcb3771eb28a843805b7ca1dc5fe95c89f5f05b382817ae19767a12fb9` | non-clean: one blocking |

Four findings are `SAME_CLASS_ONE_LEVEL_DEEPER / implementation plan /
blocking`; embedding a live capability in a persisted admitted DTO is
`NEW_CLASS / implementation plan / blocking`. Repairs again widen the quantity:

1. `_exact_enum` now inspects `StrEnum.__members__`, including alias names, and
   accepts a wire value only when exactly one symbolic member owns it. The
   falsifier constructs a synthetic alias, not merely an unknown value.
2. Owner capabilities are now fieldless tokens. Their typed payloads and live
   handles exist only in a PID/per-process-bound registry; fork clears it.
   Unwrap recursively validates nested tokens and is the only payload access.
   Registered owner entrypoints map every token failure into their typed result.
   A transitive schema guard forbids tokens beneath all persisted/wire/Pydantic
   DTOs; admitted results carry root-access refs only.
3. POSIX runtime identity now performs two complete ordered subtree walks with
   per-file pre/post observations and equal manifest refs, catching the named
   nested-file mutation. Writer-independent write-and-restore between both walks
   is explicitly bounded: immutable subtree snapshot/writer exclusion is
   `absent/unallocated`, so the receipt proves the completed quiescent cutoff,
   never continuous custody.

No implementation round or governed output exists.

### Implementation-plan Wave 14A — non-clean; capability and runtime-cutoff claims widened

Three exact packets reproduced before and after independent read-only review.
Reviewers made no edits and the research toolchain gate remained closed:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan ranges 780–855, 1360–1700, 1960–1990, 2160–2225 and 2745–2760 | 26,259 | `be71455a0dc7f3ceaa41c62266d1ad20c46b3315eaa673a88823021837aedd6f` | non-clean: one blocking |
| P2 | plan ranges 510–640, 1170–1280, 1790–1830, 2030–2115, 2180–2225 and 2728–2752 | 22,651 | `4815c8ea3415f9a49648928f659cb6ca858f1fde2325f3060d0126213943bcc6` | non-clean: three blocking |
| P3 | plan ranges 1030–1220, 2375–2445 and 2735–2755 | 16,862 | `db1c46cef275cd75c05ea384f361296f47f6c10eebe998f4d4ca97edb6371139` | non-clean: one blocking |

All five findings are
`SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking`. They fold into
two repeated P40 quantities and therefore receive structural rather than
per-instance repairs:

1. **Owner capabilities are a closed typed relation, not frozen-shaped
   objects.** The previous weak registry erased payload types, admitted
   structural `Protocol` lookalikes, exposed its payload map, queried a
   `WeakKeyDictionary` before exact-type rejection and let one decorator define
   both guard and denominator. The replacement uses fieldless tokens plus eleven
   typed `_OwnerPayloadSpec[C, P]` constants, exact private concrete leaves,
   dynamic signed-record domain reconciliation and a payload registry held only
   inside a process-bound closure. A source AST/type-hint census independently
   derives every token consumer and unwrap call, then class-wraps that complete
   protocol/concrete denominator with an interface-specific typed failure
   adapter. No per-method decorator can shrink the set. Before clearing tokens
   after fork, per-spec disposers close every unique inherited source/runtime/
   institutional-root descriptor; handles also reject the wrong PID.
2. **Two complete walks are observations, not a common cutoff.** A file already
   checked in pass two can change while later files are read, leaving both
   manifests equal but the subtree different at completion. The specification
   now retracts the completion-cutoff claim. Positive runtime identity requires
   an owner-enforced immutable snapshot or mandatory writer-exclusion lease
   bound to the exact observation. That capability is
   `absent/unallocated`; the only production v1 resolver returns
   `python_runtime_not_established`, no admitted environment receipt is
   issued, and GY-DEF22 remains `producer_missing`. The already-checked-file
   pass-two mutation is the frozen falsifier. Candidate reconstruction and
   negative tests remain deliverable.

These are plan/specification corrections. They consume no implementation round
and create no mechanism, governed artifact, writer, runtime evidence or replay.

### Implementation-plan Wave 15A — non-clean; the owner kernel and cutoff state made executable

The three exact Wave-14 repair packets reproduced before and after independent
read-only review. Reviewers made no edits and the research toolchain gate
remained closed:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | frozen plan packet 1 | 22,143 | `b13eed2bed40f06b47620e14e86cf993f0bd2fe61abc6087f84855a66551bdc2` | non-clean: four blocking, zero cosmetic |
| P2 | frozen plan packet 2 | 24,390 | `f91a92ef60615631101d7588de91fd96436019b27dcb7ba8b4d5796758769567` | non-clean: five blocking, zero cosmetic |
| P3 | frozen specification/record packet | 16,680 | `bdd9976c73acd70052a169bdcc6f4f492372c94b7037b1b3987f774dde8fda67` | **clean: zero blocking, zero cosmetic** |

P1 returned one `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan /
blocking` denominator finding plus three `NEW_CLASS / design / blocking`
findings: method-only/early guard installation, an under-specified generic
fault adapter, missing dynamic domains for nested signed records, and mint
remaining open after child-disposal poison. The duplicate-kind/rogue-spec
escape folds into the repeated denominator class. P2 returned one
`SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking` finding (cutoff admission),
three `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking` findings
(production composition/preflight, the late-mutation oracle and resource
disposal), and one `NEW_CLASS / record / blocking` finding (inexact Cluster-1
current-state rows). The structural repair is:

1. **One closed owner-capability lifecycle.** Separate token-to-spec and
   kind-to-spec maps form an identity-checked bijection. The kernel owns
   recursive nested-token validation, including each signed record's dynamic
   domain; child-disposal poison blocks both unwrap and mint. Resource tokens
   have idempotent explicit release and finalizers, and fork invokes the same
   close path. The independent denominator distinguishes class methods from
   module functions, is derived and installed only after every target exists,
   and rejects a missing or extra guarded target. Every guard receives bound
   arguments plus a frozen per-capability fault policy and persists the exact
   typed negative receipt required by that target. Private construction
   helpers consume private payloads, not caller-visible positive tokens.
2. **No dormant positive runtime-cutoff contract.** The unappointed snapshot or
   writer-exclusion authority has no positive v1 DTO. The sole production
   implementation exposes only a preflight returning
   `not_established`; the source-derived production-composition graph rejects
   a request-injected, protocol-typed or positive substitute. The deterministic
   mutation witness barriers a write after one early file's second-pass
   post-hash `fstat`, proves both candidate manifests still compare equal, and
   proves that only the absent cutoff authority prevents promotion. Thus the
   negative is about the missing decisive predicate, not about a proxy test.
3. **One exact Cluster-1 state source.** Every Cluster-1 basis row now points to
   `C1-CURRENT`: overall `producer_missing`; runtime cutoff
   `absent/unallocated`; artifact, semantic-test and surface deficits retained;
   Foundry adjudication plus authorized production-data appointment/root/
   manifest still owed. Candidate or negative witnesses never promote that
   state, and CB-I06 explicitly has no candidate wave, governed transaction or
   replay.

These are specification and plan repairs only. They consume no implementation
round and create no mechanism, governed artifact, writer, runtime evidence or
replay.

### Implementation-plan Wave 16A — non-clean; spec trust, resource ownership and refusal receipts widened

Three exact packets reproduced before and after independent read-only review;
reviewers made no edits and used no runtime or generated tooling:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 535–975 | 18,158 | `fa8c4da3a583a594daf287655f788eb647c5279ce0ec0bc18e47d68330ea337d` | non-clean: two blocking, zero cosmetic |
| P2 | plan ranges 1450–1515, 2425–2488, 2725–2770 and 2860–3135 | 27,981 | `34b7cb30c2134c946d9181dcc267539eedc5f0ea9f5d38a6ecb2b3bb12a9e1f9` | non-clean: one blocking, zero cosmetic |
| record | journal lines 1040–1093 | 3,623 | `84aa1c69e70605733fab5fcb02a9936672d0efcbcacce3c1d15f16980f5f84da` | non-clean: one blocking, zero cosmetic |

P1 returned `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking`
for registered-spec validation occurring after weak-map access, plus
`NEW_CLASS / design / blocking` for non-exclusive resource ownership and an
ambiguous repeated-release contract. P2 returned
`SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking`: the pure
cutoff preflight could not itself produce the persisted public non-receipt the
narrative promised. The record reviewer returned `NEW_CLASS / record /
blocking`: Wave-15 P2 subjects and the zero-cosmetic outcomes were omitted.
Repairs widen the relevant quantities:

1. **Registered spec trust is a first precondition.** Kernel construction
   validates the exact enum kind, fieldless-token class marker, payload class,
   leaf/path/domain/cardinality schema and token↔kind identity. A single
   resolver runs before value-type or weak-map access in mint, unwrap and
   release. Raw-string kinds, undecorated/list token classes and rogue spec
   objects therefore yield a typed family fault rather than Python container
   behavior.
2. **Resource ownership is exclusive and release is explicitly idempotent.**
   The kernel maintains a private per-resource lease. A second token cannot be
   minted over a handle already owned by a live token; the first token's GC can
   therefore never close another live authority's resource. Finalizer, fork and
   explicit release share the lease-aware close path. Weak tombstones make a
   repeated explicit release a no-op while never-minted values still reject.
3. **The outer owner persists refusal.** Cutoff `preflight()` stays pure and
   negative-only. `_ProductionMethodCatalogDependencyAuthority.resolve()`
   binds request plus source, invokes it and persists exactly one source-stage
   non-receipt through the concrete sink constructed by the no-argument
   Foundry composition root. The returned public result carries that receipt;
   reload proves no sync, capsule, marker or candidate output occurred.
4. **The record retains exact review tuples.** Wave-15 subjects and cosmetic
   counts are now explicit rather than inferred from the repair prose.

No finding consumed an implementation round. There is still no mechanism,
governed artifact, writer, runtime evidence or replay.

### Implementation-plan Wave 17A — non-clean; semantic spec, open generation and store custody widened

The exact packets reproduced before and after read-only review; no reviewer
edited files or ran runtime/generated tooling:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 540–1105 | 24,275 | `396713961ab91d1470ee3c888cdf52900efe01f7788743e7fb24e1d6cf70d6b7` | non-clean: two blocking, zero cosmetic |
| P2 | plan ranges 1595–1655, 2485–2530, 2565–2650, 2865–2938, 3060–3100, 3260–3330 and 3550–3610 | 24,131 | `89bdd6f62615207bf986b61eafac63ec49103ced94a662805c02171f94c999f1` | non-clean: two blocking, zero cosmetic |
| record | journal lines 1040–1140 | 6,866 | `47d4d892475e54fe03c0fd22441826c2226f831f96f94ba16ad930257d1f99b3` | **clean: zero blocking, zero cosmetic** |

P1 returned two repeated-class findings: token/spec construction was
`SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking` because a copied
class marker and syntactic path still stood in for token behavior and resolved
annotations; descriptor ABA was `SAME_CLASS_ONE_LEVEL_DEEPER / design /
blocking` because `(pid, fd)` could revive after close and numeric-FD reuse. P2
returned two `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking`
findings: the receipt sink had no owner-derived concrete store identity and the
owner Protocol/concrete pair tuple was its own denominator. The repair widens
all four quantities:

1. **Semantic spec construction.** A probe verifies each token is actually an
   empty, slotted, frozen, weak-referenceable, identity-equality dataclass with
   no writable instance state. A total type-hint resolver checks every leaf,
   dynamic domain, nested token and SINGLE/MANY path against the real payload
   graph during kernel construction. Copying a marker or naming a
   missing/wrong-typed attribute cannot survive.
2. **Owner-issued open generations.** One process-bound descriptor registry is
   the only handle constructor. It binds generation plus original fstat
   identity, translates OS errors to typed non-receipts and permanently marks a
   closed generation rather than deleting it. Reuse of the same numeric FD for
   another directory cannot revive a stale wrapper or token lease.
3. **One request-bound receipt store.** The outer owner derives an explicit
   filesystem-CAS child from the canonical environment request, persists a
   content-bound store-identity record, and accepts no CWD/environment/config/
   store input. The later evidence repository delegates receipt write and read
   to that same sink; it has no sibling persistence path. A fresh process loads
   by store identity and exact receipt ref.
4. **Source-derived owner-pair denominator.** A complete AST class graph, not a
   tuple, discovers every `_OwnerBoundaryBase` concrete and its exact owner
   Protocol before method/guard derivation. Adding a boundary enlarges the set;
   losing its Protocol/marker or disagreeing with live namespace objects fails.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 18A — non-clean; token storage closed and receipt-store residual bounded

The three exact Wave-17 repair packets reproduced before and after independent
read-only review. Reviewers made no edits and the research toolchain gate
remained closed:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 540–1130 | 25,245 | `929cc39e638bdf7b4bb2858a3d73d33c50d8cbf79a4aaf9235141cc2c628e679` | non-clean: two blocking, zero cosmetic |
| P2 | frozen plan packet 2 | 25,344 | `b9c0bb0a897486c9b52d679b61ba03bbc9e0c1e99f4e1ae0ae4c63e0ad61e0f6` | non-clean: two blocking, zero cosmetic |
| record | journal lines 1040–1186 | 6,300 | `1fa8affee91008ecf78a5fccc65c97541360458a6c9341a510b3bfb96df05534` | **clean: zero blocking, zero cosmetic** |

P1 returned two repeated-class findings. Token fieldlessness was
`SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`: a decorated subclass with
an inherited writable slot survived a check limited to the concrete class.
Spec lookup was `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan /
blocking`: a hostile unhashable token class reached the weak-map key operation
before registered-spec identity was established. P2 returned two
`SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking` findings. The
proposed local receipt store was neither constructible through the declared
owner graph nor institutionally independent, and its path reused the runtime
root's digest role. The source-derived owner-pair denominator otherwise
survived. The record packet returned clean.

P40 stops the repeated receipt-custody ladder here. The repair is structural
and deliberately smaller than another invented store:

1. **Object-only token ancestry and safe spec lookup.** Owner tokens must have
   exactly `object` as their base; inherited storage is rejected at kernel
   construction. Registered-spec resolution begins from the exact enum-kind
   map, requires candidate-spec identity and only then touches the trusted
   registered token type. Inherited-slot and unhashable-metaclass mutations
   therefore return typed faults before registration/map access.
2. **Receipt persistence is a declared bounded residual.** The current
   runtime-cutoff owner returns one strict `RuntimeCutoffPreflightRefusal`
   binding request, canonical source evidence and the negative predicate. It
   says `persistence=not_established` and names the missing
   `owner_resolved_resolution_receipt_store`, whose capability state is
   `absent/unallocated`; it writes nothing. A local
   filesystem CAS, adjacent copy, caller store, environment-selected signing
   policy or path digest cannot become institutional custody. The smallest
   closing capability is an appointed owner-opened, request-bound, no-follow,
   explicitly signed audit store with independent readback. Live source has no
   such component, so Cluster 1 retains `artifact_missing` and GY-DEF22 remains
   `producer_missing` rather than acquiring a speculative writer.
3. **The unused store-role ambiguity disappears with the mechanism.** There is
   no resolution-store path field or digest domain in the executable v1 plan.
   CWD, CAS/signing environment and fake store-shaped inputs are tested only to
   prove they cannot create or redirect an artifact before the typed refusal.

No finding consumed an implementation round. There is still no mechanism,
governed artifact, writer, runtime evidence or replay.

### Implementation-plan Wave 19A — non-clean; negative-only ABI and owner-resource lifecycle widened

All three exact Wave-18 repair packets reproduced before and after independent
read-only review. Reviewers made no edits and did not cross the research
toolchain gate:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 540–1135 | 25,578 | `3a13d3f11fbf1907ac9a127c699d2c29b6a72cbc5fd0322a78cc289593c70be6` | non-clean: three blocking, zero cosmetic |
| P2 | concatenated plan ranges 2345–2560, 2655–2690, 3055–3225 and 3275–3325 | 27,825 | `a67c8b80af855e178ad7e9afd014147a5e59d533642bbf90a55768316c459af0` | non-clean: two blocking, zero cosmetic |
| P3 | concatenated plan/spec/journal status packet | 17,265 | `6fc827a0ca6cdcd93cd478a03e401b328f86689b0ce06b8fd80dbb70d1164f0b` | non-clean: one blocking, zero cosmetic |

P1 confirmed the Wave-18 object-only ancestry and kind-first spec-lookup
repairs, then returned two `SAME_CLASS_ONE_LEVEL_DEEPER /
implementation_plan / blocking` lifecycle findings and one `NEW_CLASS / design
/ blocking` provenance finding: open-before-mint descriptors escaped the token
fork sweep; lease absent-check/install was not atomic across threads; and a
cleared inherited token became `UNMINTED_TOKEN/rejected` rather than
`FORKED_PROCESS/not_established`. P2 returned two
`SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking` findings: the
negative-only result was not total when canonical source resolution itself
failed, and one stale paragraph still described persisted post-cutoff outcomes
whose ABI had been removed. P3 returned one
`SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking` label finding: the missing
receipt-store capability itself lacked an exact capability state.

The structural repair is:

1. **One synchronized owner-resource lifecycle from open onward.** A private
   coordinator owns each descriptor immediately at open, installs its
   finalizer, atomically claims a complete resource set, rolls back failed mint,
   and serializes open/claim/release with all three fork callbacks. The child
   closes every generation, including unclaimed open-before-mint resources,
   before its registered token participant detaches finalizers and clears
   payloads. Two-thread same-generation mint admits exactly one lease.
2. **Fork provenance without payload retention.** The child retains only weak
   token→spec fork tombstones. A genuine inherited token is therefore
   `FORKED_PROCESS/not_established`; an independently forged fieldless object
   remains `UNMINTED_TOKEN/rejected`. Disposal failure still poisons all later
   mint and unwrap.
3. **A total negative-only source→cutoff ABI.** The no-argument factory holds a
   production source resolver, never a source snapshot. Each call freshly
   returns one of source-rejected, source-not-established or—only after source
   success—runtime-cutoff-not-established. The derived call graph forbids
   repository, component, sync, candidate and artifact edges before that
   result. A generic ABI validator requires exactly those variants and rejects
   any resolution-outcome writer, codec, domain or positive alternative;
   existing capsule/environment evidence remains a separate read-only input.
4. **Every missing capability binds its own state.** The strict cutoff refusal
   binds `owner_resolved_resolution_receipt_store` to
   `absent/unallocated`. Its refusal persistence remains `not_established`, its
   artifact remains `artifact_missing`, and GY-DEF22 remains
   `producer_missing`; those subjects are not conflated.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 20A — non-clean; active borrows and the complete negative ABI denominator

All three exact Wave-19 repair packets reproduced before and after independent
read-only review. Reviewers made no edits and did not cross the research
toolchain gate:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 540–1135 | 26,368 | `f6880b18f7978d907c6349779a56da8b6bee6239b0798bf7003486c1824030b6` | non-clean: three blocking, zero cosmetic |
| P2 | frozen plan packet 2 | 23,797 | `72dcdcc3553b475a97c64f09ba1097e8589b5df3f7d5b01537557132e01d0c67` | non-clean: three blocking, zero cosmetic |
| P3 | frozen status/record packet | 11,641 | `55c054933298e5128aaad8e6146d8b49528344ee3e4f836d45ccab72746746fc` | **clean: zero blocking, zero cosmetic** |

P1 returned one `NEW_CLASS / implementation_plan / blocking` finding and two
`SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking` findings. The
slotted concrete child handles could not support the immediate weak finalizer
the plan required; mint traversed and claimed attacker-shaped payload resources
before exact validation; and release closed resources before atomically making
the token non-live, so a concurrent unwrap could obtain a closed payload. P2
returned three `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking`
findings. Negative results did not bind exact predicate, code, evidence shape,
source-ref rule and persistence rule as one stage; the production negative graph
still required an unreachable runtime-installation owner edge; and the
no-writer validator covered only one repository while stale prose still implied
a persisted outcome. P3 independently reproduced the four current capability
states and returned clean: the owner-resolved receipt store is
`absent/unallocated`; refusal persistence is `not_established`; the receipt
artifact is `artifact_missing`; and GY-DEF22 remains `producer_missing`.

The structural repair is:

1. **One context-managed resource lifetime.** Every concrete child-disposable
   handle is weak-referenceable and is registered with the synchronized
   coordinator at open. Mint first performs a side-effect-free exact payload and
   child-type validation, then claims inside one rollback scope. Unwrap lends a
   context-managed borrow; release is one synchronized transition that refuses
   an active borrow and closes, removes and tombstones atomically. Bare unwrap,
   drop-before-mint, fake-child, failed-claim and release/unwrap barrier
   falsifiers exercise the property rather than its markers.
2. **A closed negative-stage algebra.** One frozen stage table binds result kind,
   exact predicate, code, evidence shape, source-reference rule and persistence
   rule for source rejection, source non-establishment and runtime-cutoff
   non-establishment. Strict result variants validate against that table, so a
   field-shaped cross-stage result is not constructible.
3. **The complete negative-only production graph and no-writer denominator.** A
   fresh production source resolver feeds the negative cutoff owner directly;
   no runtime-installation authority is required or reachable. The validator
   derives every authority result model, codec, digest domain, owner Protocol and
   concrete, artifact store and filesystem-writing effect in the module and its
   production call graph. A sibling writer, codec, domain or positive result
   enlarges the set and turns the generic contract mutation red. Existing
   persisted capsule, environment, trust, signed-evidence and build-lineage
   inputs remain explicitly read-only and cannot be mistaken for a new outcome
   writer.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 21A — non-clean; two-phase mint and cross-file negative strangle

The two technical targets and the status target reproduced before and after
independent read-only review. Reviewers made no edits and did not cross the
research toolchain gate:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1A | plan lines 540–1000 | 19,655 | `e54c0dbdd8201a973a8e0f27cd9bdf1dbcb469f7d8f0e932e8ea6a7635e2c0f0` | non-clean: two blocking across P1A/P1B, zero cosmetic |
| P1B | plan lines 1001–1185, 1710–1818 and 3928–3955 concatenated | 15,934 | `68014078698e7c5f1b808bc2047804a97ed8e373d10edb24d4f55b512a37fd19` | same P1 outcome |
| P2A | plan lines 2570–2870 | 13,882 | `34a10036f2040c888f6e5970cfaa655b3b6a68f99158c53f7fcbc38e13f020cc` | non-clean: two blocking across P2A/P2B, zero cosmetic |
| P2B | plan lines 2871–3220 and 3958–3975 concatenated | 18,699 | `969fa452f83654db8e5caf0c00e56470db3d2f16da015d3c084bb2762a39767e` | same P2 outcome |
| record | design lines 650–740, plan lines 7058–7094 and journal lines 1298–EOF concatenated | 13,227 | `87c74c74ed6ae3a26a7eb5cdccf0e87577d40fd2c5c97920d81b80ce744a16cf` | **clean: zero blocking, zero cosmetic** |

P1 returned two `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan /
blocking` findings. Mint still read a dynamic-domain path before the exact type
gate and ran complete semantic validation before provisional resource custody,
so a bad sibling could leave a genuine handle open. The direct owner-target
fork scan also missed helper/callback process creation and payload escape while
the same-thread `RLock` was reentrant. P2 returned two
`SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking` findings. The
stage algebra treated missing runtime evidence as a proxy for the actually
absent immutable-snapshot/writer-exclusion owner, admitted anonymous source
digests and did not bind every negative result to the same persistence gap.
Its production strangle also ended at the authority module while both public
catalog builders and their callers retained legacy ambient-positive edges.
The record target reproduced Wave 20 chronology and all four incomplete labels
and returned clean.

The structural repair is:

1. **Compiled two-phase mint.** Phase A performs only exact payload type,
   declared child extraction and exact concrete child types; no dynamic path or
   child method is touched. Phase B first claims the complete resource set,
   then performs all recursive/domain/nested validation and token registration
   inside one rollback scope. Wrong signed-record lookalikes have zero property
   access; a genuine handle beside a corrupt semantic leaf is synchronously
   closed on failure.
2. **Transitive borrow reachability.** An independent AST graph begins at every
   lexical owner borrow and resolves every helper/method/import alias
   transitively. Unknown/dynamic/callback calls fail closed; direct, aliased or
   helper process creation and every return/store/capture of the borrowed
   payload fail before execution. The direct-target keyword scan is no longer
   the predicate.
3. **Orthogonal negative dispositions.** Each result row separately binds the
   gate failure, role-bound evidence shape and persistence failure. Runtime
   refusal names `owner_enforced_runtime_subtree_cutoff:
   absent/unallocated` whether candidate evidence is present or not requested;
   source rejection requires one unequal expected/observed digest pair; and all
   three results name `owner_resolved_resolution_receipt_store:
   absent/unallocated` as the persistence reason.
4. **Public-consumer strangle.** The complete source call graph includes both
   public catalog builders and every caller. Current v1 signatures return only
   the three negative authority variants before any legacy
   `platform`/`safe_version`, ambient dictionary or pure-candidate edge. A
   future positive requires a separately reviewed ABI.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 22A — non-clean; implicit dispatch and canonical predicate evidence widened

All four sequential technical packets and the record packet reproduced before
and after independent read-only review. No reviewer edited files or crossed the
research toolchain gate:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1A | plan lines 540–1050 | 21,927 | `094091c11897f23f374d5741f706fd0e8de36ae6e8758e047d239039e1c26b30` | non-clean: one blocking across P1A/P1B, zero cosmetic |
| P1B | plan lines 1051–1210, 1740–1850, 2890–3025 and 4060–4085 concatenated | 22,006 | `a732fdddcb1597d7223c8640081486733afe5fd30e1f7cb806a4bbc18860fa91` | same P1 outcome |
| P2A | plan lines 2600–2865 | 12,250 | `23428bb50334ba9242cf166dc5a70dd2531b34227a12bc9818b45eb4b6b540d0` | non-clean: one blocking across P2A/P2B, zero cosmetic |
| P2B | plan lines 3220–3305, 3905–4015, 4090–4120 and 4160–4190 concatenated | 15,501 | `6c53df76f780aa5d2edb22e15a744d4956dad7b63a26b7830d601e902a9978a6` | same P2 outcome |
| record | design lines 650–740, plan lines 7195–7232 and journal lines 1355–EOF concatenated | 13,553 | `fe51c69cb74107c77ad0a15e55e9d0ed09d8e861a5637c037af4b67cddbeeb07` | non-clean: one blocking, zero cosmetic |

P1 returned `SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`: the transitive
graph stopped at builtin names such as `len`/`tuple`, but those operations can
dispatch through a borrowed object's `__len__`/`__iter__` to a process-spawning
helper. P2 returned `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan /
blocking`: the split dispositions still registered cutoff-owner absence as the
`PYTHON_RUNTIME` evidence predicate, and unrelated unequal source hashes were
not bound to the request and owner-observed Git relation. The cross-file
negative strangle, common persistence gap and compiled mint returned clean.
The record reviewer returned `SAME_CLASS_ONE_LEVEL_DEEPER / design / blocking`:
`C1-CURRENT` did not freeze production candidate evidence to `not_requested`.

The structural repair is:

1. **Complete terminal-edge algebra.** Every operation reachable during an
   owner borrow records its AST invocation form, exact operand types, implicit
   data-model methods and either traversed callees or a proven
   `no_user_dispatch` disposition. Descriptors, iteration, context,
   comparison/truth/hash/index, formatting and operators join explicit calls.
   Unknown operations fail. Custom `__len__`, `__iter__` and descriptor
   callbacks are falsifiers; `len` over an exact builtin tuple is the control.
2. **One canonical predicate/evidence algebra.** Predicate rows now carry
   discriminated rejected/not-established evidence requirements. The negative
   stage map references a predicate and derives its code/evidence grammar from
   that registry. Runtime refusal uses the one-sided
   `owner_enforced_runtime_subtree_cutoff` predicate. Source rejection binds the
   request's expected commit/tree to a fresh owner observation of the same
   canonical module Git root; arbitrary unequal hashes cannot satisfy it.
3. **Exact current candidate state.** Specification, Cycle-6 record and
   `C1-CURRENT` all freeze production runtime candidate evidence to
   `not_requested`; test/reference `present` remains non-decisive and cannot
   change the absent-cutoff result.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 23A — non-clean; evaluation semantics and registry bootstrap widened

The three sequential technical packets and the record packet reproduced before
and after independent read-only review. No reviewer edited files or crossed the
research toolchain gate:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 700–750, 3048–3102 and 4187–4201 concatenated | 6,357 | `e11d841f7f05f6b9708336db925fd2ca2c4c14778ac807e87c61af9002d1a646` | non-clean: one blocking, zero cosmetic |
| P2A | plan lines 485–535, 1375–1450, 1495–1552 and 2740–2813 concatenated | 12,260 | `97babb7f663179d422c23be04058a72be92e981c386ac29b04a5d91d5ee83917` | non-clean: one blocking across P2A/P2B, zero cosmetic |
| P2B | plan lines 2814–2940, 3348–3455, 3588–3620 and 4210–4228 concatenated | 16,510 | `efbc92abbecd66efe369621c380b1f67a136e1bebada77710f39d820c7bf1c0c` | same P2 outcome |
| record | design lines 680–715, 1110–1128 and 1268–1275; plan lines 202–216 and 7325–7358; journal lines 1418–1465, concatenated | 14,559 | `2d837074e78d5ad2844ee0c6294d6fafdbd6afcb26625881c60dad1a8b8b4706` | non-clean: two blocking, zero cosmetic |

P1 returned `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking`:
the implicit-dispatch graph enumerated expression/operator classes but not all
statement, pattern, comprehension, target and context nodes that can invoke
user code. P2 returned `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan /
blocking`: source-bootstrap failures had no authoritative registry to resolve,
while the nominal one-sided cutoff row could still acquire admitted/rejected
branches through the common shape. The record reviewer returned `NEW_CLASS /
research_method / blocking` because the status packet omitted a decisive spec
binding-key range, and `NEW_CLASS / record / blocking` because Wave 22 named
five technical packets although its table contained four.

The structural repair is:

1. **Complete evaluation-semantics denominator.** Every reachable concrete AST
   node occurrence—statement, expression, pattern, comprehension, target,
   context and operator—gets an exact source/context row and is either lowered
   through the same terminal-edge algebra or proved a syntactic container.
   Unknown nodes fail. `if`/custom-`__bool__` and sequence-pattern dispatch are
   falsifiers in addition to the existing implicit-method attacks.
2. **Pre-registry bootstrap separated from owner-bound post-source policy.**
   Missing/unreadable/corrupt source registry data has its own fixed typed
   bootstrap grammar. A minted source payload carries the exact decoded digest
   registry; post-source cutoff construction validates only against that
   immutable owner-bound object, never ambient bytes or an opaque ref.
3. **Branch shape is structural.** Bidirectional rows necessarily carry
   admitted, satisfied, rejected and not-established branches. A strict
   `not_established_only` row has no positive/rejected fields, so adding them or
   constructing a satisfied cutoff result fails the owner registry relation;
   ordinary bidirectional rows remain valid controls.
4. **Review denominators are generated.** Status packets enumerate every
   binding-key hit across specification, plan, journal and plan entry, and the
   prose packet count is derived from the receipt table. The next record packet
   includes the previously omitted spec disposition lines.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 24A — non-clean; occurrence identity and authority construction widened

Three technical packets and two method/record packets reproduced before and
after independent read-only review. No reviewer edited files or crossed the
research toolchain gate:

| packet | exact target | exact bytes | SHA-256 | result |
| --- | --- | ---: | --- | --- |
| P1 | plan lines 720–760, 3210–3278 and 4378–4392 concatenated | 6,654 | `1a0d626c0d323a781073c79147d52c6b982b150a9bdbbdb129df91a7e911e56c` | non-clean: one blocking, zero cosmetic |
| P2A | plan lines 1425–1695 and 2700–2725 concatenated | 12,819 | `be7ff5d095251632352a32f2f6c85197261313989688393d45a80f3770cac2e7` | non-clean: two blocking across P2A/P2B, zero cosmetic |
| P2B | plan lines 2848–3090, 3520–3635, 3768–3800, 4008–4028 and 4400–4420 concatenated | 24,043 | `f35fd695761fa66dba2a62a1948f83c29b457f9488f16f1c4169ce30286028bd` | same P2 outcome |
| P3A | exact current binding packet A | 19,212 | `d7450658fc9f7909036b35da2ffaf4e84e96daa14f1b33aced4ea0ec03708c55` | non-clean: one blocking across P3A/P3B, zero cosmetic |
| P3B | journal lines 1400–1515 | 8,181 | `1185ac0bbbe99c5b6e4010c7bb1cfb776e7af4d1c3c7a312a69eaf56751ecb05` | same P3 outcome |

P1 returned `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking`:
spanless singleton AST operator/context objects made node identity ambiguous,
so occurrence reconciliation could collapse repeated operators. P2 returned
two `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking` findings:
source-not-established required a tree ID that may be unknowable before source
resolution, and a sibling cutoff helper could construct the final DTO without
the owner-registry validator. P3 returned `SAME_CLASS_ONE_LEVEL_DEEPER /
research_method / blocking`: its independently derived 43 subject-bound lines
included six plan bindings absent from both declared packets.

The structural repair is:

1. **Structural AST occurrence identity.** Every node row is keyed by the full
   `ast.iter_fields` ancestry with field names and list-child indices. Optional
   spans are diagnostic only; object identity is never a key. Repeated operator
   siblings must remain distinct and deleting either fails reconciliation.
2. **Pre-source and source-resolved requests are different types.** The
   source-not-established result carries only the pre-source request and never
   fabricates a tree. Source rejection and cutoff use a resolved-source request
   that adds the owner-derived tree. Missing Git root/unresolvable commit is the
   falsifier.
3. **One cutoff constructor.** The sibling shaped helper is removed. A complete
   AST constructor/returner denominator admits only
   `build_runtime_cutoff_refusal`, requires every outer returner to delegate
   with the live source payload, and requires owner-registry validation before
   return.
4. **Manifest-driven status review.** The four-document, subject-anchor walk
   emits path/line/key/exact-line-hash rows, expands neighbours, partitions only
   from those row identities and rejects uncovered or multiply covered rows.
   Manifest row count/hash and every packet receipt are independently
   regenerated at each freeze.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 25A — technical clean; manifest path profile widened

The three technical packets, manifest and four manifest-derived status packets
reproduced before and after independent read-only review. No reviewer edited
files or crossed the research toolchain gate:

| target | exact bytes | SHA-256 | result |
| --- | ---: | --- | --- |
| P1 | 6,747 | `a13980ee8e8b2a9bd174edf670fc3a6ca4ef108e96afa4d5ba9d9e73ebe44d6c` | **clean: zero blocking, zero cosmetic** |
| P2A | 12,445 | `edac94a0e1f09672f4bf2e9f5b41b255c814fb3b2227ae3408c5f98dea8c543e` | **clean across P2A/P2B: zero blocking, zero cosmetic** |
| P2B | 14,208 | `671c3271f86aaca042ceda56f1b2fa71743577e13aae44f9f9d625af3f882445` | same P2 outcome |
| status manifest | 57,685 | `57ab85e56b43250cd81755e2234b063984ee898edae34e6d3292fc4269f54c43` | non-clean: one blocking across manifest packets, zero cosmetic |
| status packet 1 | 28,000 | `bd4fbb9be711745034cbc7cdce4839179bc69ae80fdff11a892c1d5c2ebf7bc4` | same status outcome |
| status packet 2 | 28,000 | `67698cbb3743d466d46a861876a2528332517d145ea2f1c3aca0bca3d0d1782c` | same status outcome |
| status packet 3 | 28,000 | `c53e7fa7beff86950ec909530bd8a40e80d37bfafd09a6687b7c2177948e49da` | same status outcome |
| status packet 4 | 24,110 | `08b91d42c9ae21fd39a2ef16674245b197161ae6b4e6aa141c0d83a9c7e92e1e` | same status outcome |

P1 returned clean: full field/index ancestry, optional diagnostic span, exact
path reconstruction and repeated-operator reconciliation close the AST
occurrence class. P2 returned clean: the pre-source/resolved-source request
split and the single constructor/returner chokepoint close both authority
construction findings while retaining the accepted branch algebra.

The status reviewer independently reproduced 234 selected lines, 237 segments,
all four packet hashes and exact per-path counts, then returned
`SAME_CLASS_ONE_LEVEL_DEEPER / research_method / blocking`: path-root and packet
index conventions were not canonical, so product-relative or zero-based
serialization could bind the same selected bytes under a different manifest.
The structural repair fixes repository-root-relative POSIX UTF-8 paths prefixed
`policy-engine/`, one-based packet indices, exact tracked line endings and
greedy 28,000-byte fill/split. Repository-root and product-root invocation plus
zero/one-based variants are the falsifiers.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 26 — broad boundaries non-clean; owner planes widened

The repaired status profile and the first two complete cluster boundaries were
reviewed from exact current bytes, not inferred from their earlier delta
reviews. All receipts reproduced before and after read-only review; no reviewer
edited files or crossed the research toolchain gate:

| target | exact bytes | SHA-256 | result |
| --- | ---: | --- | --- |
| status manifest | 57,685 | `35e4edc84833289c9cdf9a1208e6eb8f00039866a75d26a990f5875ce5046bae` | non-clean: one blocking, zero cosmetic |
| status packet 1 | 28,000 | `bd4fbb9be711745034cbc7cdce4839179bc69ae80fdff11a892c1d5c2ebf7bc4` | same status outcome |
| status packet 2 | 28,000 | `67698cbb3743d466d46a861876a2528332517d145ea2f1c3aca0bca3d0d1782c` | same status outcome |
| status packet 3 | 28,000 | `c53e7fa7beff86950ec909530bd8a40e80d37bfafd09a6687b7c2177948e49da` | same status outcome |
| status packet 4 | 24,110 | `08b91d42c9ae21fd39a2ef16674245b197161ae6b4e6aa141c0d83a9c7e92e1e` | same status outcome |
| Cluster 2 | 24,267 | `6f0c59bf2b7429135eb2b8f0e2c7ccdc04c7a3a44c458723b07d1e4c5463da45` | non-clean: five blocking, zero cosmetic |
| Cluster 3A | 27,957 | `76ccc3eb7747709a5d6fcf90fa98c37d3aaf2829522ffc143879fc1d5e2b1828` | non-clean across 3A/3B: five blocking, zero cosmetic |
| Cluster 3B | 4,906 | `b9f9a14db394223e9e52536c590fef36a5675e0704a648cf5f284e629bedf52c` | same Cluster-3 outcome |

The record reviewer returned `SAME_CLASS_ONE_LEVEL_DEEPER / research_method /
blocking`: canonical roots, indices and line endings now reproduced, but an
anchor ±1 line walk still omitted status bytes owned by the same Markdown list
item or paragraph. Changing the registered standing, refusal persistence or
receipt-store maturity left all packets green. The repair freezes the exact
four-path tuple and expands unchanged subject hits to complete Markdown owners
(outer list item, fence, GFM row, heading section or paragraph), with exact
occurrence/owner/line/packet bijections and structural-ambiguity failures. It
adds no rescue anchors.

The Cluster-2 reviewer returned five blocking buckets:

1. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan`: the policy consumer
   claimed owner-byte verification but received only a shaped resolver result.
2. `NEW_CLASS / implementation_plan`: caller-supplied artifact write options
   could mint bundle/sidecar manifest authority.
3. `NEW_CLASS / implementation_plan`: the build/verify failure lattice was
   open and contradictory results were constructible.
4. `NEW_CLASS / implementation_plan`: policy failures lost the native query
   coordinate.
5. `NEW_CLASS / implementation_plan`: the 34-ID map lacked executable B08/H05
   witnesses, a source-derived J05 terminal matrix and the exact B17 empty-head
   representation.

The structural replacement adds an owner admission index, exact artifact-byte
resolver and provenance verifier before adapter access; a closed build/verify
algebra; query-bound negative leaves; adapter-owned bundle/result codecs and
write contracts; a production-internal but unorchestrated qualification
consumer; and a complete 34-ID test/terminal map. The verifier remains
policy-free and the second shape remains non-epoch/test-only.

The Cluster-3 reviewer returned four `SAME_CLASS_ONE_LEVEL_DEEPER /
implementation_plan / blocking` buckets and one `NEW_CLASS /
implementation_plan / blocking`: caller-controlled `None` could bypass
old-to-new consistency; acceptance did not freeze its appointment/trust
snapshot; optional halves did not form the promised independent predicate
product; decisive ref/hash domains were incomplete; and the helper was absent
from the exact commit denominator. The structural replacement derives every
prior prefix from owner-loaded lineage, binds the verified appointment and
trust bytes through the unsigned acceptance/retention graph, defines an exact
acceptance × retention 3×3 result algebra, reconciles every decisive hash field
through one generated domain registry, and adds the helper to Task 3 and its
guarded path set. The production holder remains absent and both positive
appointment branches remain unissuable.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 27 — three delta boundaries non-clean; serializers and owner evidence widened

Three independent read-only delta reviews applied the P40 bucket rule in
writing. No reviewer edited files or crossed the research toolchain gate:

| target | exact bytes | SHA-256 | result |
| --- | ---: | --- | --- |
| status-method delta | 10,008 | `db6d593893b2ceb2eaae60c3490c081bf7f956efb08f3fd0cb45d7c00d79e552` | non-clean: one blocking, zero cosmetic |
| Cluster-2 D1 | 18,550 | `7e4b7f8175831e511d5cd7ed70a077929882947f1bd479e6c11a1236e83f24c1` | non-clean across D1/D2: six blocking, zero cosmetic |
| Cluster-2 D2 | 16,998 | `75038929d2607b3fea9fac256826d0689f2e712d0edce3f0146165fc0cc4029b` | same Cluster-2 outcome |
| Cluster-3 D1 | 16,263 | `not_established` | non-clean across D1/D2: three blocking, zero cosmetic |
| Cluster-3 D2 | 24,112 | `not_established` | same Cluster-3 outcome |

The retained Cluster-3 handoff preserved both byte counts, the three findings
and only truncated hash prefixes; no retained independent receipt now carries
the full digests. They are therefore recorded honestly as `not_established`,
not reconstructed by root after the fact. Wave 28 issues fresh exactly bound
packets and supersedes their substantive result.

The status reviewer returned `SAME_CLASS_ONE_LEVEL_DEEPER /
research_method / blocking`. The complete four-path Markdown-owner walk was
reproducible—115 occurrences, 54 owners, 5,002 selected lines, 5,014 segments
and 358,373 bytes—but its auxiliary container JSON, sort coordinates,
line-ending tokens, container-hash preimage and transfer-receipt grammar were
not canonical. Two serializers over identical selected source produced
1,245,720 bytes / `f8f86b5e...` and 1,244,754 bytes / `20a54ed8...`. The repair
replaces auxiliary JSON with an exhaustive versioned tab row grammar, exact
field/ordering/ending-token rules and a separate transfer receipt. Its one-row
golden fixture binds the source hash, 457-byte manifest and 190-byte transfer
receipt; both earlier serializer variants now fail without changing source.

The Cluster-2 reviewer returned six `SAME_CLASS_ONE_LEVEL_DEEPER /
implementation_plan / blocking` buckets:

1. owner verification did not independently bind the native denominator,
   ordered members or disposition evidence;
2. build and verify shared semantically impossible failure codes and admitted
   contradictory rejection shapes;
3. byte loaders lacked the query context required to construct their typed
   failures;
4. CAS deduplication could preserve an earlier wrong manifest while byte
   verification stayed green;
5. B08 and J05 lacked executable typed/topology-plus-routing witnesses; and
6. the public-surface sync, nearest runtime README and Task-to-commit path
   denominator were incomplete.

The structural repair passes one immutable resolution context to every load;
changes disposition evidence to real artifact refs; and has the owner verifier
re-enumerate the family denominator, resolve every evidence artifact and bind
owner/candidate refs, ordered members and provenance rows before qualification.
It splits builder, envelope, member and consistency failures, makes expected
bundle-hash mismatch reachable, and freezes coherent result invariants. The
artifact adapter now binds expected domain/prefix/hash into a canonical result
statement and compares full manifests after admitting only store-minted
creation time as non-decisive instance metadata. A closed projection-custody
leaf, two-walk topology plus separately read routing/status matrix, canonical
Cluster-2 public-surface sync and exact Task/guarded-array validator complete
the 34-ID handoff without widening it.

The Cluster-3 reviewer returned three `SAME_CLASS_ONE_LEVEL_DEEPER /
implementation_plan / blocking` buckets: appointment verification was still a
ref-only assertion; the digest registry selected fields by spelling rather
than resolved Digest/ArtifactRef semantics; and Ruff used a hand-selected path
denominator. The repair adds signed, content-bound acceptance and holder
appointment-verification statements to the retained object graph; derives the
digest registry from every resolved Digest annotation and nested artifact ID
independent of field spelling; and derives the Ruff file set from the complete
Cluster-3 guarded path array. Missing raw-blob/manifest/signature hashes,
package refs or lineage keys and one omitted Python path are explicit
falsifiers.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 28 — non-clean; candidate, canonical-model and record denominators widened

Seven exact repair packets reproduced before and after independent read-only
review. The P40 bucket rule was supplied in advance; reviewers made no edits
and did not cross the research toolchain gate:

| target | exact bytes | SHA-256 | result |
| --- | ---: | --- | --- |
| status | 10,000 | `9a7a0f4ca6d795a06277afe68b1ea9356893e9d3806508f0a71703564de1beea` | non-clean: one blocking, zero cosmetic |
| Cluster-2 A | 8,244 | `471d36f06a4d7c573ef787cbada1be48f9f53a36de4e87b502a75d80cf145209` | non-clean across A–D: five blocking, zero cosmetic |
| Cluster-2 B | 17,515 | `db6d16c1d86987d11b8ddb45d9daf8d3404c0df94527391b4d33b94fce4559f7` | same Cluster-2 outcome |
| Cluster-2 C | 9,639 | `24c3bec677cd1f17d14b163e8bc1551133a104a2ee7a136cef60602badf52aac` | same Cluster-2 outcome |
| Cluster-2 D | 10,877 | `beeeed2f0c8577582fdbe38c427e581916ff2101261394c4d03a4037f6e74d75` | same Cluster-2 outcome |
| Cluster-3 A | 6,399 | `b74b130a9a687fceb4fe631117a36f63e475080aeec239a71a7cce1a8520066c` | non-clean across A/B: two blocking, zero cosmetic |
| Cluster-3 B | 19,129 | `f919bc5744b7792358fd4162b3ae553a77b448b7dcd8315e12112c08d72d43df` | same Cluster-3 outcome |

The status reviewer returned `SAME_CLASS_ONE_LEVEL_DEEPER /
research_method / blocking`: `sequence-within-packet` had no one-based,
contiguous, reset-per-packet derivation or reconciliation. Globally monotone and
reset encodings preserved the same selected/source packet bytes but produced
different manifests. The repair defines sequence as one plus prior segments in
that packet, reconciles every packet to exact `1..N`, and requires global,
duplicate, skipped and non-reset mutations to fail.

The Cluster-2 reviewer returned five blocking buckets:

1. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan`: the positive owner
   receipt omitted native bytes/profile/admission context/exterior/head and the
   consumer had no denominator persistence port.
2. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan`: one verifier code was
   unreachable and invocation/result contradictions remained constructible.
3. `SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan`: exact CAS manifest
   equality still authenticated caller-invented lineage roles.
4. `SAME_CLASS_ONE_LEVEL_DEEPER / record`: the J05 terminal allocation oracle
   claimed to exist in the GY entry but did not.
5. `SAME_CLASS_ONE_LEVEL_DEEPER / research_method`: both J05 walks shared the
   same narrowed `src`/`tools` Python denominator.

The repair content-binds one complete owner-qualified candidate—including
native bytes/artifacts, all opaque coordinates, limitations and heads—and makes
final reconciliation embed that object instead of parallel fields. Policy
provenance moves inside signed policy bytes and an explicit denominator
artifact port owns persist/reload. Verifier codes are derived from concrete
rejection constructors; the unreachable commitment code is removed and the
verification statement validates every invocation/result relation. Proof
manifest inputs now derive only from the reloaded qualified candidate and must
reconcile to reparsed header/member bytes. The approved terminal matrix is
frozen as a new strict allocation TOML named from the GY entry, while two
independent complete tracked/filesystem Python walks classify every path before
topology analysis.

The Cluster-3 reviewer returned two `SAME_CLASS_ONE_LEVEL_DEEPER /
implementation_plan / blocking` buckets: exact signed appointment bytes still
sat beside caller-mutable parsed authority objects, and the digest-field walk
lacked an independently complete concrete-model/domain denominator. The repair
removes parsed objects from every persisted/verified Cluster-3 wrapper;
consumers reparse only verified bytes, canonicalize, compare and use the local
value. Independent AST/runtime concrete-model censuses now reconcile every
model to exactly one codec/transport/failure class, every canonical codec to
one domain and generated golden pair, and every Digest/nested artifact ID to
the field registry. A new unregistered model/domain fails before a manual list
can hide it. The derived Ruff denominator remained clean.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 29 — status clean; Cluster 2–4 boundaries widened

Ten exact packets reproduced before and after independent read-only review.
The P40 bucket rule was supplied in advance; reviewers made no edits and did
not cross the research toolchain gate:

| target | exact bytes | SHA-256 | result |
| --- | ---: | --- | --- |
| status | 6,484 | `a96d2499831ab17c89bc8bbe15a2f0aff3ae43b4530ba9e83decb323282790ed` | clean: zero blocking, zero cosmetic |
| Cluster-2 A | 10,125 | `94ecad7a841f99910276ebbacd7fb332dc281a77d3690da1f137b8b880f486dc` | non-clean across A–D: five blocking, zero cosmetic |
| Cluster-2 B | 23,424 | `09abbf5ef2ab5b8787912af19ea00700d22f3d398fef8df89d71325c6b84fb6c` | same Cluster-2 outcome |
| Cluster-2 C | 6,410 | `92dea32aee838fd1101a9361122fd6c560176cab23b5b2560560d85e95060fbc` | same Cluster-2 outcome |
| Cluster-2 D | 12,918 | `64bb979f3de5294ba3bd855c4619e37838652c43ca66e9c180c422edab47c091` | same Cluster-2 outcome |
| Cluster-3 A | 16,576 | `588b6de250a7f4dc8836d4ac479cc24e83c736e7177da802e228a48289cb5632` | non-clean across A/B: one blocking, zero cosmetic |
| Cluster-3 B | 20,793 | `927f673ad582506f6371480d6acc3016c7759ec417db23d90e5a443319e84830` | same Cluster-3 outcome |
| Cluster-4 P1 | 25,377 | `08a97fdfeaaa9208183ca9b312a2765792ecf5d867684d23702b1c57a34f00e6` | non-clean across P1–P3: five blocking, zero cosmetic |
| Cluster-4 P2 | 18,989 | `37bf40df7d5b2f28191a2e9c464a4667b648117f278d358069e240336f30d39b` | same Cluster-4 outcome |
| Cluster-4 P3 | 19,750 | `a6244940d843207912cd5881a113537ced56f937e67366661bc1ba6a40b1ffa1` | same Cluster-4 outcome |

The status reviewer returned clean. One-based contiguous sequence derivation,
per-packet reset, exact reconciliation and global/duplicate/skipped/non-reset
mutations now close the retained serializer class; the literal manifest and
transfer fixtures also reproduced exactly.

The Cluster-2 reviewer returned five blocking buckets, all
`SAME_CLASS_ONE_LEVEL_DEEPER`:

1. `implementation_plan`: policy-owner provenance was content-bound but never
   owner-verified, and the predicate-denominator writer remained Protocol-only.
2. `implementation_plan`: shared capacity strings contradicted a supposed
   disjoint-code rule, while early parse rejection plus wrong expected bundle
   hash was not representable.
3. `implementation_plan`: member identities were verified, but denominator and
   query-context semantic subjects were not bound to their artifact bytes.
4. `record`: the allocation TOML lacked an executable schema/row union and
   append-only Cluster-2→4 state transition.
5. `research_method`: the complete-source walk omitted `.pyi` and the
   pre-commit new/untracked Task-2.4 files.

The structural repair adds an independently verified policy-provenance receipt,
two subject-identity receipts and a concrete store-backed denominator adapter;
it freezes an ordered invocation/envelope/member/consistency evaluation state
with explicit not-evaluated predicates and phase-keyed codes. A versioned,
discriminated append-only allocation record now distinguishes capability from
property state and appends the three Cluster-4 activations. J05 walks the full
cached+untracked nonignored `.py`/`.pyi` candidate tree independently from a
filesystem/ignore walk, then rechecks committed HEAD.

The Cluster-3 reviewer returned one
`SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking`: its AST and
runtime model censuses shared the same hand-selected four-module denominator.
The repair derives the module set from every production Python path in Task
3.1 and its guarded boundary, requires a model-owner or AST-proven no-model
classification for every module, and reconciles full-set AST/runtime model
walks. A canonical DTO added to a previously excluded declared path now fails
before registry/golden edits. Parallel appointment predicate/status scalars
were also removed from exact-byte wrappers.

The Cluster-4 reviewer returned five
`SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan / blocking` buckets:

1. the live Ukraine builder remained a parallel hard-coded L5 regime owner;
2. N13b's prepared stamp and future passport ref formed a content-addressed
   cycle;
3. OpenWorldRisk had a reducer/read port but no producer, artifact repository
   or orchestration call;
4. the packet-based DV gate could not be constructed in the first/default
   recursive N9 pipeline; and
5. the Claim bridge/public export accepted caller-shaped completed batches and
   ledgers rather than resolving DV bytes and the Claim owner's current head.

The structural repair makes the Ukraine builder a canonical L5-registry reader
and guards the complete producer/reader denominator; splits stable acquisition
semantics from separately verified post-admission passport evidence; installs a
concrete negative-vector OpenWorldRisk producer/repository before every N9
input; persists a content-bound pre-N9 candidate subject that is threaded
through every direct/recursive/HTTP constructor and later packet; and replaces
the Claim authority entry with a ref-only service backed by a concrete DV
completion resolver and compare-and-advance current-head store. PUBLIC export
now resolves that same head and has no ledger-by-value input.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 30 — specification and Cluster 3 clean; execution denominators widened

Independent reviewers received the P40 bucket rule before reading. All targets
reproduced before/after on attached branch
`codex/gy-n12-epoch-chronology` at
`7445bd48cc58bca24f8531660303176f651f632e`; the expected four-document dirty
state was unchanged. The research toolchain gate remained closed and reviewers
made no edits.

| target | exact bytes | SHA-256 | result |
| --- | ---: | --- | --- |
| specification/GY S1 | 25,789 | `58db60f14189aadad1cea240e4a6a376f611c9ac477a0a70da1163733d910e0e` | clean: 0 blocking, 0 cosmetic |
| specification/GY S2 | 26,560 | `1c042725311e4b3b7c5c09245133e8e63b2fa2da8f6c68aaeb33fd6cc7617484` | same clean outcome |
| Cluster-2 A | 10,810 | `27c9ed30d785ef9a2b741a2ea4a32a26c7529e3a20adddc78ae5b6f116bf186b` | non-clean across A–C: 4 blocking, 0 cosmetic |
| Cluster-2 B | 23,009 | `a56ce4a75592f82b01a8f642b08ec27e06b10abf6b78ac2906411dc8e1df30b3` | same outcome |
| Cluster-2 C | 25,111 | `47dbcf049e231a0adf02744e932cb91a4f17c4d6d4055339fbf1fd418c53eb77` | same outcome |
| Cluster-3 | 12,327 | `7698716e0c374d94f059065ed335b9419e03a7bda54d43ad80d26acdfd0d8e8f` | clean: 0 blocking, 0 cosmetic |
| Cluster-4 A | 27,651 | `0c1cc88f41a73b7ad0603d3e8ece52173ee031ffc33c2605cf5254d2b2564d20` | non-clean across A–D: 5 blocking, 0 cosmetic |
| Cluster-4 B | 24,295 | `f50ca8260f04f42b8209eab847a6535de7ce5fa40b4aebd2a69921d400307d8d` | same outcome |
| Cluster-4 C | 21,935 | `2a191ee450f21cc9c132bbbd7cd4a8dfa3db2f407d8baf39f409acfb477225a0` | same outcome |
| Cluster-4 D | 6,647 | `63e66d1ec85a0195952ddc3e1062f54a12528cb71fce554cc8d2f8082cc852b8` | same outcome |
| tail T1 | 22,167 | `2642900d1354491d32565091fa383c788460b47074f10c9fd4082ebff6a093a3` | non-clean across T1–T3: 4 blocking, 0 cosmetic |
| tail T2 | 18,580 | `0c77f1a35b162b4b1553b6adf2606c206c211fc5cbf0dd27a3f408a1208b3e25` | same outcome |
| tail T3 | 15,818 | `ea2f4773868b1b078fba6679caec5e1c8978fef57bb9f700c654f83f14623ab9` | same outcome |

Specification/GY and Cluster 3 returned clean. Cluster 2 returned four
`SAME_CLASS_ONE_LEVEL_DEEPER` buckets: serializable qualification at the
persistence gate, an ambiguous absent-prefix evaluation state, non-appendable
allocation wire/wrong activation, and an unbound pre/post topology comparison.
The repair uses a one-shot fieldless persistence capability, one frozen
descriptor/evaluation table, predecessor-hashed EOF history and content-bound
candidate/committed/C4/closeout receipts.

Cluster 4 returned five `SAME_CLASS_ONE_LEVEL_DEEPER /
implementation_plan / blocking` buckets: operational ordinal leaked into
semantic epoch identity; OWR provenance used two identity domains; pre-N9
evidence did not reach the canonical receipt; Claim export/head initialization
remained injectable/first-head incomplete; and task/path/test sets diverged.
The repair separates semantic/admission evidence, freezes `ArtifactRef`
provenance, seals subject→gate→N9 resolution, adds owner-private initial-head
issuance/migration and export service, and derives delivery from one execution
manifest. The clean L5/Ukraine strangle is unchanged.

Tail findings formed two structural classes. `TAIL-DENOM-01` was `NEW_CLASS`;
`TAIL-DENOM-02` was one level deeper. `TAIL-GUARD-01` was `NEW_CLASS`;
`TAIL-GUARD-02` was one level deeper. The candidate repair attempted to
remove handwritten path/test arrays, make Add/Modify and every runner
manifest-derived, make commit/suite/source-freeze blocks explicitly fail
closed, and require exact closeout receipt-set equality including backend
verify, CI parity and runtime contract. Return review was still pending; no
closure was claimed.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 31 — repeated classes required one more structural widening

Independent reviewers received the P40 bucket rule before reading. All targets
reproduced before/after on attached branch
`codex/gy-n12-epoch-chronology` at
`7445bd48cc58bca24f8531660303176f651f632e`; the expected four-document dirty
state was unchanged. The toolchain gate remained closed and reviewers made no
edits.

| target | exact bytes | SHA-256 | result |
| --- | ---: | --- | --- |
| Cluster-2 A | 11,832 | `fab52c9c4f0a9bee1a2d2a252ad313c9a09ebadfcc2ee0f719ee04a695d16ac6` | non-clean across A–B: 4 blocking, 0 cosmetic |
| Cluster-2 B | 24,396 | `0a7483cc4c66cb5a54b01746a0504dfe30770dd7c3cd6d45125c94fdde75ade8` | same outcome |
| Cluster-4 A | 19,736 | `e5dbad355f502f010c0f490683bfdf8301440fbd906eba0d26ca8b1fb543e093` | non-clean across A–C: 3 blocking, 0 cosmetic |
| Cluster-4 B | 15,319 | `1041f87b28deec993b973a5e48c54d7b947fb5b73a48b01e1ccf206c6994dbb9` | same outcome |
| Cluster-4 C | 9,850 | `205a0cbb371041a591b298ff6f64e3da8a1f2399f485b05a6c5a1fb9a905062f` | same outcome |
| tail A | 21,122 | `efd2e9fd53c4a10b49f4d485b6dac2044a3792d860286b6c2a9b1739c8155591` | non-clean across tail/journal: 2 blocking, 0 cosmetic |
| tail B | 8,516 | `4d81ca19ae77a00f63ac6ea72227ceb0e524967a6de541524b518d91ee056f4a` | same outcome |
| Wave-30 journal delta | 3,787 | `9fc770b053bfd3a319db0bb48cc1e9ab72258210b729d132e813fbec2992a156` | same outcome |

All nine findings were `SAME_CLASS_ONE_LEVEL_DEEPER` and blocking. Cluster 2
found: the manifest did not bind path→runner→suite receipt→candidate→commit;
the full-prefix/persistence result algebra was not total and allowed a mixed
consistency/prefix terminal; the one-shot persistence capability was not
process/fork safe and remained caller-composeable; and allocation/boundary
receipts lacked an exact digest algebra plus predecessor receipt chain.

Cluster 4 found: one N13b receipt could not both enumerate every operational
row and keep semantic identity invariant under duplicate ordinals; OWR and DV
lacked one owner-resolved query-context artifact that could reach canonical N9;
and the Claim head/root graph was self-referential and omitted live initial
root producers.

Tail review found: validators could bypass the durable suite-index path and
timing changes had no explicit reviewed boundary; and the execution manifest
could not authorize its own bootstrap while pathspec commit/readback still left
a candidate-to-commit race. The journal also overstated Wave 30's attempted
repair and is corrected above.

The authored structural delta splits N13b native completeness from semantic
candidate identity; installs one OWR/DV owner query-context artifact; makes
Claim heads non-self-referential and owner-enumerated; closes the proof result
graph; seals persistence inside one process-generation-aware coordinator;
freezes record digest domains and phase predecessors; and replaces shell lists
with a bootstrap-once, manifest-owned suite-index/candidate/tree-commit chain
plus a conditional timing-budget boundary. These are candidate repairs until
their exact Wave-32 return reviews are clean.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 32 — non-clean; owner and execution chokepoints widened

Independent reviewers received the P40 bucket rule before reading. All exact
targets reproduced before and after on attached branch
`codex/gy-n12-epoch-chronology` at
`7445bd48cc58bca24f8531660303176f651f632e`; the expected four-document dirty
state was unchanged. The toolchain gate remained closed and reviewers made no
edits.

| target | exact bytes | SHA-256 | result |
| --- | ---: | --- | --- |
| Cluster-2 A | 13,858 | `d2f8992dcc80b5fd3aaaeb35485069eb26ab51f64ef029956fe3ae919a0135b4` | non-clean across A–D: 4 blocking, 0 cosmetic |
| Cluster-2 B | 7,407 | `f70a47c18c76be127000c9af6e2e9f2be79ec0635767937b80b23dc2cd55b608` | same outcome |
| Cluster-2 C | 8,539 | `1a2b7bf07e2e21e794352de6e3d01b8329de38100c96884a634d6fdb50823d30` | same outcome |
| Cluster-2 D | 20,059 | `3fe9245c4bf189dc1c59b96a7316b2b5cc748551a8f48a175e14bc1c2a8780e3` | same outcome |
| Cluster-4 A | 14,589 | `648d3dffc059749dda754fa943fdffbbc74f33fb9a6f59ed7367b987907584f0` | non-clean across A–E: 4 blocking, 0 cosmetic |
| Cluster-4 B | 22,291 | `3d66d496ee59c31dd0e67be41a2df85028476c7f475fc9a24e5248c513c3566a` | same outcome |
| Cluster-4 C | 14,762 | `4fca5a9692b4d864efb52eb4b9d26442b138adbce47918d774ebe90fffd8561c` | same outcome |
| Cluster-4 D | 15,084 | `ae8a37621d3b48fbcc27cb9c126a6c6aae90706749cbd86dc97c7644b54735ab` | same outcome |
| Cluster-4 E | 17,067 | `60e34fc4fba8f0f3089aa2d41c1938ef78b0f32aca054a1df460150d7eca6e58` | same outcome |
| execution tail A | 6,164 | `d8a81a6cb4efba7b6717b443b9778d490bdcca3e72552ca1f91a67134a1ae8cd` | non-clean across tail/journal: 3 blocking, 0 cosmetic |
| execution tail B | 17,637 | `3d6271b66dd62518eb05c728005055c27c24678b518bf520b6bd37294dbefa1a` | same outcome |
| execution tail C | 17,093 | `b0d75c0588aedd83e99f3af5f0b9267cfa92160e00e409432d936fcacdf367bf` | same outcome |
| Wave-31 journal delta | 7,162 | `732b53f0a38ca800a83827dab45b0ed757ed180f9a1a3874887dda5ce538415e` | same outcome |

All eleven findings were `SAME_CLASS_ONE_LEVEL_DEEPER`; ten had subject
`implementation_plan` and the uncovered execution digest algebra had subject
`record`. Cluster 2 found that native limitation/result leaves still lost
owner/policy/query context, the persistence factory remained caller-composable,
phase receipts used raw Git strings, and only one of three C2 candidate chains
had a producer or staged-byte check. Cluster 4 found that the shared OWR/DV
query coordinate had no typed aggregate derivation, Claim root issuance and
composition were nonconstructible/bypassable, the asserted file compare-and-
advance lacked an interprocess durability protocol, and the root inventory had
no independent denominator walk. N13b and L5/Ukraine otherwise survived.

Tail review found that undefined runner/candidate variables, duplicate subset
loops, early over-60 aborts, unconditional timing commits and fixed receipt
paths made the manifest lifecycle non-executable; bootstrap review was not
content-bound and ordinary `git commit` reread the mutable index; and suite
index/timing/admission records lay outside the declared digest/phase algebra.

The authored candidate widening now gives every post-policy C2 leaf one owner-
bound context, splits limitation leaves, makes reader negatives query-bound,
removes the importable persistence factory and closes the phase-symbol walk.
Promotion uses a complete candidate-denominator aggregate over separately
typed epoch/deployment query evidence. Claim Ledger gets one required owner
port, immutable verified root issuance, a two-walk root denominator and a
locked durable CAS with no raw sibling mutator. The execution manifest now
owns a boundary-wide measurement/enforcement transition, every auxiliary
digest wrapper, staged-tree reconciliation and `commit-tree`/`update-ref` CAS;
bootstrap consumes an external user-appointed clean receipt. These are
candidate repairs pending their exact Wave-33 return reviews, not a clean
claim.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.

### Implementation-plan Wave 33 — final independent return; root-cause closure followed

Independent reviewers again received the P40 rule before reading. All targets
reproduced before and after on attached branch
`codex/gy-n12-epoch-chronology` at
`7445bd48cc58bca24f8531660303176f651f632e`; the expected four-document dirty
state was unchanged. The toolchain gate remained closed and reviewers made no
edits.

| target | exact bytes | SHA-256 | result |
| --- | ---: | --- | --- |
| Cluster-2 A | 18,274 | `7e1f9df25e1d96892cc9739aaf211b87cf339865e46e2d8941f9e49b12d0882a` | non-clean across A–C: 4 blocking, 0 cosmetic |
| Cluster-2 B | 12,100 | `b78fcda4014c0ad10bf282e9a3a1993f66271eeb3ad36c1956e95689a2b5367f` | same outcome |
| Cluster-2 C | 8,110 | `1cb92f1b872a51bd38ecdf30578a4ed4dc7ffbae3bcd22eb739ffb2908eea0ee` | same outcome |
| Cluster-4 A | 17,224 | `bdee751be84f089c961a65066c2693337c2c96738321af0fa18f157ecb500c94` | non-clean across A–C: 5 blocking, 0 cosmetic |
| Cluster-4 B | 10,541 | `5d56bd4f72a8290cf1846f8c3ca0dbfdf8f85545b982336331fe59639d0b7889` | same outcome |
| Cluster-4 C | 13,978 | `1e2fdeac7f4a6e92be9f131e788528bbbbca9b5da3ea599e1b72a49ee6c59f09` | same outcome |
| execution tail A | 9,994 | `887747286325d3f2c6a568ee705a6abbc994c4ad3b9fa481310771992db3f186` | non-clean across tail/journal: 3 blocking, 0 cosmetic |
| execution tail B | 17,470 | `ecbc4b869546ddd7009c98b757934da3e8edd249608b65d200b63fc6100cbcb6` | same outcome |
| execution tail C | 12,182 | `829454be78bca2d49dd43e4ec708e61a23a8480b73c0e387a18d486f26f8a5f0` | same outcome |
| execution tail D | 9,359 | `d5bf2cc96ede34af4f902eee4cb6734a27f1482e772529a677a15c1abae8a596` | same outcome |
| Wave-32 journal delta | 4,143 | `43f3d14753b6460b9582a49ecf6674142fda29bc2110c37be68bb5553a4b777b` | same outcome |

All twelve findings were blocking and all were
`SAME_CLASS_ONE_LEVEL_DEEPER / implementation_plan` except the C2 receipt-domain
and auxiliary-receipt findings, whose subject was `record`. Cluster 2 found an
incomplete cross-product for simultaneous native limitations and negative
store verification; fork generation stopped after consumer construction;
receipt links were polymorphic across domains; and the old split boundary CLI
survived beside the single transition. Cluster 4 found no producer for the
complete promotion-candidate snapshot, no sealed candidate-member binding
through OWR/DV/N9, circular Claim initial-root issuance, an over-broad required
`ExecutionContext` migration, and underfrozen persistence profiles. Tail found
an impossible dirty-subject/timing-catalog sequence, bootstrap review authority
by shaped hashes with a non-atomic branch predicate, and a self-referential
suite-admission receipt.

The user then stopped recursive instance review and requested exactly two
root-cause passes. Pass 1 widened the four shared roots once: a complete native
result transition table; one process-generation owner registry; post-loop
promotion denominator freeze plus sealed bound-member handles; and two-phase
Claim preparation → persisted packet → verified root registration. It also
restricted the execution manifest to lane-local developer tooling: it cannot
establish any PolicyOS product predicate and must not grow into a fifth owner or
workflow subsystem (`P13`).

Pass 2 removed every executable split/subset suite surface, made observations,
admissions and durable wrappers non-self-referential, made held subject/timing
and closeout use one lifecycle, and made bootstrap authority depend on actual
external bytes plus atomic symbolic-branch/expected-old ref attachment. A local
Git protocol probe found one concrete executor defect: Git 2.49 rejects
`symref-verify` in dereference mode. The plan now sends `option no-deref` in the
same `update-ref --stdin` transaction; an aborted read-only probe returned
`start: ok` and `abort: ok`.

Final dependency-free readback found 22 Python fences and 13 executable zsh
fences, all syntax-clean; Appendix A remained 91 occurrences / 91 unique IDs;
the programme basis remained unchanged at 128; stale split-command and former
authority-interface names were absent; and `git diff --check` was clean. These
are planning-record checks, not runtime or mechanism evidence. The same
readback removed one accidentally duplicated Wave-33 record block; the one
terminal entry remains after Wave 32 and no substantive decision changed. Per
the user's stop instruction, no Wave 34 or further instance-review ladder is opened.
Remaining implementation discoveries are classified against the frozen basis
and this plan during implementation; they do not reopen Cycle-6 research unless
they refute an accepted architecture decision.

No finding consumed an implementation round. No mechanism, governed artifact,
writer, runtime evidence or replay exists.
