# Method Requirement

- Last updated: 2026-05-23

`polisyos.method_requirement` owns the W7.C compiler that turns claim-bound
method preconditions into typed `MethodValidityRequirementSpec` artifacts.

The compiler is intentionally not a method selector. Foundry and the IR
analytics bridge consume the emitted requirements and remain responsible for
selection, rejection, runtime assumption gates, method output refs,
uncertainty envelopes, limitations, and simulation lineage.
