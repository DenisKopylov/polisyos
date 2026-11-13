# Foundry Uncertainty Tests

This directory tests uncertainty propagation, dispatcher routing, numerical
admission, aggregation and sampling behavior. The implementation owner is
[`foundry/uncertainty`](../../../../src/polisyos/foundry/uncertainty).

Start with `test_dispatcher_routing.py` for method selection,
`test_joint_law_admission.py` for shared-law admission, and
`test_artifact_aware_aggregation.py` for persisted input and aggregation checks.
Delta, Monte Carlo and quasi-Monte Carlo tests cover their separate numerical
profiles. Keep sample counts, standard errors and stopping conditions distinct;
one matching sample does not establish distributional equivalence.

Run selected cases from `policy-engine/` using the existing environment, for
example `.venv/bin/python -B -m pytest -q
tests/unit/foundry/uncertainty/test_dispatcher_routing.py`. Select the numerical
backend and thread/resource profile required by the affected behavior rather
than launching all sampling tests for a documentation change.
