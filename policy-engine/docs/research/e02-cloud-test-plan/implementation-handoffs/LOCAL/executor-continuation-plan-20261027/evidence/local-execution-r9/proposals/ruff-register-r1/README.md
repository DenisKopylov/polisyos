# P38 Ruff candidate-context register proposal

Uncomposed eight-line addition to the existing P38 Ruff topology instance. The
property is that the intended source bytes are actually checked against the
applicable product configuration and logical identity in the relevant composed
physical topology. Exit zero is a proxy: an ignored scratch path or zero selected
files can produce it without that check. This is the existing P38 class, related
to P29/P35, not a new pattern or a new repository-wide gate. The amendment
requires no product change, blanket test mandate, or authority/closure decision.

## Source-bound cases and actual access

The supplied C41-r9 staging account reports that its ignored-LOCAL check had
skipped input; the original skip output is not in the artifact inspected here,
so that prior execution is not independently reconstructed by this receipt.
Its later recorded check's complete deciding output remains accessible at
`LOCAL/raw/e02-execution-20261027/repairs/C48-r5-c41-context-r1/coordination/C41-r9-after-C48/standalone-r9-ruff.json`.
Against `repairs/C41-r9/postimages/policy-engine/src/polisyos/runtime/http/routes/runs.py`
(SHA-256 `ff81b1cc8e41e03d6f26c4fc52c1197ad8badc53d763ffc3d2a55582e084d4f0`),
the recorded canonical-name check exited 1 with `I001`, `N818`, and `E501`, and
format check exited 1. The JSON records argv and bytes hash but not cwd; the
root's account supplies the product cwd, so that earlier cwd is not independently
established by this JSON alone.

The C60 composition's complete initial check is
`LOCAL/raw/e02-execution-20261027/generated-admission-r1/root-c60-c38-compose-r1/ruff-initial.json`.
For `repairs/C60-r2/postimages/policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py`
(SHA-256 `2833a23e79b9f3569636df94a4f8af00ff81cd63d644b2ae23eea48ec6fa9255`),
the recorded product-cwd canonical-name check exited 1 and reported `I001` at
line 42. Its style work and final source are in the same composition directory;
this observation does not claim runtime verification or global completion.

The C49 original configured check is
`LOCAL/raw/e02-execution-20261027/composition-c41-c49-r1/ruff-static-original.json`;
its independent source-delta review is
`LOCAL/raw/e02-execution-20261027/reviews/C49-local-r3-independent.md`.
For `repairs/C49-local-r2/postimages/policy-engine/src/polisyos/scientist/agent/_drafter_orchestrator.py`
(SHA-256 `f547da329986616ab6bb6158878fe90f5cdd380be3d0fad3af6bc4e131a131cc`),
the recorded product-cwd canonical-name check exited 1 with `I001`. The review
separately qualifies its final per-file stdin checks and leaves final physical
composed-topology qualification to root. It records a static correction, not a
product-runtime finding.

The paths beginning `repairs/` above are relative to
`LOCAL/raw/e02-execution-20261027/`. These are concrete examples, not a census of
all affected files. Full deciding outputs remain in the named accessible JSON
files, rather than being represented by hashes alone.

## Reproduction recipe, not run by this proposal

From `policy-engine`, pass each exact preserved postimage above to the product
Ruff with its canonical path, for example:

```sh
.venv/bin/python -m ruff check --no-cache --config ruff.toml --stdin-filename src/polisyos/runtime/http/routes/runs.py - < ../LOCAL/raw/e02-execution-20261027/repairs/C41-r9/postimages/policy-engine/src/polisyos/runtime/http/routes/runs.py
.venv/bin/python -m ruff format --check --no-cache --config ruff.toml --stdin-filename src/polisyos/runtime/http/routes/runs.py - < ../LOCAL/raw/e02-execution-20261027/repairs/C41-r9/postimages/policy-engine/src/polisyos/runtime/http/routes/runs.py
```

The product `ruff.toml` extends `ruff.generated.toml`; their observed SHA-256
values at the proposal base are respectively
`8ffeafd8510518f1e89e6a2028aff685817bf5466dbffbc8c8bce85d01c8a4c5` and
`759cad425eac3718d5161d1f6fd4bfe52a57f2d28a77cc408d0bc30b955bf2c6`.
Changing config, source bytes, tool version or filesystem topology changes the
replay context. Bind the complete intended input set and final topology at the
actual admission; these representative commands alone do not establish it.

## Proposal custody

`manifest.json` names the exact tracked register preimage, scratch postimage,
patch and observed HEAD. `git apply --check base-to-register.patch` passed at
that preimage. Root must recheck it immediately before composition. No canonical
file, index or ref was modified, and no Ruff, test, or product runtime was run by
this proposal.
