---
title: PolicyOS Atlas Surface Constitution And Frontend Vision
status: draft design decision - derived surface constitution
owner: team-design
created: 2026-06-10
last_reviewed: 2026-06-10
decision_status: proposed - derives frontend and design-system laws from the Universal Policy Design constitution
validity_snapshot: 2026-06-10
supersedes:
  - docs/plans/active/FRONTEND_SOTA_PLAN.md as a vision source
  - docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md as a vision source
informs:
  - docs/plans/active/POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md
  - docs/brand/ATLAS_DESIGN_SYSTEM.md
  - docs/brand/ATLAS_V4_ADOPTION.md
  - future docs/plans/active/atlas-slices/
source_constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
source_design_doc: docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md
related:
  - docs/reference/policy-design-case-failure-patterns.md
  - docs/reference/frontend/workspace-contract.md
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - design/atlas-v15/PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip
evidence:
  atlas_v15_archive:
    path: design/atlas-v15/PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip
    sha256: 28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969
    admission_status: implemented_but_not_orchestrated
external_anchors:
  - https://www.gov.uk/guidance/government-design-principles
  - https://designsystem.digital.gov/
  - https://www.w3.org/TR/WCAG22/
  - https://www.w3.org/WAI/ARIA/apg/
  - https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf
  - https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
---

# PolicyOS Atlas Surface Constitution And Frontend Vision

## What This Document Is

This document is the **derived surface constitution** for PolicyOS Atlas: the
frontend, design system, public/accountability surfaces, trust/docs surfaces, and
product-flow language that expose the Universal Policy Designer to humans and
machines.

It is deliberately **not** a second product manifesto. It derives every
load-bearing frontend rule from
`universal-policy-design-system-vision-and-organizing-rules.md`. If this document
and that constitution disagree, the constitution wins and this document must be
amended.

It is also not an implementation plan. Plans and executable slice specs should
live under `docs/plans/active/atlas-slices/` once this decision is accepted.

## Problem

The current repository has strong but drifting surface material:

- `FRONTEND_SOTA_PLAN.md` names broad frontend ambitions.
- `DESIGN_BEST_IN_CLASS_PLAN.md` records v4 Atlas product surfaces and now reads
  largely like completed deep-product history.
- `POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md` is the
  richest public/client/trust/procurement plan, but it is based on v7.
- `docs/brand/ATLAS_DESIGN_SYSTEM.md` and `ATLAS_V4_ADOPTION.md` canonize v4.
- `design/atlas-v15/PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip`
  contains a far richer v15 design-system package, but it is not admitted into
  the repo runtime or verified as a PolicyOS capability.

This creates exactly the failure mode the system already rejects elsewhere:
multiple local constitutions, drifting authority, and impressive artifacts that
are not yet wired into the capability chain.

The deeper issue is conceptual. Frontend work is not a product beside runtime.
It is the missing surface link in the existing definition of "implemented":

> typed contract/artifact -> producer -> persisted artifact/event ->
> orchestration bridge -> consumer -> verification ->
> PUBLIC/REVIEWER/EXPERT/MACHINE surface -> negative + semantic test.

A runtime capability without a surface is not implemented. A surface without the
runtime chain is not authority. Atlas exists to close that chain honestly.

## Non-Goals

This decision does not:

- choose exact routes, component APIs, token names, or implementation order;
- bless any archive, zip, prototype, component, or route as production-ready;
- replace the Universal Policy Design constitution;
- create a parallel status lattice for UI;
- make public/trust/marketing claims before runtime authority exists;
- define a new product strategy independent of the grounding backbone.

## Core Decision

PolicyOS Atlas is the **surface calculus** of the Universal Policy Designer.

It renders the state of the authority system, not an independent story about the
authority system. Its job is to expose, for each audience, what the runtime can
ground, what remains candidate-only, what is limited, what is contested, what is
blocked, what is publishable, and what has been superseded, revoked, or learned
from.

The product stance is:

> Atlas is the civic evidence cockpit and publication layer for admissible policy
> design, derived from the grounding constitution and admitted through the same
> conformance discipline as any other external capability.

Best-in-class for PolicyOS is therefore not "a better dashboard." It is the
interface discipline that makes the system proud to say "we do not know yet"
when the authority chain is incomplete.

## Current State Snapshot (2026-06-10)

The surface system must start from the same honesty as the runtime constitution:

- Layer 2's composed design mechanism is safe, but B output is shadow-only.
- Layer 3 is still grounding and subordinating engines. Local slice plans cover
  G0-G5 and GL; the master plan continues through G6 bounded agent, G7 envelope
  widening, and G8 health-metric governance.
- The proving ground remains the honest product signal: 13 canonical cases,
  named missing links, and zero useful grounded runtime designs until Layer 3
  converts at least one case.
- Atlas v15 is a strong external artifact, but relative to this repository it is
  `implemented_but_not_orchestrated` until admitted by a DS0-style conformance
  battery and connected to runtime consumers.
- Public accountability surfaces should exist first as honest status and
  evidence-readiness projections. Public recommendation/publish surfaces are
  gated by the promotion gate and grounded artifacts.

This section is a dated snapshot, not a durable source of truth about Layer 3
progress.

## Validity And Re-Derivation Triggers

This document remains valid only as a derived surface constitution. Re-derive,
do not patch around, when any of these triggers fires:

- before writing the Atlas frontend/design-system master plan or DS0 slice plan;
- after Layer 3 closeout, especially G6 bounded agent, G7 envelope widening, or
  G8 health-metric governance;
- when
  `docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md`
  changes a rule, enforcement mechanism, status-lattice statement, or capability
  reality bar;
- when
  `docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md`
  changes D3.7 status composition, D3.8 promotion, public projection, or
  machine-readable export obligations;
- when DS0 admits, rejects, supersedes, or replaces Atlas v15 archive content;
- when external conformance anchors change in a way that alters the bar
  (WCAG/APG, government-service design guidance, AI transparency obligations).

The current-state snapshot above must be refreshed from Layer 3 closeout
artifacts before any implementation master plan uses it for scope or priority.

## Pattern Pass

The surface program exists to close or avoid these known failures:

| Pattern | Surface risk | Closure move |
| --- | --- | --- |
| `P01` Contract-only capability | A route or component exists but no producer/bridge/consumer chain feeds it. | Surface readiness requires the full capability chain and a negative/semantic test. |
| `P03` Internal richness with poor external surface | Runtime knows status/evidence but PUBLIC/REVIEWER/EXPERT/MACHINE cannot inspect it. | Multi-audience projection is a required link, not a nice-to-have. |
| `P04` Status enum proliferation | Component state matrix becomes a second authority status system. | Separate interaction state from runtime authority status; UI never invents authority states. |
| `P05` Authority dilution | Public, dashboard, docs, or export surfaces appear more authoritative than their source. | Every surface consumes `authoritative_for` / `may_not_use_for`; unsupported claims fail closed. |
| `P06` Shim drift / canonical ownership ambiguity | v4/v7/v15 design artifacts become competing sources of truth. | DS0 adoption ledger records supersession, conformance, maturity, and rejected deltas. |
| `P10` Structural-only validation | Archive lint or visual polish is treated as semantic/runtime readiness. | Browser, accessibility, authority, semantic, and laundering negatives are required. |
| `P13` Contract gravity well | Design-system governance becomes ceremonial and slows surfaces without adding truth. | Define once, reference; make gates proportional to authority and public risk. |
| `P15` LLM speculation laundering | B/LLM/agent/search outputs look like final claims. | Candidate clothing is mandatory; A-grounded outputs are visually and semantically distinct. |
| `P25` Search-control laundering | Search/frontier/no-hit UI implies authority or exhaustiveness. | Search surfaces show frontier, incompleteness, recall/freshness, and candidate-only posture. |
| `P26` Responsibility-integrity laundering | Approval UI shifts accountability to or away from humans. | High-stakes actions surface mandate-bounded human decision integrity. |

## Derived Surface Laws

Every law below is a frontend dual of the Universal Policy Design constitution.
These are not new independent principles.

| Constitution rule | Surface law | Enforcement status |
| --- | --- | --- |
| 1. A grounds, B generates | B, LLM, agent, search, and exploratory engine output always wears candidate clothing. It must never share the same visual authority posture as grounded A output. | [existing] `AuthorityBoundary` contracts and candidate firewall checks; [to build] source-class badges, UI rendering rules, visual regression cases for candidate vs grounded, and tests blocking candidate output in approval/publication slots. |
| 2. Generation is candidate, never authority | Natural-language answers, draft claims, suggested risks, search hits, and agent orchestration choices are proposal/control-plane state until A admits them. | [existing] candidate firewall contracts and `may_not_use_for`/projection semantics in runtime; [to build] LLM/agent output labels in Atlas and negative UI tests where fluent text cannot populate authority slots. |
| 3. Fail closed and downgrade by default | Missing data, missing producer, stale index, absent right, failed conformance, or out-of-envelope scope renders as typed blocker, limitation, or grounded abstention - never as decorative empty state. | [existing] typed blockers and readiness/projection checks in runtime; [to build] empty-state taxonomy tied to runtime blockers and route tests for fail-closed rendering. |
| 4. Authority composes to weakest boundary | Summary cards, dashboards, public records, and badges show the weakest grounded boundary and its reason. They never average away weak links. | [existing] runtime weakest-boundary concepts and mixed-status obligations; [to build] API/client resolver use in Atlas, aggregation tests, and visual treatment for weakest-link explanations. |
| 5. Optimize honesty, not usefulness | Atlas optimizes truthful state comprehension, not fullness, green dashboards, or conversion copy. "Unknown", "blocked", "outside envelope", and "contested" are first-class designed states. | [existing] constitution objective and capability-reality labels; [to build] surface success metrics, reviewer tasks, and checks that no KPI rewards making screens appear complete. |
| 6. Untested is out-of-envelope | Surfaces show the certified operation envelope and mark untested axes/combinations as out-of-envelope by default. | [existing] envelope and authority-boundary contracts; [to build] envelope chips, scope matrix, and tests where untested axes cannot be rendered as ready or publishable. |
| 7. Closed cases are immutable for replay | Public records and reviewer snapshots never mutate closed-case facts. New evidence is rendered as supersession, reissue, learning, or historical influence. | [existing] replay/versioning discipline and rule-version obligations; [to build] public snapshot handles, bitemporal UI affordances, and copy distinguishing "this case" from "new evidence". |
| 8. One status lattice | UI renders runtime authority statuses; component interaction states are not authority statuses. | [existing] composed status lattice requirement (D3.7 / S1); [to build] static lint for unauthorized UI status enums, state taxonomy split, and contract tests mapping API statuses to UI variants. |
| 9. External power enters only through the waist | UI does not hand-fetch or locally infer authority. It consumes typed OpenAPI/runtime-api-client contracts and admitted projections. | [existing] OpenAPI -> runtime-api-client workspace contract and runtime contracts; [to build] no hand-written authority fetch lint, API client boundary tests, and no UI-side authority-computation checks. |
| 10. Define once, reference | Tokens, statuses, surface grammar, evidence labels, and product-flow contracts live once and are referenced by routes/components/docs. | [existing] canonical runtime contracts and design workspace ownership; [to build] shared Atlas registries, duplicate-label/static-copy lint, and docs links to canonical contracts rather than restated rules. |
| 11. Human principal stays accountable | Approval, override, publication, revocation, and high-stakes review show mandate, evidence exposure, dissent, override reason, and responsibility integrity. | [existing] `HumanDecisionRecord` and approval/human-review contracts; [to build] Atlas step-up flows, review-effectiveness telemetry surfaces, and rubber-stamp/uninformed-approval negatives. |
| 12. Capability follows corpus/search, never enumeration | Navigation, capability pickers, method/dataset/source/case selection, and availability surfaces are search-driven over typed indexes where capability is open-ended. Hardcoded feature menus may exist only for fixed app chrome, not capability discovery. | [existing] Layer 3 no-hardcode/search discipline for grounding; [to build] no-hardcode capability-menu lint, free-growth UI tests, search-frontier/recall/freshness surfaces, and typed-index-backed route/picker data. |

## Surface Families And Subordination Order

The surface families are not equal in readiness. They are subordinated by the
same shadow -> governed discipline as runtime capabilities.

### 1. Runtime Workspace

Primary audience: REVIEWER and EXPERT, with MACHINE evidence behind every
surface.

This is first because it has the most real substrate today: run detail, evidence
fabric, governance, public-sector readiness, publication packet, and operator
craft already exist in the app. Runtime Workspace should become the canonical
surface for:

- proving-ground board;
- design/case state inspection;
- evidence source and lineage inspection;
- grounding/admission/promotion state;
- blocker, limitation, contestability, and abstention review;
- human decision integrity.

Runtime Workspace is the first surface family allowed to grow from shadow to
governed because it can inspect incomplete authority without marketing it as a
product claim.

### 2. Atlas Design-System Product

Primary audience: engineers, designers, accessibility reviewers, and MACHINE
quality gates.

Atlas v15 is treated as a subordinate external engine/artifact. It can be rich,
but richness is not authority. It must pass a DS0 admission slice before it
becomes the repo's canonical design-system substrate.

Required DS0 admissions:

- v4/v7/v15 supersession ledger;
- token, component, state, data-viz, theming, governance, i18n, Figma, content,
  privacy, and product-pattern inventory;
- conformance battery for archive claims;
- runtime consumer inventory;
- browser/accessibility/assistive-technology evidence plan;
- maturity assignments (`fail_closed`, `predictive`, `calibrated` where
  applicable; or design-system equivalents);
- rejected deltas and sunset dates;
- no parallel status lattice proof.

Until DS0 closes, v15 is a high-quality artifact source, not the authority source.

### 3. Trust / Docs / Procurement Surfaces

Primary audience: PUBLIC and REVIEWER, with legal/security/product owners.

These surfaces may publish evidence-mapped posture before G4, but they must not
publish claims of grounded policy-design performance that the runtime has not
earned. Their correct early role is:

- methodology and authority explanation;
- current envelope and limitations;
- accessibility/conformance evidence;
- trust center evidence map;
- procurement readiness and legal copy that says exactly what is supported,
  planned, blocked, or out of scope.

Every trust claim needs a source, jurisdiction, owner, review date, and
`authoritative_for` / `may_not_use_for`.

These surfaces also inherit the civic operations bar: no third-party trackers on
public accountability paths, security headers, privacy-by-default analytics,
measured Core Web Vitals budgets, and locale coverage for the supported public
contexts, starting with `uk` and `en` where Ukraine-facing material is published.

### 4. Public Accountability And Publication Surfaces

Primary audience: PUBLIC, with REVIEWER/EXPERT/MACHINE drill-down.

These are gated by grounded artifacts and promotion state. Before G4/G5 they can
render:

- proving-ground status;
- missing links;
- method/evidence readiness;
- public transparency about non-conversion.

After grounded promotion exists, they can render:

- signed public decision records;
- decision packets;
- provenance certificates;
- dispute ledgers;
- consultation and response-to-comment records;
- transparency feeds;
- supersession, revocation, and learning history.

The public surface must never be ahead of the runtime envelope.

Every public record must have a machine-readable twin: typed export, replayable
decision packet, provenance refs, rule/schema version, and stable API/export
identity. Without the MACHINE twin, public accountability is only public copy.

## First Hero Surface: Proving-Ground Board

The honest first flagship surface is not a polished recommendation page. It is a
proving-ground board:

```text
13 canonical cases
  x missing capability links
  x adapter admission state
  x search recall/freshness
  x grounded contracts
  x promotion state
  x public/reviewer/expert/machine surface readiness
```

This board turns the system's honesty into the product's main proof. It shows
what is known, what is missing, why a case remains blocked, and what must close
for a case to become grounded-limited or grounded-abstention.

Minimum rows:

- `ua-msme-affordable-loans-2022` pinned case;
- the other 12 canonical proving-ground cases;
- case status (`typed_blocker`, `grounded_limited`, `grounded_abstention`,
  `unchanged_blocker`);
- weakest missing link;
- responsible adapter/slice (open-ended `G1+`, currently including `G6` bounded
  agent and `G7` envelope widening in the Layer 3 master plan);
- surface readiness state;
- public-safe explanation.

This is the first public-sector best-in-class move: an interface that does not
hide non-knowledge.

## Status Grammar

Atlas has two different state systems that must never merge.

### Authority Status

Authority status comes from runtime contracts and the composed status lattice
(D3.7 / S1). Canonical sources include:

- `src/polisyos/core/contracts/candidate_firewall.py`
- `src/polisyos/core/contracts/runtime.py`
- `src/polisyos/core/contracts/capability_resolution.py`
- `src/polisyos/runtime/quality/projection_semantics.py`

The list below is illustrative only. UI may render canonical status values, but
must not become a second source of truth. The lattice is expected to evolve
through G4-G7.

Examples include:

- `candidate_unverified`
- `shadow`
- `grounded_binding`
- `grounded_limited`
- `grounded_abstention`
- `ungrounded_blocked`
- `promotion_blocked`
- `governed_promoted`
- `publishable`
- `contested`
- `revoked`
- `superseded`

UI may render these but not create them.

### Interaction State

Interaction state belongs to components and product flows. Examples include:

- hover;
- focus;
- pressed;
- disabled;
- loading;
- expanded;
- selected;
- invalid;
- empty;
- offline;
- high-contrast;
- reduced-motion.

The Atlas v15 state matrix belongs here. It is valuable precisely because it
models interaction behavior. It must not become a second authority lattice.

### Surface State

Surface state bridges the two but remains derived:

- no producer;
- artifact missing;
- bridge missing;
- consumer missing;
- verification missing;
- surface missing;
- semantic test missing;
- implemented but not orchestrated.

Surface state is the UI vocabulary of the capability reality bar.

## Surface Capability Definition Of Done

A route, panel, widget, component, or public document is not "done" because it
renders. It is done when its maturity claim is true.

| Layer | Required proof |
| --- | --- |
| Typed contract | OpenAPI/runtime-api-client or design-system public API exists and is typed. |
| Producer | Runtime producer, adapter, archive build, or design-system generator emits the artifact. |
| Persistence | Artifact/event/report is stored, queryable, replayable, or intentionally scoped out. |
| Bridge | Runtime, API, client, or package bridge carries the artifact without local reinvention. |
| Consumer | UI route/component consumes the artifact through the allowed boundary. |
| Verification | Unit, contract, browser, visual, accessibility, and/or conformance evidence matches risk. |
| Surface | PUBLIC/REVIEWER/EXPERT/MACHINE projection exists or is explicitly out of scope. |
| Negative test | A laundering/fail-closed case proves the surface cannot overclaim. |
| Semantic test | Content-level adequacy is tested, not only field presence or snapshot shape. |

For accessibility, archive lint is not enough. A stable component or route needs
WCAG 2.2 AA intent, ARIA APG-compatible behavior where custom widgets are used,
browser evidence, keyboard evidence, and manual assistive-technology evidence
for high-risk patterns.

For public and trust routes, the same definition of done includes privacy,
performance, security, and localization: no tracker dependency for accountability
views, security headers, Core Web Vitals budget, stable machine-readable export,
and supported `uk`/`en` copy where the jurisdictional surface requires it.

## Component Maturity Bar

Atlas components graduate only when they carry evidence, not when they look
finished.

| Maturity | Meaning | Surface consequence |
| --- | --- | --- |
| `experimental` | Exploratory; no authority-bearing use. | May appear in prototypes and Storybook only. |
| `beta` | Typed and documented but still under watch. | May support internal REVIEWER/EXPERT flows with fallback. |
| `stable` | Public API, token-only styles, states, keyboard, a11y contract, tests, and owner are complete. | May support runtime, public, docs, and procurement surfaces. |
| `deprecated` | Replacement exists and migration is documented. | New surfaces must not adopt it. |

No component may be `stable` for PolicyOS authority surfaces without:

- public typed props;
- token-only styling;
- native semantics first;
- documented keyboard behavior;
- state matrix;
- story or visual reference;
- accessibility evidence;
- owner and review cadence;
- negative tests for authority-relevant misuse when applicable.

## Navigation And Capability Discovery

Atlas navigation has two layers:

1. **Fixed workspace chrome** - stable product places such as command center,
   runs, evidence, platform, docs. This may be explicit and curated.
2. **Capability discovery** - methods, datasets, sources, legal norms, cases,
   agents, evidence lines, slices, adapters, and grounding opportunities. This
   must be search-driven over typed indexes and ledgers.

Hardcoded capability menus are the frontend version of forbidden enumeration.
They are allowed only as temporary, owner-dated compatibility paths with a
strangle plan.

## Visual And Interaction Character

Atlas should feel like a calm civic evidence cockpit:

- dense but not cramped;
- typographically serious;
- accessible by keyboard and screen reader;
- strong at showing missingness, limitation, and contestability;
- restrained in color and motion;
- explicit about time, authority, provenance, and envelope;
- service-oriented, not brochure-oriented.

The external design anchors are intentionally few:

- GOV.UK: build digital services, not websites; be consistent, not uniform.
- USWDS: accessible, mobile-friendly government services and reusable guidance.
- WCAG 2.2 and WAI-ARIA APG: conformance battery for accessibility.
- NIST AI RMF: trustworthy AI attributes such as validity, transparency,
  explainability, resilience, privacy, and fairness.
- EU AI Act: risk, transparency, and human-oversight posture for AI-assisted
  public-sector use.

These anchors do not override PolicyOS semantics. They supply civic craft and
conformance expectations.

## Data And API Boundaries

Atlas does not compute authority in the browser.

Allowed:

- generated/runtime API clients;
- typed fixtures that are explicitly marked as fixture-only;
- UI derivations for layout, sorting, filtering, and non-authority interaction;
- client-side validation of form shape before submission.

Forbidden:

- hand-written fetch paths for authority-bearing data;
- UI-side recomputation of support, publishability, admissibility, or promotion;
- route-local status enums that duplicate runtime status;
- public copy that upgrades "planned" or "candidate" to "supported";
- charts without source, summary, uncertainty/provenance treatment, and data
  fallback where decision-bearing.
- charts, claims, or public records without explicit time semantics such as
  `as_of`, freshness/staleness, valid window, and replay/rule-version context.

## Atlas v15 Admission Posture

`design/atlas-v15/PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip`
is treated as a subordinate artifact source under the Layer 3 discipline.

It currently contributes:

- design tokens and generated outputs;
- component library and state matrix;
- forms/data-entry;
- dashboard responsive model;
- data visualization grammar;
- theming/accessibility modes;
- governance, i18n, Figma, content-design, security/privacy UX, and
  product-flow patterns;
- archive-level verification reports.

It does not yet prove:

- runtime integration in `policy-engine`;
- browser behavior in the repo app;
- manual assistive-technology behavior;
- public-route performance;
- authority-status compatibility;
- consumer adoption;
- replacement of v4/v7 source-of-truth docs.

Therefore the first Atlas implementation plan must start with DS0 as defined in
the Atlas Design-System Product family above.

DS0 is not bureaucracy. It is the surface equivalent of adapter admission.

DS0 also owns design-plan cleanup. After DS0 classifies v4/v7/v15, the active
plan set must be reconciled through the docs-lifecycle process: at minimum,
`docs/plans/active/FRONTEND_SOTA_PLAN.md` and
`docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md` must be archived, superseded,
or explicitly retained with a dated canonical-owner rationale.

## Amendment Procedure

Changing this surface constitution requires:

1. a link to the Universal Policy Design constitution rule being amended or
   re-derived;
2. a pattern pass against `P01`, `P03`, `P04`, `P05`, `P06`, `P10`, `P13`,
   `P15`, `P25`, and `P26`;
3. an impact note on status grammar, authority boundaries, public surfaces, and
   accessibility/conformance evidence;
4. an owner and date for any exception;
5. a rule-version reference if closed cases or public records depend on the old
   behavior.

If a change would make Atlas easier to ship but less honest, the change is wrong.

## Consequences

Positive:

- Surface work becomes a direct closure mechanism for `surface_missing`
  capability debt.
- v4/v7/v15 drift can be resolved through one admission ledger.
- Public and trust surfaces cannot outrun runtime authority.
- Accessibility, content, and component maturity become evidence-bearing, not
  decorative.
- The proving-ground board gives PolicyOS a distinctive honest product hero.

Tradeoffs:

- Public recommendation surfaces wait for grounded promotion.
- Some attractive v15 components remain unadmitted until evidence exists.
- Designers must distinguish interaction polish from authority semantics.
- Search-driven capability discovery is harder than fixed menus, but fixed menus
  would violate the constitution for open-ended capability.

## Promotion Criteria

This decision can move toward ADR extraction when:

1. DS0 exists and classifies v4/v7/v15 adoption with maturity and supersession.
2. The proving-ground board has an accepted slice plan.
3. A status grammar lint or contract test prevents UI-only authority states.
4. API/client boundary checks prevent hand-written authority fetches.
5. Accessibility evidence requirements are connected to CI/browser/manual
   evidence workflows.
6. `FRONTEND_SOTA_PLAN.md` and `DESIGN_BEST_IN_CLASS_PLAN.md` have a
   docs-lifecycle disposition: archived, superseded, or explicitly retained with
   owner/date/rationale.
7. At least one public/trust route demonstrates privacy, performance, security,
   i18n, and MACHINE-twin obligations appropriate to its audience.
8. At least one surface closes a real `surface_missing` or
   `implemented_but_not_orchestrated` capability link without weakening the
   runtime authority boundary.
