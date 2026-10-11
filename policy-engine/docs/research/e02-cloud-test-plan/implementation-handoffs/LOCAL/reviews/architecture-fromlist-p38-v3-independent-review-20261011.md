# Independent review: P38 from-list classifier v3

**Verdict: GO for applying this exact candidate delta and including it in the next composed source freeze.** This is a bounded code-review verdict, not a native-gate pass, source-graph receipt, formal finding closure, or G acceptance.

## Identity and boundary

- Candidate HEAD: `43c9d3d64baaf5932852ab2e676b12bbd2c5e14f`.
- Candidate tree: `bb17b9687d94f00c6ff838c535c8f06e4168850b`.
- Virtual patch: `implementation-handoffs/LOCAL/raw/architecture-fromlist-p38-v3-20261011/architecture-fromlist-p38-v3.patch`.
- Patch SHA-256: `43b70cafe2bb13ad73e61e3be2d5ebc05cb63885fb1a6016b451eb70398b96c5`.
- Manifest SHA-256: `e5c1f351f2191220809a45bd1a2d15d904dd870f90a7d5574fe5a16a273eb7d5`.
- Scope is exactly three virtual source paths: `guardrails.py`, its mirrored architecture tests, and the architecture README. The working-tree files still match the manifest's preimage SHA-256 values. Applying the patch was not part of this review.

## Property and P40 bucket

**Property:** a supported parent import must not hide a from-list child-module import that crosses the declared package boundary. A child can be treated as a facade attribute only when the facade has a complete statically resolved `__all__` containing the name and source establishes one unique direct module-level binding.

**P40:** same P38 class, one level deeper. V2 had the right broad mechanism but accepted a direct binding without requiring membership in the complete resolved export manifest. V3 adds that missing conjunct and tests the whole bounded predicate. Further cases within the declared supported grammar are examples for future review, not a reason for another repair round; an actual escape from that grammar requires widening to the property or recording a bounded residual with a falsifier.

## Independent evidence

1. `git apply --check --verbose` passed for all three patch paths. The overlay's three SHA-256 values equal the manifest after-hashes; the candidate files equal its before-hashes.
2. From `policy-engine/`, I reran `python3 docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/architecture-fromlist-p38-v3-20261011/run_targeted_pytest.py`. Result: 9 selected fixture tests passed in 0.882 seconds, exit 0. The tests exercise supported future-import directives and aliasing; child fallback and direct import; positive complete-export/direct-binding behavior; an unlisted-but-bound name and its corrected diagnostic; ambiguous and lazy-only bindings; a marker-preserving removal probe; and relative/dynamic-star candidates.
3. The runner's actual-source probe returned `not_established` with `_UnresolvedExportDeclarationError` at `src/polisyos/fabric/__init__.py:import importlib`. This is the expected honest boundary: the resolver refuses executable import-time machinery and does not emit those Fabric candidates into a baseline. It does not establish a positive resolution for the production Fabric facade.
4. As a focused language check, executing `from __future__ import annotations` bound `annotations`, and the aliased form bound `compiler_flag`; this matches the source binding model used by the fixture. The classifier limits accepted directives to named interpreter-known features in the legal module prefix and does not execute facade source.

The mechanism now distinguishes a binding omitted from `__all__` (`bound_but_unlisted`) from a declared name without a proven unique binding (`declared_binding_unproven`). Unknown export manifests and dynamic/star cases remain non-baselinable. A removal probe preserves the `__all__` marker but removes the direct binding and makes the gate fail, satisfying the P29 behavioral falsifier for this bounded property.

## Limits and next check

The full source graph, current native architecture/repository gates, generated freshness, and composed candidate replay remain **UNRUN**. The targeted fixtures establish the v3 predicate but do not settle every repository consumer or authorize a baseline refresh. Preserve the actual Fabric candidates as `not_established` until its import-time export machinery is either statically provable under a reviewed extension or refactored to expose a pure complete manifest. Next check is one source-bound full graph/native replay after all blocking companion deltas are frozen; inspect the resulting candidate edges and do not promote unresolved edges into the baseline.

`closure_ids` remain empty. No source, generated baseline, contract, index, or history was changed for this review.
