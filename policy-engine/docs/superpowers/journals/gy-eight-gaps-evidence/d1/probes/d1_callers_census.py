"""Read the complete tracked RetrievalService call census after a branch write."""

import json

from tests.repo_quality.tools.test_gy_d1_catalog_wiring import constructor_census


def main() -> int:
    _, report = constructor_census()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
