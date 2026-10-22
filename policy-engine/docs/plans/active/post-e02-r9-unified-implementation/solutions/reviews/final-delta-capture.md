# Final narrow capture delta

This note checks only the two previously reported residuals in `solutions/preferred-solutions.json`: CAP-01 authorization inputs and CAP-02 pre-materialization rights enforcement. No other rows or classes were reviewed. No implementation, tests, imports, builds, installs, or protected data were involved.

## CAP-01 — authorization inputs

**Resolved in the row.** `CAP-01.inputs_to_resolve[1]` now states the native-verifier alternative explicitly: the selected provider/source/use contract authorizes the exact query **OR** applicable accountable custodian permission. It separately preserves provider logging, retention, training, region, and recipient constraints when those apply, and says no unrelated custodian grant is required for every lawful public/owned nonsensitive query. This agrees with `preferred_solution` and `acceptance_discriminators[2]`; no conjunctive grant residual remains in this field.

## CAP-02 — authorization before raw materialization

**Resolved in the row.** `CAP-02.preferred_solution` limits an immutable body witness to profiles permitting raw retention and routes other profiles to CAP-03's lawful query/result-receipt boundary. `implementation_steps[1]` obtains LIF-05/native source-use permission for the actual placement before writing body, temporary, log, cache, or other sink data; it explicitly bars forbidden raw staging in query-only mode and says later CAP-03 admission cannot authorize capture retroactively. `acceptance_discriminators[4]` checks query-only canaries at capture time and removes the pre-materialization permission to distinguish the gate. The prior CAP-02/CAP-03 timing conflict is addressed in these two rows.

## Limit

This is a bounded review of those two documentary predicates, not verification that any producer or rights gate is implemented.
