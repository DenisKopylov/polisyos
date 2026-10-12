# Runtime HTTP Unit Tests

This subtree covers HTTP services, contracts, route helpers, and runtime control
plane behavior.

Run-bound predictive-calibration request validation and route delegation are covered in `test_runs_api.py`. `test_predictive_calibration_post_event_reopen_get_and_exact_intent_retry` in `test_control_service_di.py` exercises a controlled real N5 run, authenticated POST, `ForecastOwner`, S10, durable association event, fresh-app GET, exact selected model/policy profiles, changed-body conflict, and event-payload tamper refusal. It also holds the producer while a second app/store instance sharing the same SQLite database submits the same intent; the follower receives the typed in-progress conflict and the owner runs once. A persisted pre-R229 event is exercised through the legacy-scope refusal, which avoids replaying an event whose principal was never recorded. These composed source checks are authored but execution remains UNRUN pending the parent-controlled API test slot. The separate store tests include a SQLite process race, event/result transaction rollback, and an abandoned-pending no-takeover case; they are also UNRUN. PostgreSQL concurrency is unverified. Owner, bridge, and S10 tests remain supporting checks, not substitutes for the composed route.

