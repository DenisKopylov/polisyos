from __future__ import annotations

import pytest

from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
    SemVer,
    SemverRange,
    validate_metadata,
)


def test_component_id_parsing_and_semver() -> None:
    comp = ComponentId.parse("fiscal.taxation.flat_tax@1.2.3")
    assert comp.base_id == "fiscal.taxation.flat_tax"
    assert comp.namespace == "fiscal.taxation"
    assert comp.name == "flat_tax"
    assert comp.version == "1.2.3"

    for invalid in [
        "A.b@1.0.0",
        "a..b@1.0.0",
        "a.b@1",
        "a@1.0.0",
    ]:
        with pytest.raises(ValueError):
            ComponentId.parse(invalid)

    assert SemVer.parse("1.2.10") > SemVer.parse("1.2.3")
    assert SemVer.parse("1.2.3-alpha.2") > SemVer.parse("1.2.3-alpha.1")
    assert SemVer.parse("1.2.3") > SemVer.parse("1.2.3-rc.1")

    assert SemverRange.parse("1.x").matches("1.8.2")
    assert not SemverRange.parse("1.2.x").matches("1.3.0")
    assert SemverRange.parse(">=1.2.0,<2.0.0").matches("1.9.9")


def test_ir_fragment_rejects_build_metadata_in_compliance() -> None:
    metadata = ComponentMetadata(
        component_id=ComponentId.parse("roads.ir.fragment@1.0.0+local"),
        kind=ComponentKind.IR_FRAGMENT,
        abi_targets={"ir_abi": "1.x"},
        domains=["roads"],
        jurisdictions=[],
        tags=[],
        capabilities=Capability.IR_FRAGMENT,
        deps=[],
    )

    issues = validate_metadata(metadata)
    assert any(issue.code == "component_id.build_metadata_not_allowed" for issue in issues)
