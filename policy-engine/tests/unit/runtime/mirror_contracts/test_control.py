from typing import get_args

from polisyos.core.contracts.control import ControlJobKind
from polisyos.runtime.http.services import _control_contracts, control_plane_store
from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test_control_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract("runtime", "control")


def test_control_job_kind_is_canonical_for_both_runtime_consumers() -> None:
    canonical = frozenset(get_args(ControlJobKind))

    assert "acquisition" in canonical
    assert canonical == _control_contracts._CONTROL_JOB_KINDS
    assert canonical == control_plane_store._CONTROL_JOB_KINDS
    assert _control_contracts._coerce_control_job_kind("acquisition") == "acquisition"
    assert control_plane_store._coerce_control_job_kind("acquisition") == "acquisition"
