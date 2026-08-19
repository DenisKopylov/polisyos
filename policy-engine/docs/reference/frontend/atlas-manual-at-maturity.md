# Atlas Manual AT Maturity Prerequisite

Freshness: 2026-08-11
Owner: `team-frontend`
Contract: `apps/runtime-dashboard/src/test/evidence/atlasManualAtMaturity.ts`
Evidence envelope: `polisyos.atlas.evidence-receipt@1.0.0`

## Owner and scope

The Atlas surface constitution owns the normative component maturity bar. Its
definition of done requires manual assistive-technology evidence for high-risk
stable components. The shared maturity vocabulary comes from
`surface-readiness-ledger.schema.json#/$defs/componentMaturity`; C09 imports
that owner rather than declaring another maturity enum.

`adoption-ledger.schema.json` is the only Atlas schema with a structural
`stable` evidence condition, but the adoption ledger is authoritative for DS2
adoption and migration—not production readiness. The actual adoption ledger is
also content-bound by the contended frontend disposition register. C09 changes
neither owner: the behavioral prerequisite consumes the actual component row
shape (`id`, `kind`, `maturity`, and `evidence_refs`) without re-anchoring the
governed register. The focused witness starts from the real
`component-badge` row, which is currently `experimental`, and constructs a
future owner-shaped `stable` input because the complete ledger has no current
`stable` row.

The consumer decides whether the manual-AT prerequisite is not required or
must remain blocked. It cannot report satisfaction until C08/C10 supply the
missing integrity and reconciliation predicates, and it never grants overall
`stable`. Browser, keyboard, persistence, reconciliation, and the rest of the
constitutional maturity bar remain separate gates.

## Reused evidence contract

Manual AT uses C07's existing receipt and verification-payload envelope. The
rule-owned payload `details` are strict. C09 also imports C07's exported
five-value P37 predicate-provenance schema instead of copying that
load-bearing vocabulary. The details contain:

- protocol identity `polisyos.atlas.manual-at-review@1.0.0`;
- a named human assistive-technology reviewer;
- a versioned task/AT basis reference with its frozen predicate-provenance
  classification;
- a session ID, unique AT identities and capabilities, and unique task
  outcomes;
- an observation state with a nullable task count;
- the complete C07 denied-use set and authority only for
  `manual_at_observation`; and
- a protocol-owned `expires_at` instant.

Known zero, unknown, and missing are different facts. `observed` carries an
integer count equal to the complete task-result set, including a valid known
zero. `unknown` carries `null` and no task claims. Missing means no receipt was
provided at all.

Expiry is not storage retention. C07's 365 days controls CAS cleanup; C09
compares `expires_at` with an injected `evaluated_at`, rejects evaluation before
the C07 `verified_at` instant, and requires expiry to follow verification. No
90/180/365-day freshness threshold is invented here. The evidence producer
must issue an explicit cutoff, and later governance may own the duration rule.

## Fail-closed evaluation

For a `stable` owner row, the consumer requires the row to cite the exact
manual-AT receipt artifact identity, parses the C07 receipt, checks the resolved
payload's artifact and semantic binding, requires the manual-AT rule identity,
matches the exact component/state, parses strict rule details, evaluates P37
predicate provenance, then evaluates time roles, observation results, and the
complete declared task/AT basis.

| Condition | Result code |
| --- | --- |
| no bundle | `manual_at_evidence_absent` |
| owner row does not cite the receipt | `manual_at_owner_reference_absent` |
| evaluation predates verification | `manual_at_evidence_not_yet_valid` |
| expiry does not follow verification | `manual_at_expiry_invalid` |
| expired cutoff | `manual_at_evidence_expired` |
| authority exceeds observation-only bound | `manual_at_authority_bound_exceeded` |
| another component/state or a surface receipt | `manual_at_subject_mismatch` |
| unknown observation | `manual_at_evidence_unknown` |
| known zero observations | `manual_at_zero_observations` |
| asserted/supplied/unestablished gate predicate | `manual_at_predicate_not_admissible` |
| task/AT basis is not independently established | `manual_at_basis_not_established` |
| observed task/capability set differs from the declared basis | `manual_at_basis_mismatch` |
| unresolved or semantically drifted C07 payload | `manual_at_payload_unverified` |
| shaped artifacts lack C08 CAS integrity proof | `manual_at_integrity_not_established` |

Only `recomputed` or `independently_reconciled` predicate provenance can carry
an authority-grade prerequisite. A raw human observation labelled
`institutionally_supplied` remains admissible evidence to record, but cannot by
itself carry `stable`. A syntactically valid basis reference remains only a
declaration until C10 resolves and reconciles it.

C09 deliberately has no `satisfied` result. Even a perfectly shaped,
semantically bound in-memory bundle returns
`manual_at_integrity_not_established`: C07's binder explicitly does not prove
CAS existence or digest integrity, and C08 has not supplied that bridge. Every
result sets `grants_stable: false`.

## Current capability state

C09 is `contract_only`. The focused fail-closed consumer exists, but C08 has not
persisted, resolved, or integrity-verified a real C07 receipt, no runner or
reviewer workflow produces this protocol, and C10 has not reconciled either the
instrument basis or the rest of the maturity bar. The missing links remain `producer_missing`,
`artifact_missing`, `bridge_missing`, actual-evidence `verification_missing`,
and `surface_missing`.

Focused non-browser verification:

```bash
cd apps/runtime-dashboard
corepack pnpm exec vitest run src/test/evidence/atlasManualAtMaturity.test.ts --maxWorkers=2 --reporter=default
```
