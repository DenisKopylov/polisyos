# Scientist Feedback

Feedback owns decision monitoring, observed-actual comparisons, and reissue
materialization for Scientist decision packets.

Use this hub for:

- monitoring-contract and monitoring-report helpers;
- parameter override bundles derived from calibration feedback;
- compare/reissue helpers that react to post-decision evidence.

Do not add new modules under `polisyos.scientist.feedback.utils`. The retired legacy module
is a Phase 4.4 compatibility shim for `polisyos.scientist.feedback.utils` and
sunsets on 2026-11-30.

Tests live under `tests/unit/scientist/feedback`.
