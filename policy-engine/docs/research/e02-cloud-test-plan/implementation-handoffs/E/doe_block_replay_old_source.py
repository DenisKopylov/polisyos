"""Pin all loaded PolicyOS modules to the immutable frozen-source archive for the probe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    """Preload the old package before pytest's product-root path manipulation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_root.resolve()
    sys.path.insert(0, str(source))
    from polisyos.scientist.methods.doe import analysis

    if not Path(analysis.__file__).is_relative_to(source):
        raise ValueError(f"Probe source is not pinned: {analysis.__file__}")
    sys.stdout.write(f"runtime_source={analysis.__file__}\n")
    sys.stdout.flush()
    import pytest

    status = pytest.main(
        [
            "-o",
            "addopts=",
            "-q",
            "tests/unit/scientist/methods/doe/test_analysis_receipt.py"
            "::test_sobol_whole_paired_block_replay_keeps_estimands_and_rebinds_content",
            "tests/unit/scientist/methods/doe/test_analysis_enhanced.py"
            "::TestS2InteractionRanking::test_native_interaction_matches_independent_anova_oracle",
        ]
    )
    loaded = {
        name: module.__file__
        for name, module in sys.modules.items()
        if name.startswith("polisyos.") and getattr(module, "__file__", None)
    }
    violations = {
        name: path for name, path in loaded.items() if not Path(path).is_relative_to(source)
    }
    if violations:
        raise ValueError(f"Old source execution used foreign modules: {violations}")
    sys.stdout.write(
        f"complete_imported_polisyos_module_denominator={len(loaded)} source_binding=exact58e\n"
    )
    raise SystemExit(status)


if __name__ == "__main__":
    main()
