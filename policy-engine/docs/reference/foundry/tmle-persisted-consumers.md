# Persisted TMLE confidence and value consumers

The registered cross-sectional TMLE method can emit a numerically successful
regular-IID report with an EIF interval. This is a candidate estimate. Its
`SUCCESS`, interval, execution evidence, and artifact identity do not establish
causal identification or production value eligibility.

The regression fixture executes one native `TMLEEstimator` MethodJob. It retains
the observation artifact, MethodJob result, execution evidence, typed causal
report, and uncertainty envelope in the existing filesystem CAS. The report's
manifest binds the native result; the result binds the observation artifact.
Every reader opens a fresh CAS handle in a separate Python process and compares
the typed report to that same persisted MethodJob result before invoking both
consumers. It does not construct a substitute TMLE report. The IR artifact
writer's existing canonical float normalization applies to the separately
persisted envelope; adversarial copies preserve its exact persisted point and
interval, while the native report retains the original numerical values.

The fixture uses 600 bounded binary observations, two configured folds, one
repeat, logistic propensity, and the existing linear outcome backend. This is
the minimum selected fixture for consumer composition. It does not repeat the
numerical coverage, cache, default-fold, or aggregate resource experiments.

## Confidence intake

`ConfidencePass.validate` retains the causal-purpose BLOCKER independently of
the envelope's offered source label and gate flag. The test preserves the native
point, interval, method and `SUCCESS` while adversarially relabeling only its
envelope as an eligible ensemble result. It challenges both top-level and
artifact-index causal refs with minimum eligible ratios zero and one.

The sibling SimulationResult is absent, healthy, unresolved in CAS, malformed
JSON in CAS, or a different model in CAS. The supplied simulation ref uses each
supported indexed, top-level typed, and top-level string address. Artifact
loading failures retain the causal BLOCKER and add the existing degraded-path
warning. A healthy sibling is a successful CAS-load control; it is not positive
causal identification. The unmodified native envelope is challenged separately.

The held context is important: ratio zero may suppress a statistical ratio
issue, but it must not suppress the causal-role issue. Changing a source label
while preserving the causal input role does not change the authority purpose.

## Value projection

The same fresh reader offers the same native report to the existing
`project_method_value_evidence` consumer through TMLE's real method signature
and selected `report` slot. That slot has no declared native value projection
contract. The actual result is the typed
`method_output_contract_unresolved` refusal. This occurs before the downstream
envelope-eligibility predicate. It proves neither a positive value projection
nor that downstream predicate's behavior. The reader leaves the report's
numerical success and interval intact after the refusal.

## Required owner inputs for a positive authority scenario

The current report converter has no accepted causal-identification admission
input; the current ConfidencePass likewise has no accepted verifier-backed
positive branch for that role. Genuine positive identification remains UNRUN.
The Runtime/PDC `EvaluationExecutionContext`, fresh admission challenge,
verifier port, and current revision can admit operational evaluation under their
existing contract. That operational receipt is not statistical identification
and is not a value projection capability.

At the inspected G9a/ROOT072 Runtime intake, the maintained default authority
and appointment resolvers return unresolved/unappointed, the verifier registry
returns no supplier, and the attempt supplies no basis/pack/facet denominator
or evidence. Resolver-injected unit fixtures exercise verifier mechanics but
cannot supply a genuinely institutionally admitted production context.

The minimal Runtime/IR/C owner packet must identify the existing accepted
identification issuer and verifier API, its exact artifact and consumer input,
and how it content-binds the current observation source, graph, estimand,
treatment contrast, population/target and revision. The supplier must provide
an actual producer-issued positive receipt that the consumer challenges freshly,
plus missing, fake, stale, and source/graph/target-swapped refusals. A string,
UUID, producer marker, or self-issued seal cannot supply this packet. Adding a
parallel authority subsystem is outside this fixture.

The native value-contract owner must separately supply the declared slot
contract, canonical projection owner and estimand binding before a positive
value projection can be exercised. Operational evaluation admission cannot
replace these contracts. B56 additionally needs the actual admitted common
study, competing workload, models, seeds/repeats and budget context. A standalone
MethodJob and an execution-context-missing pool attempt do not close that input.

## Reproduce the bounded consumer checks

Run from `policy-engine/` with the candidate's `src:tools` on `PYTHONPATH`:

```sh
python -m pytest -o addopts='' -q -s \
  tests/unit/scientist/governance/test_tmle_persisted_evidence_consumers.py
```

The source-bound handoff records the actual interpreter, complete output,
immutable source/tree, negative replay and independent review. Backend markers
remain unchanged; this fixture uses native NumPy/scikit-learn and does not treat
Python 3.14 DoWhy/EconML exclusions as a backend witness.
