# Core artifacts facade routing v5 — independent source review

Disposition: **GO for the bounded import-routing candidate.** This is source and finite import evidence only; no G acceptance, formal finding closure, or full 69-consumer runtime verification is claimed.

## Exact candidate and boundary

- Candidate base: `43c9d3d64baaf5932852ab2e676b12bbd2c5e14f`, tree `bb17b9687d94f00c6ff838c535c8f06e4168850b`, branch `codex/e02-unified-local-20261009`. The checkout contains known unrelated dirty E02 work; all candidate preimages were checked against the current working files before review.
- Patch: `LOCAL/raw/architecture-core-artifacts-facade-v5-20261011/architecture-core-artifacts-facade-v5.patch`, SHA-256 `3c9945dd214472eca7154db946613bfdf1c5abd46cb6cbda97478fb8ba837c80`.
- Route manifest: `LOCAL/raw/architecture-core-artifacts-facade-v5-20261011/route-manifest.json`, SHA-256 `d874f5485ace728a221c6300fc4730ad016d58dc6adb10aa8b140372d1161dcd`.
- Patch applies cleanly (`git apply --check --verbose`, exit 0). All 69 physical file preimages match the manifest. The current supported-entrypoint contract and facade hashes also match the manifest: `architecture/public_surface/contract.toml@5dcf70e80f03145f14f4cb747022f3041cd1e44bf3c84a3b70379bfd646dd718`, `src/polisyos/core/artifacts/__init__.py@e22dc9dd7872ee0e3867924e5b0de839b6a6f65958624824b056fdf9277b2b67`.

## Review result

This is the same deep-import-to-supported-facade class, widened across all 96 completely mapped Core-artifacts edges (105 import sites, 139 bindings, 69 source files). It changes consumers to the already-supported `polisyos.core.artifacts` facade; it adds no facade exports, public allowlist entries, or history baseline. The facade's 67-name `__all__` already contains every name in the 96 selected routes.

I reconstructed the virtual postimages in memory from the patch. All 69 parse; their SHA-256 postimages match the manifest; stripping import nodes yields identical non-import ASTs; imported names, aliases, scope, and multiplicity are preserved. This includes imports under `TYPE_CHECKING` and local imports. The edits retain the original import scope; I found no moved runtime/type-only boundary or non-import behavior change.

A fresh `policy-engine/.venv/bin/python` process directly compared facade attributes with their source-module objects: all 21 unique source-module/name bindings across the eight target modules are identical, including the lazy `ensure_ir_artifact_store` adapter. A separate actual `from polisyos.core.artifacts import ...` check passed; `ArtifactID` is the exact `ids.ArtifactID` object, and no `polisyos.core.artifacts.ArtifactID` or `polisyos.core.artifacts.manifest.ArtifactID` child-module fallback was loaded. The facade's lazy IR `__getattr__` returned the exact adapter object.

The manifest keeps the 5 partial and 9 unmapped Core-artifacts edges as residual; no claim is made for them. The other 277 of 387 architecture rows are outside this cohort. `formal_closure_ids` is empty and `g_acceptance` is not claimed.

## Verification limits and next checks

No importer unit/integration suites or broad package import sweep were run here. The finite fresh facade/object-identity checks above do not replace the root's planned affected importer tests and composed replay.

The captured Ruff artifacts show two I001 diagnostics removed and a remaining TC004 for `DesignProblem` in `runtime/http/services/control/job_nl_admission.py`. The candidate touches that file's artifact import and separately sorts its local runtime-quality imports, but does not move or alter the `DesignProblem` type-checking import. Because the file intersects this candidate footprint, this review does **not** label the residual inherited under P41; root has assigned the independent `DesignProblem` correction and should replay Ruff on the exact composed source.
