# Exploratory coordinate order for native search

The supported `exploratory_coordinate_order.v1` profile assigns existing Sobol/GP
coordinates to physical parameters in the complete recomputed DOE ranking order.
It changes the proposal stream when explicitly activated; it does not estimate
optimization advantage, authorize effects, or establish a population input law.

Use the existing `SensitivityBridge` producer with full continuous non-log bounds,
explicit units, uniform distributions, an actual evaluator, a replay seed and an
explicit experiment budget. Persist through the configured store. For Sobol,
`input_law="independent"` describes the synthetic parameter experiment; the
population law remains `not_established`.

Build the native autotune `SearchSpace` from the same full bounds/unit/distribution
records. Resolve the returned full `analysis_ref` through
`SensitivityAwareCandidateGenerator.from_artifact(base_generator, store, ref)`
before transfer, warm observations or generation. It uses the canonical verified
CAS snapshot and existing E reader to recompute the analysis. It checks the entire
parameter basis against native bounds and activates the existing generator's
ordering port. Generators without that explicit port remain `metadata_only`.

For the existing explicit composition, replace `SearchLoopSpec.candidate_generator`
with that resolved adapter and use `SearchLoopRunner`. The native runtime companion
adds owner-configured spec metadata activation:
`analysis_ref`, `analysis_order_profile="exploratory_coordinate_order.v1"`, and
`analysis_purpose="exploratory"`. That companion must be integrated before claiming
this metadata entry point or its default typed-codec projection is available.

The native generator checkpoint retains the exact full ref, design/analysis IDs,
complete parameter basis, ordering policy and space fingerprint. Restore requires
fresh composition with the same original receipt and reader; the reader rechecks
CAS before proposal and numerical restore. Exact same-profile revalidation is
idempotent. Changing ref, units, distribution, bounds or order after activity
refuses. Configure transfer after ordering with an owner-supplied target basis for
that resulting ordered space; no target basis is inferred from a warm row.

Old metadata-only generator checkpoints do not establish this ordering policy.
Keep their original bytes, resume their old unconfigured stream when appropriate,
or create a fresh explicitly configured experiment. Do not relabel old checkpoints
or overwrite their source history. Missing/unsupported backend means `UNRUN`;
missing or malformed source/configuration is refusal, not a fallback proposal.

This profile supports complete finite Morris/Sobol analyses of continuous, non-log,
uniform coordinates with known declared units. Other domain mappings require an
explicit supported consumer profile rather than silent projection. Institutionally
correct units, evaluator provenance and production input-law appointments remain
external supplier/G decisions.
