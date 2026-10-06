# Internal generator and Pareto checkpoint migration

Owner: team-policyos-runtime. Scope: conditional numerical continuation and indicator
availability in the existing internal receiver. This is not a source-authorization,
production appointment, scientific-quality or deployment decision.

## Generator and native GP

Generator wrapper `bayesian_candidate_generator.v2` retains indexed converted
history rows and the configured metric/direction/split/space/numeric basis.
Native GP checkpoint version4 retains the actual fitted evaluation payloads,
ordered observation IDs, raw X/Y, full-refit prefix, learned transforms and
local RNG. Restore reuses the configured CAS admission reader for transferred
warm and fitted rows, recomputes each ID and numeric row, then reconstructs the
saved model without MLL fitting. Pending due-refit state remains pending.

Generator v1 and native GP versions1–3 are unsupported because their absent
source-row bindings cannot be reconstructed from a saved marker or model bytes.
Keep their original bytes for audit; this change does not authorize deletion.
Recover the exact original source observations and configured target basis,
resolve their full CAS refs through the existing reader, then create a fresh
receiver and permit its ordinary initial fit. This is a new fit, not a claimed
no-refit continuation. When originals are unavailable, preserve an explicit
unavailable continuation rather than manufacturing refs or granting authority.

Configure `configure_transfer(bridge, fingerprint)` before any activity, or use
the existing paired constructor arguments. After admission, persist `get_state()`
and restore with `set_state()` on an equal configured receiver. Keep converted
history prefix rows unchanged when next calling `generate`; the search service
owns raw history, persistence and factory lifecycle. A failed restore must leave
model, wrapper, schedule and local RNG unchanged. Investigate reader/ref/profile
mismatches using original bytes; do not bypass the admission reader.

Defining real consumer checks:

```bash
python -m pytest -q tests/unit/scientist/methods/autotune/test_generator_checkpoint_activation.py tests/unit/scientist/methods/autotune/test_transfer_workflow.py tests/unit/scientist/methods/search/strategies/test_gp_resource_resume.py
```

## Pareto coordinates and quantity

Legacy coordinatev1/assessmentv1 remain readable bounded profiles. Explicit
producer definition versions select coordinatev2; do not infer missing versions.
Display labels are cosmetic. Changed metric/split/direction/unit/version bases
must refuse comparison, including after actual CAS readback.

Empty/unassessed input, invalid reference and unsupported/missing backend now
carry null plus a typed unavailable assessment. Nonempty finite boxes with
exact zero union remain available zero. Indicator consumers check assessment
availability before comparison; replacing null with zero changes the meaning.
There is no hypervolume stopping adapter in the scoped native caller inventory.
Supported exact dimensions are1–4; the optional3/4D profile is locked CPUfloat64
BoTorch0.16.1/Torch2.10.0 dominated partitioning. Other profiles are unavailable.

Positive contributing boxes that compute to zero in float64 now carry null and
`nonzero_derived_hypervolume_underflow`. This distinguishes loss of a positive
quantity from genuine boundary/outside-reference zero. The supported profile
uses float64 arithmetic and does not promise arbitrary precision or recover
every value lost by intermediate rounding. Non-finite derived volume retains
its existing unavailable diagnostic. Front membership and original input
coverage are independent of either quantity limitation.

The native MO reference reader also checks the finite representability of its
derived axis spans and reference values before model construction/fitting.
Single and batch suggestion raise `ValueError("invalid_reference_point")` for
this unsupported arithmetic profile; generic random fallback cannot turn it into
an apparently successful optimization. The indicator API carries the same
refusal as null plus an unavailable assessment. Keep original inputs and choose
an independently justified supported coordinate/reference basis; this is not
permission to rescale units or change the reference policy silently.
The refusal includes an overflowing intermediate axis span even when an exact
real-number rearrangement could produce a finite final reference. It declares
the supported float64 arithmetic boundary, not mathematical impossibility.

Paired axis reindexing moves policies and their definition versions together.
Persisted coordinate IDs, values and reference keys remain bound to their full
metric/split/direction/unit/version tuple. Labels are cosmetic; an unpaired
definition version or stale ID refuses comparison/readback.
Every missing/non-finite omission ID also belongs to that current schema, once
and with its original input index. This applies to partial fronts and wholly
unassessed inputs. Stale or duplicate omission IDs and omitted rows without a
bound coordinate schema refuse at the canonical typed artifact reader. A paired
coordinate rename/reindex must update omissions along with values and reference
keys; retaining old omission IDs does not describe the new coordinate basis.

Direct typed `ParetoFront`/`HypervolumeResult` CAS serialization must explicitly
use `CanonSpec(forbid_floats=False, exclude_none=False)`. The default direct-model
profile drops required null fields and does not establish safe readback. The
ordinary registry JSON writer and the reviewed A frontier-report metadata path
preserve mapping nulls; their actual update, projection, persistence and fresh
report reader are checked separately. This does not appoint an external
candidate-universe provider or supply institutional metric-source authority.

```bash
python -m pytest -q tests/unit/scientist/methods/autotune/test_hypervolume_profile.py tests/unit/scientist/methods/search/strategies/test_multiobjective_hypervolume_admission.py tests/unit/scientist/methods/search/test_frontier_quantity_readback.py
python -m pytest -q tests/unit/scientist/methods/autotune/test_hypervolume_representability.py tests/unit/scientist/methods/search/strategies/test_mo_reference_representability.py
python -m pytest -q tests/unit/scientist/methods/search/test_registry_quantity_projection.py
```

The external A producer/exporter and eligible/feasible/unknown denominator packet
remain separate owner dependencies. These fixtures and quantities do not supply
that missing basis or establish institutional metric units.
