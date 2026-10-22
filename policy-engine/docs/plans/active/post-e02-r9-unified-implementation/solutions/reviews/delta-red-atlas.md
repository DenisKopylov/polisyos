# R13 Atlas consolidated delta review — 2026-10-22

Bounded review of the three-way fixes in `solutions/preferred-solutions.json`, `solutions/sources.json`, and `solutions/decision-clarifications.md`. This is a contradiction check, not product acceptance or a rerun of the 20-row review. P40 buckets are explicit.

## Residuals

1. **MEDIUM — UI-12 still lists a cloud-only required input.** **P40: same P38 environment/topology status class.** `preferred-solutions.json:4782,4804,4842` now correctly allow local or cloud real PostgreSQL and classify FAIL/ERROR/SKIP/UNRUN separately. However `inputs_to_resolve` at `:4853–4855` still requires “Cloud PostgreSQL DSN/driver.” Counterexample: a commissioned local real-PG profile satisfies all four properties but dispatch/rebind treats absent cloud credentials as a blocker. **Correction:** change the input to “selected local or cloud real-PostgreSQL DSN/driver and isolated-schema permission,” consistent with the selected-profile identity.

2. **MEDIUM — UI-17’s broad preferred-solution gate still conflicts with gross VOI under unknown cost.** **P40: same P10 VOI/cost semantic-separation class.** At `preferred-solutions.json:5014`, the solution says extend the existing acquisition API/projection/client “only after” route, cutoff, facet, **cost basis**, rights and mandate are accepted. At `:5044–5045`, it correctly allows a producer-backed gross VOI value to display while cost is unknown. Counterexample: valid gross VOI exists but no actionable-cost schedule; the detailed step allows the read-only VOI display while the headline gate appears to block the projection itself. **Correction:** scope the `only after` clause to positive-route/action or net-value/price claims. State that read-only gross VOI may project on its own admitted ref/basis with cost explicitly unknown.

3. **HIGH — UI-08’s composition rule leaves posterior mutation unconditionally available for `prediction_error`.** **P40: same P05 authority-activation class; the condition remains missing in the final composition contract.** `preferred-solutions.json:4541,4572,4595` says only `prediction_error` changes the effect posterior and that “only prediction_error changes effect,” while the steps/discriminator correctly say current WP-01/02 prohibits *all* posterior mutation and defer any update until “an actual scoped activation.” The activation packet and competent-principal decision described in `decision-clarifications.md#GYD-09` are not yet a current input. Counterexample: a fresh consumer sees a `prediction_error` and applies the composition rule without resolving an activation; that mutates posterior under the current WP-01/02 prohibition. **Correction:** make `prediction_error` necessary but not sufficient: no cause mutates posterior under current WP-01/02; after a separately approved, versioned WP-01 activation, only the explicitly activated cause/profile may update (and WP-02 routine assimilation needs its own decision). Keep the current test asserting zero mutation until that decision is bound.

## Fixes that now read consistently

- UI-02 separates capability/refusal, PR1a data-only issue with empty signer slot, and PR1b/pilot/signature appointment; its acceptance now names the page-level accessibility, language, and audience checks.
- UI-07 permits isolated contract/projection prep after exact interface agreement while preserving real N13b composition requirements.
- UI-08 explicitly assigns causal/world persistence to O1/O3 and bars UI-created causal history.
- UI-12’s preferred route, outcomes, and fallback now preserve executed property failures as FAIL; the remaining cloud-only input wording is the sole topology inconsistency above.
- UI-14 hashes raw source/package bytes and limits normalization to paths, with a concise parity receipt.
- UI-17’s detailed steps distinguish gross VOI, cost, net value, and action; the remaining broad headline gate is the inconsistency above.
- PostgreSQL citations are pinned to major 18. The Helm citation’s `limits` now explicitly bounds the relied-on property to generic package checksum/signature integrity and requires rebind to the deployed major before command-level use.
