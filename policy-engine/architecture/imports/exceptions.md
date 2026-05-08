# Import Exceptions Registry

Реестр временных исключений import-policy. Все исключения должны существовать в `architecture/imports/exceptions.toml` и иметь owner + expiry + issue/ADR reference.

Phase 3.4 synthetic-world shim collapse does not add an import exception:
first-party consumers use `polisyos.foundry.agent_sim.world`, and the
wrapper-only `polisyos.synthetic_world` facade is covered by
`architecture/imports/policy.toml` until the 2026-07-31 sunset.

| id                                                   | owner           | reason                                                                                                          | added_on   | expires    | status |
| ---------------------------------------------------- | --------------- | --------------------------------------------------------------------------------------------------------------- | ---------- | ---------- | ------ |
| `E-2026-04-ACADEMIC-SCIENTIST-001`                   | `team-data-forge` | Data Forge academic batch preserves existing scientist autotune/cross_graph dependencies for claim adjudication and benchmarking until those contracts are extracted | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-CORE-CLI-METRIC-VALIDATION-SCIENTIST-001` | `team-polisyos` | core metric-validation CLI imports Scientist metric comparison helpers until CLI glue moves out of Core         | 2026-04-24 | 2026-07-01 | active |
| `E-2026-04-CORE-CLI-SCIENTIST-001`                   | `team-polisyos` | core CLI scientist subcommands lazily import Scientist provider and agent evaluation entrypoints                | 2026-04-17 | 2026-07-01 | active |
| `E-2026-05-DATA-FORGE-LEGAL-BATCH-LEX-001`           | `team-data-forge` | Data Forge legal offline code still reuses Lex runtime contracts/errors/artifact helpers while Lex runtime consumers reach legal artifacts through read_api.legal | 2026-05-01 | 2026-07-30 | active |
| `E-2026-05-DATA-FORGE-LEGAL-BATCH-SCIENTIST-001`     | `team-data-forge` | Phase 4 legal benchmark code keeps its existing scientist quality-scoring dependency after the no-behavior-change move | 2026-05-01 | 2026-07-30 | active |
| `E-2026-05-DATA-FORGE-UKRAINE-BUILDERS-FOUNDRY-001`  | `team-data-forge` | Phase 5 moved accepted Ukraine production builders into Data Forge without behavior changes; Foundry protocol and release bundle dependencies remain until builder contracts are split downward | 2026-05-01 | 2026-07-30 | active |
| `E-2026-05-DATA-FORGE-UKRAINE-BUILDERS-LEX-001`      | `team-data-forge` | Phase 5 keeps existing Ukraine release intervention compilation behavior while Lex-facing payload contracts are extracted | 2026-05-01 | 2026-07-30 | active |
| `E-2026-05-DATA-FORGE-UKRAINE-BUILDERS-SCIENTIST-001` | `team-data-forge` | Phase 5 keeps existing Ukraine calibration governance behavior while Scientist governance facades are extracted | 2026-05-01 | 2026-07-30 | active |
| `E-2026-04-FABRIC-WORLD-DEEP-001`                    | `team-polisyos` | Fabric benchmarks and observability still call world materialization/segment helpers before facade extraction   | 2026-04-17 | 2026-07-01 | active |
| `E-2026-05-FOUNDRY-CALIBRATION-CONTINUOUS-001`       | `team-foundry` | Foundry econometrics advanced methods still reuse Calibration continuous contracts until the calibration facade or method-owned adapter is extracted | 2026-05-01 | 2026-07-30 | active |
| `E-2026-05-FOUNDRY-FABRIC-QUALITY-001`               | `team-polisyos` | Foundry calibration and uncertainty quality bridges import Fabric product-integration helpers until the quality facade is extracted | 2026-05-01 | 2026-07-30 | active |
| `E-2026-04-FOUNDRY-LEX-001`                          | `team-polisyos` | foundry agent_sim wiring/contracts.py imports lex interventions for mechanism wiring                            | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-FOUNDRY-SCIENTIST-001`                    | `team-polisyos` | foundry calibrator and composition_failure_cards import scientist autotune/search types                         | 2026-04-02 | 2026-07-01 | active |
| `E-2026-05-IR-ANALYTICS-CORE-DYNAMICS-001`           | `team-polisyos` | IR analytics dynamic proof bridges still import Core Foundry/truthfulness contracts until those contracts move behind an IR-safe facade | 2026-05-01 | 2026-07-30 | active |
| `E-2026-05-IR-ANALYTICS-CORE-SIMULATION-PROOF-001`   | `team-polisyos` | IR simulation proof bridge imports Core truthfulness contracts until the proof contract facade is extracted     | 2026-05-01 | 2026-07-30 | active |
| `E-2026-04-IR-ANALYTICS-FOUNDRY-001`                 | `team-polisyos` | ir/analytics imports foundry id_engine and strategic for identification and causal queries                      | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-ANALYTICS-SCIENTIST-001`               | `team-polisyos` | ir/analytics imports scientist cross_graph and kernel for alignment certification and budgets                   | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-JAX-001`                               | `team-polisyos` | ir/observation/compiler.py uses jax for calibration tensor operations                                           | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-OBS-FOUNDRY-001`                       | `team-polisyos` | ir/observation modules import foundry calibration and method protocols for contract compilation                 | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-OBS-SCIENTIST-001`                     | `team-polisyos` | ir/observation bundles and contract_compilers import scientist backtesting/search types                         | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-PANDAS-001`                            | `team-polisyos` | ir data/observation/analytics modules use pandas for dataframe handling in new observation plane                | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-PASSES-FOUNDRY-KERNEL-LOWERING-001`    | `team-polisyos` | ir kernel-lowering pass lazily imports Foundry lowering helpers until compiler boundary extraction lands        | 2026-04-24 | 2026-07-01 | active |
| `E-2026-04-IR-SCHEMAS-REFLECTION-001`                | `team-polisyos` | IR schema catalog reflects the repo-local ABI registry package used by schema generation                        | 2026-04-17 | 2026-07-01 | active |
| `E-2026-04-LEX-FOUNDRY-001`                          | `team-polisyos` | lex/interventions.py imports foundry causal-engine and DTR for intervention compilation pipeline                | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-LEX-SCIENTIST-001`                        | `team-polisyos` | lex modules import scientist policy_design/search for intervention-to-policy linking                            | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-SCIENTIST-FOUNDRY-PRIVATE-001`            | `team-polisyos` | scientist search dtr.py imports foundry causal _common private module for DTR shared utilities                  | 2026-04-02 | 2026-07-01 | active |
| `E-2026-05-SCIENTIST-RUNTIME-REPLAY-001`             | `team-scientist` | Scientist replay backend and verification still reuse Runtime replay contracts until replay ownership is split behind a Scientist-safe facade | 2026-05-01 | 2026-07-30 | active |
