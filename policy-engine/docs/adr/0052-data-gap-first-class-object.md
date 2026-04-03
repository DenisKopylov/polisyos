# ADR-0052: DataGap as a First-Class Object

## Status
Proposed

## Date
2026-02-28

## Context
When a variable needed for transportability adjustment (e.g., P*(Z) in the target context)
is missing from available datasets, the transport analysis silently degrades: confidence
drops, proxies are substituted, or the path is marked infeasible. Without explicit tracking
of data gaps, users cannot distinguish between "transport is genuinely infeasible" and
"transport would be feasible if we had this specific data."

## Decision
1. `DataGap` is a first-class Pydantic model in the IR, included in every
   `TransportabilityResult`.
2. Each `DataGap` records: `variable` (canonical name), `context` (target context ID),
   `available_proxies` (list of proxy options with their reliability scores), and
   `impact_on_confidence` (estimated confidence loss due to the gap).
3. The `TransportabilityResult.data_gaps` field is a list of all identified gaps, ordered by
   impact (highest confidence loss first).
4. Data gaps are surfaced in the governance report and the decision packet, enabling
   stakeholders to prioritize data collection efforts.
5. A transport result with data gaps but no HARD legal blocks is marked `feasible = True` with
   `confidence` reduced proportionally to the gap impact.

## Consequences
### Positive
- Transforms silent degradation into explicit, actionable information.
- Enables data collection prioritization: stakeholders can see exactly which data would most
  improve transport confidence.
- Distinguishes between infeasibility (HARD legal block) and data insufficiency (gaps), which
  require different responses.

### Negative
- Adds complexity to the `TransportabilityResult` schema and every consumer that processes it.
- Impact estimation is approximate and depends on the quality of the proxy reliability model
  (ADR-0050).
- Large numbers of data gaps in under-studied contexts may produce verbose reports that
  overwhelm stakeholders.
