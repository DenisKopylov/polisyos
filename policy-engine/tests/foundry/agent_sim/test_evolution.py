"""Tests for agent_sim evolutionary strategies config."""
from __future__ import annotations

import pytest

from polisyos.foundry.agent_sim.evolution import ESConfig, CMAESConfig
from polisyos.foundry.contracts.fidelity import FidelityLevel


class TestESConfig:
    def test_default_values(self):
        cfg = ESConfig()
        assert cfg.population_size == 64
        assert cfg.n_generations == 100
        assert cfg.antithetic is True
        assert cfg.fidelity == FidelityLevel.SURROGATE_FLUID

    def test_custom_values(self):
        cfg = ESConfig(population_size=32, sigma=0.05, antithetic=False)
        assert cfg.population_size == 32
        assert cfg.sigma == 0.05
        assert cfg.antithetic is False


class TestCMAESConfig:
    def test_default_values(self):
        cfg = CMAESConfig()
        assert cfg.population_size == 64
        assert cfg.sigma_init == 0.5
        assert cfg.fidelity == FidelityLevel.SURROGATE_FLUID
