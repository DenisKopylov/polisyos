# Runtime HTTP Unit Tests

This subtree covers HTTP services, contracts, route helpers, and runtime control
plane behavior.

Run-bound predictive-calibration request validation and route delegation are covered in
`test_runs_api.py`. The composed test `test_predictive_calibration_post_event_reopen_get_and_exact_intent_retry`
in `test_control_service_di.py` exercises a controlled real N5 run, authenticated default-app POST,
`ForecastOwner`, S10, a durable association event, fresh-default-app GET, exact selected
model/policy profiles, changed-body conflict, and event-payload tamper refusal. It also holds the
producer while a second app/store instance sharing the same SQLite database submits the same
intent; the follower receives the typed in-progress conflict and the owner runs once.

The paired run-bound case keeps the forecast and predictive intervals fixed while changing only
the held-out observations, then checks distinct owner/S10 empirical grades in a fresh default-app
read. Both associations remain limited and predictive-only, with causal/counterfactual authority
not established. A persisted pre-R229 event is exercised through the legacy-scope refusal, which
avoids replaying an event whose principal was never recorded.

The POST route uses the same server-derived, current root/CAS candidate-simulation projection as
the run GET view before the service checks candidate and model references. A client-supplied N4
reference remains untrusted: it must match a resolved selected reference in that current projection.
The composed test uses a profileless-reference refusal and a model-only negative with the valid
GET-derived N5 reference, then exercises the successful producer and fresh-read path.

Execution state is tracked by the parent-controlled raw receipts; this overview does not claim a
pass/fail result. Separate store tests include a SQLite process race, event/result transaction
rollback, and an abandoned-pending no-takeover case. PostgreSQL concurrency is unverified. Owner,
bridge, and S10 tests remain supporting checks, not substitutes for the composed route.
