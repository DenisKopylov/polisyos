# Replay Authoring

- Put execution and dead-letter behavior in `backend.py`.
- Put structural and semantic comparisons in `diff.py` and comparator helpers
  in `comparators.py`.
- Put replay report persistence and registry behavior in `verification.py`.
- New first-party imports must use `polisyos.scientist.replay.*`, never
  `polisyos.scientist.replay.backend`.
- Replay changes should keep deterministic behavior explicit: seed handling,
  environment diffs, and verification reason codes need direct tests.
