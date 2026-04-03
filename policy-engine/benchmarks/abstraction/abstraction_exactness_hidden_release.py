from __future__ import annotations

from benchmarks.advanced.common import main_for_suite


def main(argv: list[str] | None = None) -> int:
    return main_for_suite(
        "abstraction_exactness_hidden_release",
        description="Academic contour abstraction exactness hidden-release benchmark",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
