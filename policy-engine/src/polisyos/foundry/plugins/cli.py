from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from polisyos.foundry.plugins.api import PolisySimulator
from polisyos.foundry.plugins.core import DomainConfig, get_registry
from polisyos.foundry.plugins.discovery import auto_register_plugins


def _write(message: str) -> None:
    sys.stdout.write(message + "\n")


def _error(message: str) -> None:
    sys.stderr.write(message + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PolisyOS Policy Simulation Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    list_parser = subparsers.add_parser("list", help="List available plugins")
    list_parser.add_argument("--verbose", "-v", action="store_true")

    run_parser = subparsers.add_parser("run", help="Run simulation")
    run_parser.add_argument("--config", "-c", type=Path, help="Config file (JSON/YAML)")
    run_parser.add_argument("--domain", "-d", action="append", help="Domain to simulate")
    run_parser.add_argument("--n-agents", "-n", type=int, default=1000)
    run_parser.add_argument("--n-steps", "-s", type=int, default=256)
    run_parser.add_argument("--seed", type=int, default=42)
    run_parser.add_argument("--output", "-o", type=Path, default=Path("./output"))

    train_parser = subparsers.add_parser("train", help="Train agents")
    train_parser.add_argument("--config", "-c", type=Path)
    train_parser.add_argument("--domain", "-d", action="append")
    train_parser.add_argument("--n-episodes", "-e", type=int, default=100)
    train_parser.add_argument("--output", "-o", type=Path, default=Path("./output"))

    analyze_parser = subparsers.add_parser("analyze", help="Analyze results")
    analyze_parser.add_argument("result_path", type=Path)
    analyze_parser.add_argument("--metrics", "-m", action="append")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list_plugins(args)
    elif args.command == "run":
        cmd_run_simulation(args)
    elif args.command == "train":
        cmd_train(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    else:
        parser.print_help()


def cmd_list_plugins(args) -> None:
    registry = get_registry()
    auto_register_plugins(registry)

    plugins = registry.list_plugins()

    _write(f"\nAvailable Plugins ({len(plugins)}):")
    _write("-" * 50)

    for meta in plugins:
        _write(f"\n  {meta.name} (v{meta.version})")
        if args.verbose:
            _write(f"    Description: {meta.description}")
            _write("    Capabilities: " + ", ".join(c.value for c in meta.capabilities))
            if meta.tags:
                _write("    Tags: " + ", ".join(meta.tags))


def cmd_run_simulation(args) -> None:
    sim = PolisySimulator()

    if args.config:
        config = load_config(args.config)
        for domain, domain_config in config.get("domains", {}).items():
            sim.add_domain(domain, DomainConfig(**domain_config))
    else:
        domains = args.domain or ["economics"]
        for domain in domains:
            sim.add_domain(domain, DomainConfig(n_agents=args.n_agents))

    _write(f"Running simulation with {len(sim.domains)} domain(s)...")
    _write(f"  Domains: {list(sim.domains.keys())}")
    _write(f"  Steps: {args.n_steps}")

    result = sim.run(n_steps=args.n_steps, seed=args.seed)

    _write("\nResults:")
    for name, value in result.objectives.items():
        _write(f"  {name}: {float(value):.4f}")

    args.output.mkdir(parents=True, exist_ok=True)
    save_results(result, args.output / "results.json")

    _write(f"\nResults saved to {args.output}")


def cmd_train(args) -> None:
    sim = PolisySimulator()

    if args.config:
        config = load_config(args.config)
        for domain, domain_config in config.get("domains", {}).items():
            sim.add_domain(domain, DomainConfig(**domain_config))
    else:
        domains = args.domain or ["economics"]
        for domain in domains:
            sim.add_domain(domain, DomainConfig(n_agents=1000))

    _write(f"Training for {args.n_episodes} episodes...")

    result = sim.train(n_episodes=args.n_episodes)

    _write("\nTraining complete!")
    _write(f"  Final loss: {result.loss_history[-1]:.4f}")

    args.output.mkdir(parents=True, exist_ok=True)
    result.plot_losses(str(args.output / "training_loss.png"))


def cmd_analyze(args) -> None:
    if not args.result_path.exists():
        _error(f"Error: {args.result_path} not found")
        sys.exit(1)

    with open(args.result_path) as f:
        results = json.load(f)

    _write("\nAnalysis Results:")
    for key, value in results.items():
        if args.metrics and key not in args.metrics:
            continue
        _write(f"  {key}: {value}")


def load_config(path: Path) -> dict:
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("pyyaml required for YAML configs") from exc
        with open(path) as f:
            return yaml.safe_load(f)
    with open(path) as f:
        return json.load(f)


def save_results(result, path: Path) -> None:
    data = {
        "n_steps": result.n_steps,
        "objectives": {k: float(v) for k, v in result.objectives.items()},
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    main()
