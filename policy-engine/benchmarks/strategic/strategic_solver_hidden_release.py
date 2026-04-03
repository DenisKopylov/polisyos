from __future__ import annotations

from benchmarks.advanced.common import main_for_suite


def main(argv: list[str] | None = None) -> int:
    return main_for_suite(
        "strategic_solver_hidden_release",
        description="Academic contour strategic solver hidden-release benchmark",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
