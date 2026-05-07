"""Minimal canonical SyntheticWorld example for external callers."""

from __future__ import annotations

import json
import sys

from polisyos.foundry.agent_sim.world import SyntheticWorld, phase0_seed_world_specs


def main() -> None:
    spec = phase0_seed_world_specs()[0]
    world = SyntheticWorld.from_spec(spec)
    sample = world.sample(split="train")
    truth = world.truth(targets=["causal.ate"])

    payload = {
        "causal_ate": round(float(truth.targets["causal.ate"]["value"]), 6),
        "family": spec.family.value,
        "rows": sample.row_count,
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
