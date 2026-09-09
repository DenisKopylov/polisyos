"""Resolve the two CORR IR contracts through their existing stable owner facade."""

import importlib
import json
import sys


def main() -> int:
    facade = importlib.import_module("polisyos.ir")
    required = {
        "ArticleExtractionResult": "polisyos.ir.analytics.literature",
        "TrinityBundle": "polisyos.ir.trinity",
    }
    results = {}
    for name, module in required.items():
        try:
            resolved = getattr(facade, name)
        except AttributeError:
            results[name] = {"status": "stable_export_absent", "owner_module": module}
            continue
        owner = getattr(importlib.import_module(module), name)
        results[name] = {
            "status": "same_owner_object" if resolved is owner else "wrong_owner_object",
            "owner_module": module,
            "listed_public": name in facade.__all__,
            "lazy_owner_binding": facade._LAZY_IMPORTS[name],
        }
    passed = all(
        value["status"] == "same_owner_object" and value["listed_public"]
        for value in results.values()
    )
    sys.stdout.write(
        json.dumps(
            {"declared_symbol_denominator": sorted(required), "results": results, "passed": passed},
            sort_keys=True,
        )
        + "\n"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
