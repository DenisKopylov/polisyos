# DS8 Case & Evidence Workspace execution journal

Date: 2026-08-21

Branch: `codex/atlas-ds8-planning`

Approved specification: `docs/plans/active/atlas-slices/DS8-case-evidence-workspace.md`
at `d7068d41f44f0358f89e39871ddad6a5bf7ca232`.

## Superseded full-slice stop receipt

The initial execution bound documentation-only base
`6049bf450c298885fa6b9077a144766b5fcd7c7a` and correctly stopped at C00 with
`artifact_missing`: a complete AST walk of 5,579 tracked Python files and an
independent textual census both found zero production callers of
`persist_runtime_policy_design_case_graph` and
`persist_s2_design_search_run` (one and six test calls respectively).
`DesignRecordV0` has no admitted run/case/tenant binding and no manifest
closure edge. Focused helper/current-absence verification was 15/15.

The capability remained `producer_missing + bridge_missing +
consumer_missing + semantic_test_missing`; no builder, mock authority, global
index or unrelated persistence route was added. The stop consumed 0/12 rounds,
changed only this journal, left OpenAPI/generated clients/register/snapshots
untouched, and released or never acquired all three serialization resources.
The protected plan-line hashes, 147-entry DS5 corpus, 383/30 status inventory,
13-diagnostic status receipt `511bfd68…17f9`, 18/34/2/0 generated-client
census, and legacy A4 bytes were preserved. Revision 3.29 accepted that stop,
registered `case-record-not-run-bound` to `team-runtime`, and recut only the
independent DS8-A clusters below.

## DS8-A continuation — Revision 3.29

The owner accepted the `artifact_missing` stop at zero rounds and narrowed its
scope. DS8-A resumes the paper, support-rebind, run-terminality, register and
closeout clusters while `case-record-not-run-bound` remains a registered typed
unavailable owned by `team-runtime`. DS8-B alone inherits the case-inspection
endpoint, resolver, Case Workspace and MACHINE twin.

The attached branch advanced append-only to user-directed immutable base
`9e6a43b53d11166e90df376940cb34ff15b77289` through merge commit
`0a6e45645e21234c9c4b4a7cc8d5811e8e3056f2`. Independent complete Git
comparisons from `6049bf450c298885fa6b9077a144766b5fcd7c7a` to the new base
each returned exactly one documentation path:

```text
M policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
```

The reallocated mechanism budget is **nine rounds**, with C03's two rounds not
transferred and C01's paper-only scope halved:

| cluster | DS8-A scope | mechanism rounds |
| --- | --- | ---: |
| C00 | new-base bind, red tests and artifact-role preflight | 0 |
| C01-A | full paper contract, replay pins, href and typed unavailable case slot | 1 |
| C02 | OpenAPI plus both generated client families | 1 |
| C03 | DS8-B; not attempted | 0 |
| C04 | four support-only artifact/evidence rebinds | 2 |
| C05 | consume `RunSummary.run_terminality` without substitution | 1 |
| C06 | paper producer/consumer, egress closure and composed A4 gate | 2 |
| C07 | complete 145-production-path governed map | 2 |
| C08 | frozen closeout, two no-writer receipts and C13 handoff | 0 |
| **total** |  | **9** |

Opening spend is **0/9**. P40 remains binding: classify each finding before a
repair; on the second finding of one class, widen once or declare a bounded
residual with its falsifier; never add a third patch. Tests, this journal,
generated/release companions, governed register records and the one authorized
bounded snapshot derivation remain P39 record companions rather than mechanism
paths.

### C00 artifact-role preflight

The paper source denominator was walked before contract work. DS8-A admits only
facts already bound into the terminal run closure:

| paper role | admitted source | binding / negative |
| --- | --- | --- |
| run identity, terminal state and times | verified terminal `core.run_manifest` plus producer-owned `RunSummary.run_terminality` | the canonical bound-manifest resolver must re-check CAS bytes, sidecar kind/media/schema, run/tenant/cell identity, producer provenance and registry lineage; terminality is the exact `terminal` / `non_terminal` / `not_established` value and is never inferred from status |
| replay identity | manifest artifact id and schema plus a versioned paper-projection rule and recomputed projection hash | all pins are required together and recomputed; omitted, partial, mixed or mismatched pins fail with 409 |
| run stage trace | the verified manifest trace/provenance reference | this is the `#stage-trace` section of the run paper, never a case/DesignRecord stage or promotion claim |
| ordinary artifact links | exact manifest outputs with content-bound artifact identifiers | only admitted links are preserved; a valid zero-link packet emits no synthetic link |
| case / DesignRecord | no admitted run-bound source exists | the full ABI slot is `artifact_missing`, reason and closure signal `case-record-not-run-bound`, capability state `producer_missing`, owner route `team-runtime`, with a non-empty `may_not_use_for`; case values may not be built, mocked, globally indexed or borrowed from unrelated persistence |
| browser-local reviewer state and signed public targets | no admitted paper source | excluded from the packet and from every print/MACHINE egress |

This classification makes the available run-paper projection independent of
the unavailable case slot. A Cycle Board href is resolver-backed only when it
addresses the verified run-manifest paper projection and its complete replay
tuple. An unavailable or foreign-tenant run remains a typed absent href; a
mere string or guessed route is not an available fact.

### P40 property widening before source work

The earlier C05 validator omission is the first finding, and the C06
route/query/loader/prefetch bypass is the second finding, of one class: the
declared path set was narrower than the single-response typed-egress property.
DS8-A therefore widens this mechanism once and will not pay site patches for a
third example.

- C05 is **two** production mechanism paths: `src/api/validators.ts` preserves
  the producer-owned three-state value and `RunsListPage.tsx` consumes it.
- C06 is **eleven** production mechanism paths: one raw-byte paper hook, one
  pure paper presentation, one exact-byte export helper, the canonical query
  key, report loader, report prefetch, route manifest, runs route, report
  consumer, overview link-only consumer, and scoped print CSS.
- Tests, generated artifacts, package/lock and PDF helpers, the journal,
  register/inventory and bounded snapshot are mandatory P39 companions outside
  those mechanism counts.

The widening targets the property: one resolved paper response supplies the
typed DOM, print tree and byte-identical MACHINE download; `/report` is its only
emitter, while `/overview` can link/prefetch but cannot render or export its
payload. A later route or component instance of the same class folds into this
invariant and consumes no new patch round.

### C00 red receipts

`corepack pnpm install --frozen-lockfile` completed first, exit 0 in 1.7
seconds under a fixed 180-second ceiling, with no tracked delta. The focused
frontend red ran 27 tests in two files: 22 passed and five failed in 11 seconds
under a 120-second ceiling. The three validator failures prove Zod discards
each producer state, the negative proves missing terminality is accepted, and
the real-DOM failure proves the list renders none of them.

The corrected focused backend red completed in 17 seconds under a 60-second
ceiling: seven of seven tests failed for only the intended missing mechanisms.
Five `/paper` tests received 404/no OpenAPI operation, and the two Cycle Board
tests failed because `CycleBoardProjectionService` has no injected stage-trace
resolver. Both runs recorded an `uptime` pair and completed; these are red
receipts, not killed non-receipts. C00 changes no production mechanism and the
mechanism spend remains **0/9**.

## C01-A — frozen run-paper producer and Cycle Board bridge

The one C01-A mechanism round landed as the seven-path property declared by
the plan: strict frozen DTOs, one manifest-backed projection service, public
reuse of the existing bound-terminal-manifest verifier, one `/paper` operation,
the Cycle Board source-kind extension, resolver composition, and request-tenant
DI. `openapi_contract.py` and tests are P39 companions.

The producer requires exact owner `RunSummary.run_terminality == terminal`,
then re-verifies the manifest CAS bytes, sidecar kind/media/schema, run/tenant/
cell identity, producer/environment provenance and registry lineage. Trace and
ordinary output refs are separately verified against their sidecars before
they become paper facts or links. The projection carries no request clock,
browser state or signed target. Its semantic hash excludes self-referential
addresses and pins.

The full case ABI is frozen with an available arm for a content-bound
`DesignRecordV0`, separate grounding/admission/promotion facts and distinct
blocker/limitation/objection/abstention objects. DS8-A has no code path that can
construct that arm. Every emitted packet instead carries exactly the registered
`artifact_missing` / `producer_missing` / `case-record-not-run-bound` /
`team-runtime` typed unavailable, with all nine denied uses and no available
keys.

The available arm is not merely field-shaped. DesignRecord digest/ref/kind/
media/schema and case/record/run/tenant identities are structural invariants.
Each future authority or issue source carries content hash, schema, producer,
role, verifier id/version and verifier-bound case/run/tenant/record identity.
Grounding, admission and promotion use their closed owner vocabularies and
require distinct source artifacts and validators; a candidate admission cannot
carry governed promotion. The packet recomputes its complete semantic hash,
ordinary artifact hrefs derive from their refs, and hashes, pins and addresses
must agree.

Replay is zero pins for the current packet or exactly all four recomputed pins.
The HTTP boundary walks raw query multi-items before FastAPI can collapse them:
unknown or duplicate keys in either order return 422, as does malformed syntax;
well-formed partial, stale and cross-generation tuples return 409
`run_paper_replay_conflict`. Complete replay returns byte-identical HTTP content.
The report href serializes all four pins before `#stage-trace`. Cycle Board only
emits that href for a non-`None` tenant-bound resolver result and adds its
manifest id and projection hash to the composition manifest; changing the paper
hash changes both board composition and projection hashes.

P40 classified raw-query scalar collapse and stale semantic-content replay as
the first and second findings of one replay-identity class. The mechanism was
widened once to the whole raw-multiset plus semantic-content property. A stale
unavailable-to-available substitution now fails on semantic hash recomputation,
while an independently recomputed available packet passes; wrong source role,
verifier identity and derived artifact href each fail their own invariant. The
remaining declarative verifier/content proof is a bounded DS8-B residual: only
the registered run-bound producer/resolver can establish those source bytes,
and DS8-A's emitter has no available-arm path.

Final measured greens, each with a fixed ceiling and `uptime` pair:

- paper API, real-CAS corruption, raw replay syntax, semantic binding and strict
  OpenAPI union: 8 passed, 11 seconds / 60;
- resolver/Cycle Board link and composition hashing: 2 passed, 8 seconds / 60;
- global runtime OpenAPI examples/problem hardening, including independent
  paper-example hash recomputation: 18 passed, 28 seconds / 90;
- focused Ruff over all C01-A and companion paths: clean.

The worktree-local `.venv` did not contain Ruff, so that first static-check
attempt was a tooling non-receipt; the repository environment's Ruff module ran
the exact path set clean under the same 60-second ceiling. Three final
delta-only reviewers returned GO: API/OpenAPI, authority/content binding, and
focused behavioral tests. The last reviewer independently completed the
combined 28-test set and reproduced both stale-swap rejection and recomputed
available acceptance.

The real-CAS negative first obtained the packet, changed the exact manifest
blob while preserving its id/ref/shape, and then proved both the HTTP producer
(409 `run_paper_source_invalid`) and direct stage-trace resolver (`None`) fail
closed.

A broader Cycle Board/API replay returned one unrelated red: the raw governed
owner packet was `invalid_source` where an existing test expects `available`.
P41 replay from an archive of immutable slice base `9e6a43b53` reproduced the
identical assertion in 20 seconds / 90. The failing subpredicate reads the
unchanged `services/governed_projections.py` definition, owner JSON and owner
validator; C01-A's route DI and composed-paper additions do not enter it. It is
therefore an inherited completed red, not a C01 repair or stop.

C01-A mechanism spend is **1/1**; cumulative spend is **1/9**. The
`case-record-not-run-bound` producer gap remains owned by `team-runtime` and no
DS8-B route, resolver or workspace was attempted.

At the continuation bind, all three serialized resources were unheld. The
protected line-7 byte hashes are Atlas
`74cd4a8823318ffb00c349d05e19c7d8413b2123a6bd5c15ab88f291a837aebf`
and GY
`ffe105ef594603c3a2a3a0247d41cb188529c4fd6fd72cab3ddfbde7956fc6e0`.

## C02 — generated paper clients

The regeneration token was acquired once after the C01 freeze. Two setup
attempts were tooling non-receipts (`fastapi` absent from the worktree venv;
then `tools` absent from `PYTHONPATH`) and changed no generated output. With
`PYTHONPATH=src:.` and the repository environment, the OpenAPI export completed
in 7 seconds / 60; both generated TypeScript families then completed in 3
seconds / 60. Generated outputs were never hand-edited.

The first architecture receipt found four DS8-owned imports below the stable
facades. One convergence repair replaced terminality and artifact internals
with the owner literal and `polisyos.core.artifacts` facade; focused paper tests
(8 passed) and Ruff were clean. A final derivation then reported both actual
GY-DEF20 predicates clean: runtime-api-client **5/5** generator-observed outputs
and runtime-dashboard-api-types **1/1**. The composite remained red only for the
six inherited `deep-import-baseline-stale` edges; no DS8 path appears in that
denominator and `guardrails sync` was not run.

The independent generated-client census walked 1,377 JSON/TOML candidates and
returned 18 primary plus 18 independent anchors, 34 construct identities, two
absence predicates, zero legacy line bindings and zero errors. C02 spends
**1/1**, cumulative **2/9**. The regeneration token was explicitly released
after these predicates were read back.

### C04 P40 classification before repair

The first delta review classified the surviving SLA-colored thread bar and
governing container as **SAME-CLASS-DEEPER** local authority clothing. C04-R1
therefore widens once to the complete local-SLA presentation property: neutral
geometry and labels with explicit interaction-purpose/display-state metadata.
It does not invent `ProjectionFreshness` or claim the registered authority
rows closed.

The final C04 review classified the new accessible 0–100 meter as a **NEW
P38/P15 proxy class**: the clamped decorative width is not a producer quantity.
C04-R2 removes that invented measurement, marks the bar decorative and keeps
only the interaction labels semantic. This exhausts C04 at **2/2**.

C04 red was 4 failures / 10 passes; green is 14/14 across the four support
views, targeted ESLint and dashboard typecheck clean. Final read-only review is
GO. No route, field, MACHINE view, or authority-debt closure is claimed.
Cumulative spend is **4/9**.

## C05 — run terminality consumer

P40 classifies the page-only omission as **SAME-CLASS-DEEPER** content
preservation, already widened in C00 to one ingress-plus-consumer mechanism.
The generated `RunTerminality` union now validates exhaustively at Zod ingress;
the list renders and exports that exact field in neutral clothing, never status
or Cycle Board substitution.

The focused validator/hook/fixture/page wave is 33/33; the two P15 files remain
12/12; targeted ESLint and dashboard typecheck are clean. A complete UTF-8 walk
of 984 tracked dashboard `src` TS/TSX files (zero ambiguous) and independent
`rg` occurrence census agree: production has three occurrences/three lines in
exactly two paths—validator (one) and RunsListPage (two)—beside two generated
and 15 test occurrences. Thus C05 discharges `run-lifecycle-terminal-fact`.
C05 spends **1/1**, cumulative **5/9**.

## C06 — report-only paper and MACHINE egress

Before C06 production work, review classified missing server-side
`runs.review` enforcement on `GET /runs/{run_id}/paper` as a **NEW P05
action-permission class**. Tenant isolation is necessary but does not authorize
the reviewer/expert audience. The property repair is structural at both ends:
one server action dependency denies a same-tenant VIEWER before projection,
and only a verified frontend `runs.review` child may mount the sole paper
query. This is ABI-neutral and does not authorize another client generation.

The earlier route/query/loader/prefetch escape remains the already-widened
single-emitter class: all eleven frontend mechanism paths move as one property
repair, not as further site patches. C06 enters at **5/9** with two rounds.

C06-R1 replaced the interactive report reconstruction with one generated-client
paper query whose response bytes are cloned before parsing. The report loader
and intent prefetch are parser/no-network seams, `/report` is the sole payload
renderer and MACHINE exporter, and `/overview` retains only a review-gated
canonical link. The paper document consumes no RunInspector, timeline, error,
telemetry, Operator Craft or browser-local state. Its controls are print-hidden
siblings; only admitted manifest-output links may print targets, and signed
public-decision targets remain globally suppressed.

Round-one review found four property escapes. The unavailable ABI admitted an
arbitrary non-empty denial list; the client did not bind the response run to the
requested run; selected-field assertions were not a real DOM/MACHINE parity
proof; and the report browser census stopped at the document root rather than
the complete print page. P40 classified the first and fourth as deeper examples
of the already-widened unavailable/egress classes, and request identity plus the
parity verifier as new P32 and P29/P31 classes.

C06-R2 closes those properties once. The backend and client require the exact
nine-member canonical denied-use tuple without changing OpenAPI bytes; the
captured packet must name the requested run. A recursive canonical roster now
emits every object, array (including empty), null and scalar leaf of the complete
paper presentation as visible semantic DOM. The decoder reconstructs that value
from uniquely addressed nodes, binds raw facts to printed text, rejects missing,
duplicate, extra, changed, localized or reordered facts, and separately proves
that every rendered anchor is exactly one admitted artifact link. Both union
arms execute: typed unavailable and an available DesignRecord fixture carrying
grounding/admission/promotion plus one blocker, limitation, objection and
abstention. The available arm remains test-only; production construction count
is zero and `case-record-not-run-bound` remains `producer_missing`.

The composed browser gate now walks the whole live print page for both routes:
visible controls, HUD/Craft nodes, text and every anchor. It asserts overview
has no paper payload or link, report links equal the packet in order, and the
browser-local sentinel is absent from page text, response bytes and the exact
download. PDF capture waits for bundled fonts and consecutive stable geometry;
every MediaBox and CropBox is A4 portrait within 0.5 point, and the honest
zero-output versus 64-output run pair may only assert that admitted growth adds
pages. The raster is bounded to the stable report identity region.

Final non-browser receipts: backend paper API **13/13**, frontend focused wave
**56/56**, dashboard typecheck, focused Ruff and targeted ESLint all green. The
generic consumer census independently reconciles 581 tracked and physical
production TS/TSX files. Both GY-DEF20 freshness predicates remain clean at
**5/5** and **1/1**; the composite remains red only for the six inherited deep
imports. Final delta review is GO across five packages below 28 KB. The legacy
`724×2,113` PNG remains 231,141 bytes with SHA-256 `a920f6c9…`, byte-unmodified
until C08 runs the serialized semantic/PDF gate. C06 spends **2/2**, cumulative
**7/9**. No serialization token or register/visual lock is held.
