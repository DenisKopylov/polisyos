from __future__ import annotations

from pathlib import Path

_CATALOG_SOURCE_ROOT = (
    Path(__file__).resolve().parents[4] / "src" / "polisyos" / "foundry" / "methods" / "catalog"
)


def test_catalog_source_files_do_not_ship_placeholder_namespaces() -> None:
    offenders: list[str] = []
    for path in sorted(_CATALOG_SOURCE_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if 'namespace="placeholder"' in text or 'namespace = "placeholder"' in text:
            offenders.append(str(path))

    assert not offenders, (
        "Catalog source files must leave undecorated MethodSignature "
        "namespaces empty instead of shipping placeholder literals:\n" + "\n".join(offenders)
    )
