# Native ratchet proxy and issuer decision — proposal

**Disposition:** proposal only; owner adjudication required. Keep current ratchet definitions and row findings unchanged. The final native fullwave remains UNRUN; current root says source_freeze=false and closure_ids=[]. This is not a renewal, baseline change, or closure.

**Intended tracked decision target:** policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/native-gate-proxy-issuer-20261023.md. It is not written here; root reviews any canonical decision.

## E07 row witness

E07 is bound to HEAD b2b57daa56cb68e5ae68565437fe39887421723a and source frame SHA 72425e5979d855f71326765f6a43a5a23517c4227297535c39e0bea18b6e35b1. Its complete denominator has 321 runtime modules and 448 qualifying unit-test files.

| Package | Loose matches / modules | Ratio vs floor | E07 status | Other checks |
| --- | ---: | ---: | --- | --- |
| Foundry | 385 / 539 | 0.7143 vs 0.7176 | floor_regression | Strict 191/539 = 0.3544 vs 0.3531; 28 required property files present |
| IR | 106 / 177 | 0.5989 vs 0.6012 | floor_regression | Strict 26/177 = 0.1469 vs 0.1272; 1 required property file present |
| Runtime | 228 / 321 | 0.7103 vs 0.7152 | floor_regression_exception | Strict 165/321 = 0.5140 vs 0.3892; 1 required property file present |

All three strict ratios exceed their baselines; all required property checks are present. The Runtime exception names team-runtime but expired 2026-06-15. Treat it as an expired record needing an owner decision, not authorization to waive the shortfall. The runtime HTTP cross-module normalization counts for integration coverage only; it does not affect loose mirror arithmetic.

## P38 proxy falsifier

The loose metric credits a source when its stem appears in global unit-test filename stems. It does not inspect imports, assertions, behavior, or ownership. From the complete E07 denominator, an in-memory-only falsifier renames the existing resource summary behavior test to test_resource_binding.py and the existing owned-attempt semantics test to test_owned_attempt_anchor.py. Their corresponding unmatched source modules are resource_binding.py and owned_attempt_anchor.py.

This changes the loose result from 228/321 = 0.7103 to 230/321 = 0.7165, crossing the 0.7152 floor. Source and test bytes stay unchanged; no files were renamed, added, or edited. The two-name shortfall is not evidence of exactly two missing behaviors. Do not add filler tests or rename files to satisfy the count. Add a test only when an owner identifies a specific missing behavior and failure case.

## Proposed G decision

1. Preserve the floors and current findings: Foundry and IR stay recorded as floor regressions; Runtime stays below floor under an expired exception record. Do not shift or renew the old date.
2. Ask each package issuer to choose with complete current input hashes and source-to-behavior evidence: preserve the floor and add only a regression for an independently demonstrated semantic gap; issue a fresh narrow exception only for a real gap that cannot yet be repaired, naming scope, behavior mapping, issuer, expiry, and closure criterion; or re-ratify a measured baseline from the full current source/test denominator, semantic mappings, property evidence, and threshold rationale.
3. Issuers are team-foundry, team-ir, and team-runtime, respectively. Root does not waive package policy.
4. Keep the 34 used shared helpers. E07 finds 34 vs baseline 10, 27 layer-local conftests, one registered cas_store duplicate, zero unused helpers, zero forbidden reverse imports, and zero stale/unregistered duplicate registrations. team-quality may retain the baseline and record growth or re-ratify from full usage evidence; do not delete used helpers.
5. Require issuer evidence before the next source-freeze review. A future move from filename ratios to explicit source-owner/behavior-test mappings requires a separately reviewed contract/tool change with complete-denominator and proxy-falsifier coverage. No migration is part of this packet.

## Separate E06 hold

Root’s coordination instruction and the Q2 peer finding keep E06 on HOLD for “debt removed”: deleting metadata alone does not eliminate active Ruff debt while the Fabric package-wide ignore remains. The retained probe removes only that ignore in an overlay and yields 248 diagnostics on 306 Python inputs. Its input-manifest SHA matches the retained current E08 input manifest exactly. Codes: TC001 133, TC003 100, TC002 5, UP046 5, E501 5.

The Q2 HOLD arrived as a peer message; no durable report path/hash was supplied. The E08 output, manifest, invocation, and receipt are the durable evidence cited here. Fabric/IR source owners continue typing/lint repairs. No blanket renewal is requested and E06 is not closed.

## Pattern pass and evidence limit

P35: complete named denominators support the counts. P38: the filename proxy has a concrete rename-only divergence. P37: baseline or exception authority must come from the named issuer with current evidence. P41: this packet does not transfer E07 status to a later source composition.

Latest coordinator record: HEAD fb4fdc858d5db44bb433b927f0f1b737a26ce306, full frame SHA 8a55b99662712b882077978974e3da95dc4b0c89cb6d01805d64ed08b28bab70, source_freeze=false, closure_ids=[]. No native fullwave was run for this decision packet.
