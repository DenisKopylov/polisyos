# CLI Reference
Related explanation: [Architecture](../explanation/architecture.md).

This page documents the console scripts declared in `pyproject.toml` and the repo-local workspace
commands used for contributor setup.

## Installed Scripts

| Script | Entry point | Purpose | Notes |
|--------|-------------|---------|-------|
| `polisy` | `polisyos.foundry.plugins.cli:main` | Foundry plugin simulator CLI | Simulation, training, and result analysis |
| `polisyos` | `polisyos.core.components.cli:main` | Core platform operations CLI | Components, Lex, Scientist, replay, signing, audit |
| `polisyos-foundry` | `polisyos.foundry.methods.cli:main` | Foundry methods developer CLI | Scaffold, validate, catalog, compatibility checks |
| `polisyos-causal-capabilities` | `polisyos.foundry.methods.catalog.causal.capabilities:main` | Emit causal capability contract JSON | No subcommands or `--help` mode |
| `polisyos-tools` | `tools.cli:main` | Unified Policy Engine tooling CLI | Category-based entry point for repo-local engineering workflows |

## Repo-Local Workspace Commands

These commands are repo-local unified CLI entrypoints. On a clean checkout they
can be invoked via `python3 -m tools.cli ...`; after bootstrap, the installed
surface is `uv run polisyos-tools ...`.

| Command | Purpose |
|--------|---------|
| `python3 -m tools.cli workspace bootstrap` | Install or verify contributor prerequisites |
| `python3 -m tools.cli workspace doctor` | Validate Python, Node, `uv`, Playwright, lockfiles, generated contracts, and optional env surfaces |
| `python3 -m tools.cli workspace verify` | Run the standard fast local gate |
| `python3 -m tools.cli workspace ci-parity` | Run a heavier local validation pass that approximates the main CI jobs |

## Invocation Notes

- For installed console scripts, the canonical contributor setup is `uv sync --frozen --extra lint --extra test --extra runtime` from `policy-engine/`.
- `python -m polisyos` is currently unsupported because `polisyos.__main__` does not exist.
- `python -m polisyos.foundry` is currently unsupported because `polisyos.foundry.__main__` does not exist.
- `polisyos-causal-capabilities` is a direct JSON emitter. It does not implement `argparse`, subcommands, or a `--help` flag.
- Some subcommands require optional extras or local state:
  - `polisy` YAML configs require `PyYAML`.
  - `polisyos` Lex, Scientist, replay, signing, and audit commands assume a populated CAS or run directory.
  - `polisyos-causal-capabilities` reflects the currently installed causal backend stack.

## Exit Codes

Baseline exit codes across the CLI surface:

| Exit code | Meaning |
|-----------|---------|
| `0` | Success, help output, or successful report emission |
| `1` | Operational failure, failed validation/check, or runtime exception |
| `2` | Usage error or invalid CLI shape |

Additional note:

- `polisyos-foundry` returns `130` on `KeyboardInterrupt`.

## `polisy` — Foundry Plugin Simulator

### Synopsis

```bash
polisy COMMAND [OPTIONS]
```

### Commands

| Command | Description |
|---------|-------------|
| `list` | List available plugins |
| `run` | Run a simulation |
| `train` | Train agents |
| `analyze` | Analyze a result JSON file |

### `polisy list`

```bash
polisy list [--verbose]
```

- `--verbose`, `-v`: show plugin description, capabilities, and tags.

### `polisy run`

```bash
polisy run [--config CONFIG] [--domain DOMAIN] [--n-agents N] [--n-steps N] [--seed N] [--output PATH]
```

Key flags:

- `--config`, `-c`: JSON or YAML config file.
- `--domain`, `-d`: repeatable domain selector when not using a config file.
- `--n-agents`, `-n`: default `1000`.
- `--n-steps`, `-s`: default `256`.
- `--output`, `-o`: output directory, default `./output`.

Output:

- prints simulation objective values to stdout;
- writes `results.json` into the output directory.

Example:

```bash
polisy run --domain economics --n-agents 500 --n-steps 128 --output ./output
```

### `polisy train`

```bash
polisy train [--config CONFIG] [--domain DOMAIN] [--n-episodes N] [--output PATH]
```

Key flags:

- `--config`, `-c`: JSON or YAML config.
- `--domain`, `-d`: repeatable domain selector.
- `--n-episodes`, `-e`: default `100`.
- `--output`, `-o`: output directory, default `./output`.

Output:

- prints the final loss to stdout;
- writes `training_loss.png` into the output directory.

### `polisy analyze`

```bash
polisy analyze RESULT_PATH [--metrics METRIC]
```

Key flags:

- `result_path`: required path to a result JSON file.
- `--metrics`, `-m`: repeatable metric filter.

Output:

- prints the selected result keys and values to stdout.

## `polisyos` — Core Platform CLI

### Synopsis

```bash
polisyos [--version] COMMAND ...
```

### Runtime Notes

- `polisyos.core.components.cli_parts` imports subcommand handlers lazily after argument parsing, so importing the module is safe for docs/tests that only need parser metadata.
- Local component discovery honors `POLISYOS_PACKS_PATHS` in addition to repeatable `--dev-scan-path`.
- Artifact signing/verification commands honor `POLISYOS_SIGNING_KEY`, `POLISYOS_SIGNING_KEY_FILE`, `POLISYOS_SIGN_TRUST_DIR`, `POLISYOS_SIGN_REVOKED_DIR`, `POLISYOS_SIGN_IDENTITIES`, and strict-identity/sign-on-put flags documented in [Configuration](configuration.md).
- `audit export` SLSA defaults come from `POLISYOS_SLSA_*` unless `--slsa-mode` or `--slsa-policy` is passed explicitly.

### Top-Level Commands

| Command | Description |
|---------|-------------|
| `components` | Component discovery and bootstrap |
| `registry` | Build component registries |
| `scholar` | Scholar enrichment operations |
| `lex` | NormPack build and impact analysis |
| `scientist` | Burn-in, calibration, sensitivity, stress-test, and backtest workflows |
| `replay` | Replay a decision packet |
| `resume` | Resume a checkpointed run |
| `keygen` | Generate signing keys |
| `sign` | Sign CAS artifacts |
| `verify` | Verify artifact signatures |
| `audit` | Export and verify audit packages |

### `polisyos components`

| Command | Synopsis | Purpose |
|---------|----------|---------|
| `components list` | `polisyos components list [--kind KIND] [--domain DOMAIN] [--jurisdiction JURISDICTION] [--tag TAG] [--json] [--dev-scan-path PATH]` | Filter and print component registry entries |
| `components bootstrap` | `polisyos components bootstrap [--group GROUP] [--dev-scan-path PATH] [--no-dev-scan] [--skip-connectors] [--skip-methods] [--skip-evaluators] [--skip-extractors] [--skip-providers] [--skip-nodes] [--json]` | Rebuild component discovery state |

Notes:

- `components list --kind` accepts:
  - `ir_fragment`
  - `foundry_method`
  - `fabric_connector`
  - `scholar_extractor`
  - `lex_extractor`
  - `lex_evaluator`
  - `scientist_node`
  - `norm_pack_provider`
- Both commands support repeatable `--dev-scan-path` for local plugin/dev discovery.

### `polisyos registry`

| Command | Synopsis | Purpose |
|---------|----------|---------|
| `registry build` | `polisyos registry build --domain DOMAIN [--jurisdiction JURISDICTION] [--cas-root PATH] [--dev-scan-path PATH]` | Build a registry artifact for a domain/jurisdiction pair |

### `polisyos scholar`

| Command | Synopsis | Purpose |
|---------|----------|---------|
| `scholar enrich` | `polisyos scholar enrich --intent INTENT [--cas-root PATH] [--fact-log-root PATH]` | Enrich scholar evidence for a research intent |

### `polisyos lex`

| Command | Synopsis | Purpose |
|---------|----------|---------|
| `lex normpack build` | `polisyos lex normpack build --jurisdiction JURISDICTION [--domain DOMAIN] [--as-of DATE] [--cas-root PATH] [--fact-log-root PATH]` | Build a NormPack snapshot |
| `lex impact` | `polisyos lex impact OLD_REF NEW_REF [--passes PASSES] [--profile {fast,mvp,strict}] [--format {json,md}] [--output PATH] [--cas-root PATH]` | Compare two NormPack references and emit a legal impact report |

Example:

```bash
polisyos lex normpack build --jurisdiction ua --domain labor --cas-root .polisyos/cas
polisyos lex impact old_normpack.json new_normpack.json --format md --output impact.md
```

### `polisyos scientist`

| Command | Synopsis | Purpose |
|---------|----------|---------|
| `scientist burn-in` | `polisyos scientist burn-in --config CONFIG [--output PATH] [--format json] [--cas-root PATH]` | Run burn-in workflow from a JSON config |
| `scientist calibration-report` | `polisyos scientist calibration-report --config CONFIG [--output PATH] [--format {json,md}] [--cas-root PATH]` | Generate calibration governance output |
| `scientist sensitivity run` | `polisyos scientist sensitivity run --config CONFIG [--output PATH] [--format json] [--cas-root PATH]` | Run sensitivity analysis |
| `scientist stress-test` | `polisyos scientist stress-test --config CONFIG [--output PATH] [--format json] [--cas-root PATH]` | Run stress-test suite |
| `scientist backtest` | `polisyos scientist backtest [--config CONFIG] [--cas-root PATH] [--output PATH] [--format {json,summary,markdown}] [--json] [--run-id ID] [--historical-data PATH] [--metric METRIC] [--ground-truth SERIES] [--intervention-step N] [--prediction-source {provided,scientist,naive}] [--predicted SERIES]` | Run backtesting in config mode or inline single-scenario mode |

Backtest mode notes:

- Config mode: supply `--config` with `plans[]`.
- Inline mode requires at least:
  - `--run-id`
  - `--historical-data`
  - one or more `--metric`
  - one or more `--ground-truth metric=v1,v2,...`
- `--json` is an alias for `--format json`.

Example:

```bash
polisyos scientist backtest \
  --run-id wage-subsidy-q1 \
  --historical-data ./historical.json \
  --metric employment_rate \
  --ground-truth employment_rate=0.61,0.63,0.64 \
  --prediction-source naive \
  --format summary
```

### Replay And Resume

| Command | Synopsis | Purpose |
|---------|----------|---------|
| `replay` | `polisyos replay PACKET_REF [--cas-root PATH] [--mode {bit_exact,ci_bounded,skip}] [--strategy {auto,foundry,scientist}] [--check-only] [--export PATH] [--bundle PATH] [--no-verify] [--tolerance FLOAT] [--confidence-level FLOAT] [--json]` | Replay a decision packet and optionally verify or export the replay subgraph |
| `resume` | `polisyos resume RUN_ID [--cas-root PATH] [--checkpoint-policy {off,strict,best_effort}] [--force] [--dry-run] [--json]` | Resume a checkpointed run |

### Signing And Verification

| Command | Synopsis | Purpose |
|---------|----------|---------|
| `keygen` | `polisyos keygen [--output PATH] [--name NAME] [--force] [--public-only] [--json]` | Generate Ed25519 signing keys |
| `sign` | `polisyos sign [ARTIFACT_REF] [--all] [--cas-root PATH] [--key PATH] [--identity LABEL] [--workers N] [--resign] [--json]` | Sign one artifact or all CAS artifacts |
| `verify` | `polisyos verify [ARTIFACT_REF] [--all] [--cas-root PATH] [--public-key PATH] [--trust-dir PATH] [--revoked-dir PATH] [--identities PATH] [--workers N] [--json] [--quiet] [--fail-unsigned] [--strict-identity]` | Verify artifact signatures and identity bindings |

### Audit

| Command | Synopsis | Purpose |
|---------|----------|---------|
| `audit export` | `polisyos audit export RUN_ID [--cas-root PATH] [--runs-dir PATH] [--output PATH] [--profile {full,manifests_only}] [--exclude-kinds CSV] [--signing-policy {strict,warn,skip}] [--slsa-mode {off,local,private,public}] [--slsa-policy {best_effort,required}] [--no-visualization] [--json]` | Export an audit package |
| `audit verify` | `polisyos audit verify PACKAGE [--trusted-key PATH] [--trusted-keys-dir PATH] [--allow-package-keys] [--fail-unsigned] [--require-slsa] [--format {markdown,json}] [--output PATH] [--json]` | Verify an audit package |

## `polisyos-foundry` — Foundry Methods Developer CLI

### Synopsis

```bash
polisyos-foundry COMMAND [OPTIONS]
```

### Commands

| Command | Description |
|---------|-------------|
| `scaffold` | Generate a new method skeleton |
| `validate` | Validate one method or the whole registry |
| `catalog` | Print the current method catalog |
| `compat` | Check for breaking signature changes against a baseline |

### `polisyos-foundry scaffold`

```bash
polisyos-foundry scaffold --namespace NAMESPACE --name NAME [--version VERSION] [--backend {numpy,jax,solver,bayesian}] [--fidelity {LOW,MEDIUM,HIGH}] [--output-dir PATH] [--overwrite]
```

Example:

```bash
polisyos-foundry scaffold --namespace causal.did --name my_estimator --backend jax --fidelity HIGH
```

### `polisyos-foundry validate`

```bash
polisyos-foundry validate [--all] [--file FILE] [--module MODULE] [--class CLS]
```

Behavior:

- `--all`: validate all registered methods.
- `--file`: validate a method class from a Python file.
- `--module` + `--class`: validate a class from an importable module.
- Returns `1` when checks run but one or more methods fail validation.
- Returns `2` when no target is specified.

### `polisyos-foundry catalog`

```bash
polisyos-foundry catalog [--namespace NAMESPACE]
```

Output columns:

- fully-qualified method name;
- fidelity;
- backend;
- input slot count;
- output slot count.

### `polisyos-foundry compat`

```bash
polisyos-foundry compat [--baseline BASELINE]
```

Default baseline:

```text
tests/foundry/fixtures/signature_baseline.json
```

Returns:

- `0` when no breaking changes are detected;
- `1` when methods were removed or signatures changed;
- `2` when the baseline file is missing.

## `polisyos-causal-capabilities` — Causal Capability Contract

### Synopsis

```bash
polisyos-causal-capabilities
```

### Behavior

- No subcommands.
- No `--help` or `--version` support.
- Writes a JSON `CausalCapabilityContract` to stdout.

### Output Fields

| Field | Meaning |
|-------|---------|
| `backends[]` | Resolved backend availability, disabled reason, and supported identification families |
| `full_backend_order` | Preferred backend fallback order |
| `supported_families` | Identification families available in the current environment |
| `disabled_families` | Identification families currently unavailable and why |
| `degradation_policy` | Runtime fallback policy |
| `dependency_fingerprint` | Environment-sensitive fingerprint of dependency availability |
| `notes` | Human-readable capability notes |

Example:

```bash
polisyos-causal-capabilities > causal-capabilities.json
```

Current local environment note:

- symbolic backends `y0` and `r_causaleffect` currently resolve as unavailable in this workspace;
- the emitted contract still advertises `bounds_manski` and `direct` support via fallback backends.
