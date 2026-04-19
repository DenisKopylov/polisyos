# Import Exceptions Registry

Реестр временных исключений import-policy. Все исключения должны существовать в `import_exceptions.toml` и иметь owner + expiry.

| id | owner | reason | added_on | expires | status |
| --- | --- | --- | --- | --- | --- |
| `E-2026-04-ACADEMIC-SCIENTIST-001` | `team-polisyos` | academic batch imports scientist autotune/cross_graph for claim adjudication and benchmarking | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-CORE-CLI-SCIENTIST-001` | `team-polisyos` | core CLI scientist subcommands lazily import Scientist provider and agent evaluation entrypoints | 2026-04-17 | 2026-07-01 | active |
| `E-2026-04-DATASETS-ACADEMIC-001` | `team-polisyos` | datasets modules import academic canonical_seed and registry for variable alignment | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-FABRIC-DATASETS-001` | `team-polisyos` | fabric retrieval service imports datasets source_registry for connector discovery | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-FABRIC-WORLD-DEEP-001` | `team-polisyos` | Fabric benchmarks and observability still call world materialization/segment helpers before facade extraction | 2026-04-17 | 2026-07-01 | active |
| `E-2026-04-FOUNDRY-LEX-001` | `team-polisyos` | foundry agent_sim wiring/contracts.py imports lex interventions for mechanism wiring | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-FOUNDRY-SCIENTIST-001` | `team-polisyos` | foundry calibrator and composition_failure_cards import scientist autotune/search types | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-FOUNDRY-UKRAINE-DATA-001` | `team-polisyos` | Foundry release acceptance verifies Ukraine release manifests until release-manifest facade extraction lands | 2026-04-17 | 2026-07-01 | active |
| `E-2026-04-IR-ANALYTICS-FOUNDRY-001` | `team-polisyos` | ir/analytics imports foundry id_engine and strategic for identification and causal queries | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-ANALYTICS-SCIENTIST-001` | `team-polisyos` | ir/analytics imports scientist cross_graph and kernel for alignment certification and budgets | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-JAX-001` | `team-polisyos` | ir/observation/compiler.py uses jax for calibration tensor operations | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-OBS-FOUNDRY-001` | `team-polisyos` | ir/observation modules import foundry calibration and method protocols for contract compilation | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-OBS-SCIENTIST-001` | `team-polisyos` | ir/observation bundles and contract_compilers import scientist backtesting/search types | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-PANDAS-001` | `team-polisyos` | ir data/observation/analytics modules use pandas for dataframe handling in new observation plane | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-IR-SCHEMAS-REFLECTION-001` | `team-polisyos` | IR schema catalog reflects the repo-local ABI registry package used by schema generation | 2026-04-17 | 2026-07-01 | active |
| `E-2026-04-LEX-BATCH-SCIENTIST-001` | `team-polisyos` | lex batch benchmark imports scientist agent knowledge tools for quality scoring | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-LEX-FOUNDRY-001` | `team-polisyos` | lex/interventions.py imports foundry causal-engine and DTR for intervention compilation pipeline | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-LEX-SCIENTIST-001` | `team-polisyos` | lex modules import scientist policy_design/search for intervention-to-policy linking | 2026-04-02 | 2026-07-01 | active |
| `E-2026-04-RUNTIME-FOUNDRY-PRIVATE-001` | `team-polisyos` | runtime replay resolves Foundry execution posture before that helper is exposed through a public Foundry facade | 2026-04-17 | 2026-07-01 | active |
| `E-2026-04-SCIENTIST-FABRIC-PRIVATE-001` | `team-polisyos` | Scientist Fabric adapter depends on the connector bridge while a public Fabric execution port is extracted | 2026-04-17 | 2026-07-01 | active |
| `E-2026-04-SCIENTIST-FOUNDRY-PRIVATE-001` | `team-polisyos` | scientist search dtr.py imports foundry causal _common private module for DTR shared utilities | 2026-04-02 | 2026-07-01 | active |
