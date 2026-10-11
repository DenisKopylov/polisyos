# B190 metric source and unit binding: decision for G

Status: narrow architecture decision requested; not a formal finding adjudication or closure.

## Observed boundary

The current `Metrics` DTO carries `values: dict[str, float | int | str]` and report-level notes. The native Foundry execution producer emits `step_latency_ms` from elapsed wall-clock time in milliseconds (`foundry/execute/_internal/graph/__init__.py`), but the metric entry carries no per-key source or unit binding. Separately, the actual execute-backed identifiability response basis resolves a requested global state slot from the selected source simulation, parameter override, registry, and CAS replay; it stores parameter/moment units and exact source identities, but it is expressly local and `gate_eligible: false`. Its `response_slots` key is caller-selected. Therefore a same-string join is not a producer/consumer binding.

The executable falsifier in `tests/unit/foundry/calibration/test_identifiability_response_basis.py::test_metric_name_collision_does_not_bind_counter_to_response_unit` uses the real native execution and response-basis producers. It chooses `step_latency_ms` as the response key for `government.balance`; the response basis resolves USD for that state path while the native graph metric is elapsed milliseconds. The test requires the candidate basis to remain non-gating. A consumer that turns this name collision into a resolved relationship would fail the falsifier. `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py` separately exercises the real propagation node: valid raw coefficients still produce candidate outputs, while malformed present maps return a typed failure without writing propagation artifacts.

## Options

1. **Reuse without a new binding.** Keep caller maps as explicitly limited candidate calculations; use the existing response-basis API only for its local Jacobian diagnostic. This is the safe immediate behavior and preserves current consumers. It cannot support a resolved B190 response claim.
2. **Extend the existing metric producer contract (recommended if G wants this capability).** Add a versioned, typed per-metric observation identity from the actual Foundry producer: metric definition/id, exact source artifact/profile, unit reference, observation-time role, producer execution identity, and replay inputs. A consumer can then reconcile the selected output metric with an execute-backed response basis over the same source, parameter axis, unit dimensions, and replay identity. Producer labels remain producer-supplied evidence; any authority gate must independently recompute or reconcile the binding and keep absent/legacy units `not_established`.
3. **Consolidate around an existing typed owner.** The existing response-basis carrier already owns execute-backed local state Jacobians and unit registry resolution. It is a suitable source for candidate diagnostics, but it does not own metric IDs or Foundry metric units. Reuse it as the numerical component only after a typed metric-to-response bridge exists; do not merge arbitrary metric names into `response_slots`. The current per-example `MetricObservationBundle` has a different contract and is not a compatible drop-in.
4. **Build a new producer/bridge only if the owner review finds no compatible extension point.** This costs a new schema, producer, reader, migration, and generated public surface; it is not justified before option 2 is evaluated against the existing `Metrics` owner.

## Impacts and migration

Keep `Metrics` schema 0.1.0 readable and byte-stable. Legacy values with no typed source/unit evidence stay `not_established`; do not infer units from names, `notes`, report metadata, caller coefficients, or a registry slot alias. A versioned extension needs dual-read migration, generated SDK/API updates, a fresh-CAS consumer, and negative controls for missing, malformed, wrong-profile, cross-source, and same-key/different-unit inputs. Historical candidate reports remain candidates; no retroactive authority or closure follows from the new producer.

## Status, authority, and time

The existing raw-map candidate calculation may be retained with `sensitivity_mapping=consumer_asserted`, source `caller_parameters`, and `gate_eligible=false`. A future typed metric observation is still not independently verified authority. The consumer must bind content and selected manifest profile, reconcile producer and replay lineage, verify units against the registered definition, and preserve observation/valid/transaction times distinctly. No legal rule, institutional issuer, calibration law, or production currentness is created by this packet.

## Decision requested and next check

G should decide whether the canonical `Metrics` producer can be extended with a versioned per-metric source/unit observation carrier, or whether the local response basis remains diagnostic-only and B190 stays limited. The falsifier is executable at the command below; after a decision, the next source check is an actual producer→CAS→fresh-reader integration that binds one matching metric/unit/profile and refuses (a) `step_latency_ms` joined to a USD balance response, (b) same metric ID under a different producer/source ref, (c) missing/malformed unit or source identity, and (d) changed selected manifest profile. Any positive must be derived from persisted source and replay bytes, not an inline caller assertion.

```bash
cd policy-engine
.venv/bin/python -m pytest -q tests/unit/foundry/calibration/test_identifiability_response_basis.py::test_metric_name_collision_does_not_bind_counter_to_response_unit
```

## Pattern pass

Relevant patterns: P01/P02 (producer-to-reader bridge), P05/P10/P14 (authority and evidence adequacy), P29/P32/P37/P38 (actual behavior, source-bound inputs, and no name-only proxy), P40 (one general metric-binding mechanism rather than per-key fixes). Existing defect: `Metrics.values` can be caller-interpreted by key alone; the response-basis key is also caller-selectable. Target pattern: candidate-only reuse now; if ratified, one typed producer source/unit observation plus one fresh-reader reconciliation. Current status: `verification_missing` for resolved metric response; `implemented_but_not_orchestrated` for joining the existing local response-basis producer to the actual metrics consumer; candidate-only propagation is explicitly limited. Acceptance signal for any future positive: real producer bytes, source/profile/unit identity, replayed Jacobian, fresh reader, and same-key/different-unit plus changed-source negatives.
