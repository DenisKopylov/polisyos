---
title: PolicyOS Production Backlog
status: active
owner: team-runtime
created: 2026-05-10
---

# PolicyOS Production Backlog

This directory tracks only major work discovered during end-to-end debugging
that would materially improve production runs.

Use it for work that improves at least one of these properties:

- stability
- resilience
- transparency
- predictability
- result quality
- performance

Do not use this backlog for small local fixes, typo fixes, one-line regressions,
or ordinary cleanup. Those should be fixed directly during debugging when the
root cause is clear.

Every backlog item must include:

- evidence from a run, test, log, trace, or artifact;
- production impact;
- likely owning layer;
- proposed durable fix path;
- acceptance gates proving the issue is actually resolved.

Current production-run backlog:

- [Production Run Backlog](production-run-backlog.md)
- [Production Data End-To-End Diagnostic Backlog](production-data-e2e-diagnostic-backlog.md)
- [Cloud Production Debug Ten-Check Backlog](cloud-production-debug-ten-checks-backlog.md)
