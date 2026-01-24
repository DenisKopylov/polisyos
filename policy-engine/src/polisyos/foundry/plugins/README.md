# PolisyOS Domain Plugins

This package provides a modular plugin architecture for domain-specific simulations
(economics, healthcare, climate, etc.). It defines core protocols, a registry, and
utilities for building multi-domain simulations.

## Key Components

- `core.py`: Plugin protocols, metadata, and registry.
- `composite.py`: Composite state/executor for multi-domain simulations.
- `discovery.py`: Auto-discovery of plugins.
- `api.py`: High-level `PolisySimulator` API.
- `cli.py`: Command-line interface.

## Quick Start

```python
from polisyos.foundry.plugins import DomainConfig, PolisySimulator

sim = PolisySimulator()
sim.add_domain("economics", DomainConfig(n_agents=1000))
result = sim.run(n_steps=256)

print(result.get_metric("economics", "gdp"))
```

## Multi-domain Example

```python
from polisyos.foundry.plugins import DomainConfig, PolisySimulator

sim = PolisySimulator()
sim.add_domain("economics", DomainConfig(n_agents=1000))
sim.add_domain("healthcare", DomainConfig(n_agents=1000))

sim.add_interaction(
    source_domain="healthcare",
    target_domain="economics",
    source_field="costs",
    target_field="agents.consumption",
)

result = sim.run(n_steps=128)
```

## CLI

```bash
python -m polisyos.foundry.plugins.cli list
python -m polisyos.foundry.plugins.cli run --domain economics --n-steps 128
```
