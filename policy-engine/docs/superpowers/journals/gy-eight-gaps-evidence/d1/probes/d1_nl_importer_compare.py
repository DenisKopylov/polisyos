"""Compare exact selected failure identities without substituting a smaller run."""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path("_build/gy-gaps/d1/root")
    paths = {
        "slice_base": root / "nl-catalog-importer-base.json",
        "first_wiring": root / "nl-catalog-importer.json",
        "canonical_wiring": root / "nl-catalog-importer-canonical.json",
    }
    receipts = {key: json.loads(path.read_text()) for key, path in paths.items()}
    commands = {tuple(value["command"]) for value in receipts.values()}
    assert len(commands) == 1
    command = next(iter(commands))
    selected = {arg for arg in command if "::test_" in arg}
    identities = {}
    for name, receipt in receipts.items():
        assert not receipt["timed_out"] and receipt["returncode"] == 1
        failed = {line.split(" ", 2)[1] for line in receipt["stdout"].splitlines()
                  if line.startswith("FAILED ")}
        independent = {member for member in selected
                       if f"FAILED {member}" in receipt["stdout"]}
        assert failed == independent and failed <= selected and failed
        assert "ERROR collecting" not in receipt["stdout"]
        identities[name] = failed
    print(json.dumps({
        "command": command,
        "selected_test_identities": sorted(selected),
        "selected_denominator": len(selected),
        "independent_command_node_count": sum("::test_" in arg for arg in command),
        "receipts": {key: str(path) for key, path in paths.items()},
        "failure_identities": {key: sorted(value) for key, value in identities.items()},
        "current_added_vs_slice_base": sorted(identities["canonical_wiring"] - identities["slice_base"]),
        "current_lost_vs_slice_base": sorted(identities["slice_base"] - identities["canonical_wiring"]),
        "corrected_own_failure": sorted(identities["first_wiring"] - identities["canonical_wiring"]),
        "p41_attribution": "not_established",
        "reason": "Exact base replay repeats the remaining canary failure, but this lane changes its NL input module; zero changed-input intersection is not established.",
    }, indent=2))


if __name__ == "__main__":
    main()
