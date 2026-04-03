# Configuration Reference
Related explanation: [Security Model](../explanation/security-model.md).

> pyproject.toml dependency groups, environment variables, and profiles.

## Installation Groups

```bash
# Minimal (core only)
pip install -e .

# Full installation
pip install -e ".[all]"

# Specific extras
pip install -e ".[causal]"      # Causal inference methods
pip install -e ".[ml]"          # Machine learning methods
pip install -e ".[deep]"        # Deep learning (PyTorch)
pip install -e ".[security]"    # Security features (SPIFFE, TEE)
pip install -e ".[rag]"         # RAG/embedding support
pip install -e ".[dev]"         # Development tools
```

<!-- Phase 2: add full list of extras from pyproject.toml, env vars, profile configuration -->
