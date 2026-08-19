---
title: Stage-0 Custody Kernel — Ratification Record (S0-K01–S0-K16)
status: ratified design decision — the sixteen Stage-0 custody invariants
owner: team-architecture
created: 2026-08-02
last_reviewed: 2026-08-02
decision_status: accepted — ratified by the human principal (owner decision, 2026-08-02); this document is the acceptance record for all sixteen statements and for the three amendments applied to them
supersedes: nothing (it ratifies research statements; it does not amend the constitution)
source_kernel: docs/research/policy-operations/consolidation/stage0/stage0-consensus-kernel.md
informs:
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
  - docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - docs/research/policy-operations-and-real-world-runtime-backlog.md
  - docs/system-design-decisions/policy-design-custody-time-model.md
related:
  - docs/system-design-decisions/policyos-identity-and-custody-boundary.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/research/policy-operations/s0-gap-01-minimum-policy-subject-reference-and-semantic-owner-decision.md
authoritative_for: [stage0_kernel_dispositions, custody_invariant_rulings]
may_not_use_for: [capability_claim, production_schema, code_contract, canonical_owner_assignment, authority_grant, legal_compliance_conclusion, implementation_authorization, benchmark_passage]
---

# Stage-0 Custody Kernel — Ratification Record

## 1. What is ratified

All sixteen statements of the Stage-0 Consensus Kernel, `S0-K01`–`S0-K16`, are
**ratified** — thirteen as written, three with the amendments in §4.

The kernel consolidates the ratified identity/custody decision with the independent
audits of the three Stage-0 anchors. It is pinned at:

| Artifact | Commit |
| --- | --- |
| Historical + current repository baseline | `4813b49f6ce14e8debf3aaea096f0967d38d9768` |
| PAO-R0 audit | `258aa740efcfb9e6771bfe52d4fdabc6b74f93a7` |
| PAO-R1 audit | `566840c330e867a15313923c87c20b6863cb053f` |
| OPS-R15 audit | `42a79a655974b37e28a89d31b5f72ffea83927f4` |

**The source documents are preserved byte-identical.** Their `research_only: true`
standing and `may_not_use_for` lists remain exactly as authored. This record is the
*append* that changes their standing — S0-K08 applied to ourselves. A reader who
finds the kernel and wants to know whether it binds is routed here through this
directory's index, not through an edit to the research artifact.

## 2. The evaluation lens (the durable part of this act)

The tension every custody invariant creates is honesty against usefulness: a system
rewarded for refusing finds it always safe to refuse. The constitution already names
that failure — **T6, abstention inertia** (`universal-policy-design-system-vision-and-organizing-rules.md`
§8.2) — and already supplies the instrument that resolves it: the **two-speed
connection** of §2 and §7. The candidate band is cheap and free, because nothing in
it can launder; the authority band is conformance-gated, because everything in it
can.

The test applied to each of the sixteen was therefore one question:

> **Does the statement bind only the authority band, or does it leak into the
> candidate band?** A statement that binds only the authority band is safe to ratify
> strictly. A statement that reaches the candidate band eats capability and must be
> amended before it binds.

Under that lens the kernel passes almost entirely, for one structural reason worth
recording: **it forbids claiming and representing, not acting.** "No authority by
observation" does not forbid observing. "Passage is bounded" does not forbid passing
a benchmark. "Unknown fails closed **for the affected protected action**" does not
forbid working under an unknown jurisdiction — it forbids silently performing a
protected action there.

Two features of the kernel's own construction are the reason it holds this line, and
both are the style to keep:

- every statement carries an explicit **`Does not decide`** field — K06 refuses a
  common persisted header and one gate sequence; K09 forbids reports from freezing
  nine, ten, or thirteen clock fields; K12 refuses a universal evidence envelope;
  K13 forbids the benchmark from freezing our architecture; K16 refuses arbitrary
  efficiency, RPO, and RTO numbers;
- **K11 rejects its own source proposal.** The OPS-R15 audit discarded its twenty-gate
  resume chokepoint as a denial-of-service risk and premature architecture, replacing
  it with "equivalent protection to the extent material to that action". A kernel
  that amends itself downward when strictness stops buying safety is the precedent
  this record adopts for future custody rulings.

**Strictness that creates capability is not a cost.** Three of the most expensive
statements are preconditions of the product, not limits on it: without K10 durable
suspension, refusal-with-a-path is a dead end; without K06 scope closure there is no
multi-jurisdiction, multi-tenant custody and therefore no universality; without K12
reuse is unsafe, and reuse is the economics of the system.

## 3. Dispositions

| ID | Statement | Disposition |
| --- | --- | --- |
| **S0-K01** | Identity above a single case | **Ratified with the name amendment** (§4.1) |
| **S0-K02** | Existing identifiers are not silently repurposed | Ratified as written |
| **S0-K03** | Classify one plane at a time | Ratified as written; carried into `AGENTS.md` beside the four-way test |
| **S0-K04** | External acts remain external | Ratified as written |
| **S0-K05** | No authority by observation, transport, or projection | Ratified as written |
| **S0-K06** | Scope must close before authority use | **Ratified with the application note** (§4.3) |
| **S0-K07** | Projection cannot mint authority | Ratified as written |
| **S0-K08** | Correction appends; history is not rewritten | Ratified as written |
| **S0-K09** | Preserve temporal roles without freezing clocks | Ratified **in pair with** the Custody Time Model (`policy-design-custody-time-model.md`), which is the OPS-R4 answer K09 defers to |
| **S0-K10** | Suspension is durable; wake is only a candidate | Ratified as written |
| **S0-K11** | Protected actions require equivalent, action-specific protection | Ratified as written; cited in §2 as the precedent against over-strictness |
| **S0-K12** | Content equality is not authority validity | Ratified as written; see §6 for why content-keyed caches survive it |
| **S0-K13** | Benchmark observable semantics, not internal architecture | Ratified as written |
| **S0-K14** | Oracle and rebuild must be independent | **Ratified with the scope amendment** (§4.2) |
| **S0-K15** | The benchmark resists memorization and preserves dissent | Ratified as written |
| **S0-K16** | Passage is bounded and carries no authority | Ratified as written |

## 4. The three amendments

### 4.1 K01 — the subject is named by S0-GAP-01, not by `PolicyMatter`

K01 ratifies a **need**: a stable technical reference above a single Policy Design
Case, because case-local identity cannot represent original design, revalidation,
incident review, and correction as separate cases concerning one continuing subject
without reusing `case_id` dishonestly.

The kernel's candidate name is superseded inside the research itself. `S0-GAP-01`
(`accepted_profile_with_owner_role_only`) rejects `PolicyMatter` as unsafe when it
implies a complete external legal or administrative ontology, and replaces it with:

- **the subject** is a **PolicyOS custody subject** — the opaque target to which
  PolicyOS attaches its own justification-custody records across cases; by definition
  not a legal matter, programme, institution, instrument, or administrative case;
- **the minimum reference identity** is **assigning system plus opaque local value**;
  a raw unqualified token is unsafe;
- **tenant or authority-domain qualification** must accompany comparison and
  persistence whenever the assigning system is not proved globally unique and
  cross-tenant safe; the enclosing association may carry it;
- **reference equality proves only** the same token under the same assigning system
  and a compatible qualification context — no legal continuity, no evidence
  applicability, no claim authority, no public currentness, no permission to combine
  records.

K01 is ratified with that substitution. `PolicyMatter` survives only as a historical
term. **No package, issuer, registry, resolver, or schema is ratified** — the current
posture stays adapter-local references plus explicit mappings constrained by the
profile.

### 4.2 K14 — independence binds verification claims, not every rebuild

K14 as written says current-state semantic reconstruction *must* use an independently
owned declarative evaluator. Read outside its context that would demand an independent
evaluator for any state rebuild, including a production system rebuilding its own
reducers — operationally impossible and not what the OPS-R15 audit constrains
(its own `Constrains` field is "any claim that OPS-R15 is executable or passed").

**Ratified scope:** independence is required for **verification claims** — the oracle
side of a benchmark, and any assertion that a result was independently validated. A
same-code rebuild remains legal everywhere and proves exactly what it claims:
**consistency**, never correctness.

### 4.3 K06 — fail-closed binds the protected action, not the computation

K06's wording is already correct: fail-closed attaches to "the affected protected
action", and its `Does not decide` field refuses a common persisted header and one
gate sequence. The risk is the literal reader, who converts it into "compute nothing
under unknown scope" — which would end universality, since entry into any new domain
begins with unknowns, and the adopted search spec is built precisely on acting under
set-valued uncertainty where `unknown` is a first-class honest outcome.

**Application note, binding:**

> Fail-closed binds the **authority band** — protected actions, published claims, and
> custody facts. The **candidate band** may operate under unknown scope as a credal
> state with a **declared** unknown, carrying the unresolved scope forward as a typed
> limitation on future promotion rather than as a prohibition on work. Silently
> substituting a concrete scope for an unknown one is the violation; a declared
> assumption is not.

This is constitution Rule 3 restated at the scope layer — "fail closed **and
downgrade**": the adapter emits the lowest tier it can prove, not zero. `GY-DEF1`
(an absent or unregistered jurisdiction resolving to `UkrainianJurisdiction`) is the
violating form; `assumed: UA, declared default` carried into the record is not.

## 5. Prices accepted

Ratification is not free, and both prices were taken deliberately.

**1. Three registered defects become violations of a ratified rule.** `GY-DEF1`
(K06), `GY-DEF3` (K06/K11), and `GY-DEF4` (K05/K07) move from *found* to *in breach*.
Their honest direction is unchanged and must not be inflated by this reclassification:
`GY-DEF4` is fail-closed-safe (unknown values fall into the obligation branch),
`GY-DEF1` is latent until a config omits or mistypes a code, and `GY-DEF2` — a
tenant-private CAS ref reaching the public export bundle — remains the only one
crossing the public boundary and the only one failing a test on `main` today.
Closing them is now an obligation with owners, not an option.

**2. OPS-R15 scoring is blocked until S0-GAP-02 exists.** Under ratified K14 the
capstone cannot be scored with an oracle that shares admission, reducers, dependency
traversal, or status projection with the implementation. The alternative — scoring
the flagship custody benchmark against a circular oracle — is worse than a late
capstone, because a false pass is unrecoverable.

**So S0-GAP-02 is commissioned in this act**, making the block a refusal *with a
path*: *Independent Custody-Benchmark Oracle and Evaluator Architecture*, specified
in `stage0-additional-research-register.md` and registered as an active task in the
Wave-2 backlog. **Designing** OPS-R15 under K13 and K15 is not blocked and may
proceed now; only passage claims are.

## 6. Non-conflicts settled in advance

**Content-hash-keyed caches survive K12.** A content-keyed world cache (GY plan
§3.5.7 E1, where a hit is by construction identical to a rebuild) reproduces a
**computation**, not an **admissibility**. K12 governs whether an unchanged payload
may still be *used* — source, competence, delegation, licence, freshness,
jurisdiction, and permitted use are re-evaluated downstream against the current
authority context. E12 and the `GY-DI1` debt row already reason this way when they
separate the authority import closure from the source tree. No cache is condemned by
this ratification.

**The constitution is not amended.** No statement conflicts with the twelve
Organizing Rules: K05 and K07 are Rule 8 and the Atlas surface laws; K12 restates
Rule 3 and Rule 9 at the evidence layer; K03 is the operational form of the four-way
test introduced by the §1 identity amendment. Amending the constitution is its
highest-governance act (§12) and is not spent restating what it already binds. This
record enters the `informs` graph instead.

**The identity decision is not amended.** Its §6 row `PolicyMatter identity above a
single case — OWN, now` stands as the historical record of a ratified *need*; the
*name* is closed by S0-GAP-01 and §4.1 above.

## 7. What this does not ratify

Carried unchanged from the kernel's own "Deliberately unresolved" list: a canonical
custody-subject owner, identifier, schema, or relation vocabulary; subject-to-case
cardinality or evidence inheritance across split and merge; a production
`OperationalBoundaryDecision` register; a universal institutional evidence or event
envelope; any shared evidence, boundary, owner, custody, or public status lattice;
clock names or a common field bundle; a twenty-gate resume transaction; a
`WorldRelease` schema or release-state enum; H2's state machine, persistence,
scheduler, or service topology; public correction states, cache fan-out, or long-term
key and archive policy; institutional operator, competence, proof-of-service, remedy,
or payment facts; benchmark passage, numerical efficiency targets, or production
RPO/RTO.

## 8. Impact note (constitution §12 form)

- **Status lattice:** unchanged. No statement creates a status; K05 and K07 constrain
  what may *carry* one. The one-lattice law is untouched.
- **Authority boundaries:** narrowed, not reshaped. K06 requires scope closure before
  authority use and K14 requires independence for verification claims; neither adds
  an authority slot or alters `AuthorityBoundary` composition.
- **Replay behavior:** unchanged. K08 and K09 restate the append-only discipline
  already in force. Rule-version reference: this document's `created` date; work
  closed before 2026-08-02 is interpreted under the prior, unratified standing.
- **Affected plans:** the GY plan (defect reclassification, `depends_on`), the Atlas
  plan (the DS16 producer-binding debt row under K07), and the Wave-2 backlog
  (completion ledger, the OPS-R15 scoring block, S0-GAP-02 registration). No task
  scope changes; the in-flight lanes are untouched.

## 9. Revisit conditions

The kernel's eight falsifiers are adopted as the reopening triggers. This record must
be reopened if any is demonstrated — in particular if a same-code rebuild is shown to
independently detect faults shared by its own reducer and dependency logic (K14), if
an existing identifier can safely be reinterpreted as lifetime identity without
ambiguity or migration (K01/K02), or if historical correction is shown to require
rewriting previously signed bytes rather than appending a semantic successor (K08).

Separately, an accepted subject-reference and owner decision supersedes §4.1, and an
independently reviewed oracle and evaluator package supersedes the block in §5.
