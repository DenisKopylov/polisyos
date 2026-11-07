# Source-qualified unmarked randomization fixture

This is a bounded synthetic **software fixture generated on 2026-11-02**,
not a retained production case. The compiler and public executor came from Git
commit `198076863e143dea9f89f02734b13d50dae3eed5`, tree
`2b754a92c27959e2e747738d47ed0b419f3b6dd8`. They generated actual unmarked
ProgramGraph/ExecPlan/Treasury artifacts and observed native results at seeds
0, 17 and -3. No current plan was copied or unmarked to manufacture this input.

The old source used the existing supported Python 3.14.3/JAX 0.8.2 CPU runtime;
the dependency environment is current, not historically reconstructed. The
metadata records its actual versions, critical old source blobs, expected state
and archive hash. The generation run checked all 934 loaded first-party module
origins against the selected immutable old source. Its source-only input slice
was Git-blob verified before execution; no environment or dependency copy was made.

The 53 KB lossless archive preserves the exact generated CAS blob/default/view
manifest bytes for all three cases (291,105 bytes before compression). Only
zero-byte runtime lock files are omitted. The ordinary current public executor
reads those views in a temporary CAS and compares fresh results against the old
observations. Its regression also refuses any forced Treasury read for this
unmarked law. This establishes the named legacy software profile, not exhaustive
production history, economic validity, or scientific/randomness authority.

## Regeneration recipe

Run from `policy-engine/`, using the existing supported environment. Extract only
the exact old source/tools and minimal owner configuration into a temporary
directory; no checkout, environment, production payload or recovery archive is
needed. Keep these source inputs unchanged while generating the fixture.

```sh
historical_fixture_root=$(mktemp -d)
historical_fixture_commit=198076863e143dea9f89f02734b13d50dae3eed5
git -C "$(git rev-parse --show-toplevel)" archive "$historical_fixture_commit" -- \
  policy-engine/src policy-engine/tools policy-engine/pyproject.toml policy-engine/hatch.toml \
  policy-engine/architecture/production_quality/method_catalog_dependency_profiles.toml \
  policy-engine/architecture/production_quality/method_catalog_dependency_authority.toml \
  policy-engine/architecture/production_quality/method_catalog_dependency_digest_domains.toml \
  | tar -xf - -C "$historical_fixture_root"
python3 -c 'import json, pathlib, subprocess, sys; c=sys.argv[2]; pathlib.Path(sys.argv[1]).write_text(json.dumps({"old_commit":c,"old_tree":subprocess.check_output(["git","rev-parse",c+"^{tree}"],text=True).strip()}))' \
  "$historical_fixture_root/admission.json" "$historical_fixture_commit"
JAX_PLATFORMS=cpu OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python -I -B tests/fixtures/foundry/historical_randomization/generate.py \
  "$historical_fixture_root/policy-engine" "$historical_fixture_root/generated" \
  "$PWD" "$historical_fixture_root/admission.json"
```

Before replacing the checked-in fixture, verify extracted file blobs against the
named Git tree and inspect the actual old-run receipt and origins. Preserve the
exact generated `.blob`/`.json` CAS files in one lossless archive and derive
expected values from each `observed.json`, then run the current regression.
Manifest timestamps may differ on regeneration; reproducibility concerns the
declared old law, serialized payloads and native results, not a fabricated
timestamp or identical archive hash across separate captures.
