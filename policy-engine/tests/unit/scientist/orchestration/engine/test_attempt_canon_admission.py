from __future__ import annotations

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.protocol import _require_return_selected_profile_writer
from polisyos.core.canon import CanonSpec, CanonViolation
from polisyos.scientist.orchestration.engine.retry import (
    _AttemptAuthority,
    _AttemptFacade,
    _AttemptWriteDeniedError,
)

_UNREADY_SPEC = CanonSpec(version="0.3.0")


@pytest.mark.parametrize("selected_api", [False, True], ids=["legacy", "selected"])
@pytest.mark.parametrize("keyword", [False, True], ids=["positional", "keyword"])
def test_attempt_store_freezes_spec_before_wrapped_lookup_and_preserves_gate(
    selected_api: bool, keyword: bool
) -> None:
    spec = CanonSpec()
    ref = ArtifactRef(
        artifact_id="sha256:" + "0" * 64,
        kind="test.attempt",
        media_type="application/json",
    )

    class _Store:
        def __init__(self) -> None:
            self.armed = False
            self.calls: list[str] = []

        @property
        def put_json(self):
            if self.armed:
                object.__setattr__(spec, "version", "0.3.0")
            if selected_api:

                def selected(_obj, _opts, canon_spec=None, *, return_selected_profile=False):
                    self.calls.append(canon_spec.version)
                    return ref

                return selected

            def legacy(_obj, _opts, canon_spec=None):
                self.calls.append(canon_spec.version)
                return ref

            return legacy

    store = _Store()
    authority = _AttemptAuthority()
    facade = _AttemptFacade(
        store,
        authority,
        write_methods=frozenset({"put_json"}),
        raise_on_revoked_write=True,
    )
    if selected_api:
        _require_return_selected_profile_writer(facade, "put_json")
    else:
        with pytest.raises(NotImplementedError, match="artifact_store_return_selected_profile"):
            _require_return_selected_profile_writer(facade, "put_json")
    store.armed = True
    if keyword:
        observed = facade.put_json({"value": 7}, object(), canon_spec=spec)
    else:
        observed = facade.put_json({"value": 7}, object(), spec)
    assert observed is ref
    assert spec.version == "0.3.0"
    assert store.calls == ["0.2.0"]

    authority.revoke()
    with pytest.raises(_AttemptWriteDeniedError, match="attempt_write_revoked"):
        facade.put_json({"value": 8}, object(), CanonSpec())
    assert store.calls == ["0.2.0"]


@pytest.mark.parametrize("selected_api", [False, True], ids=["legacy", "selected"])
def test_attempt_store_refuses_unadmitted_profile_before_wrapped_lookup(selected_api: bool) -> None:
    class _Store:
        def __init__(self) -> None:
            self.lookups = 0
            self.calls = 0

        @property
        def put_json(self):
            self.lookups += 1
            if selected_api:

                def selected(_obj, _opts, canon_spec=None, *, return_selected_profile=False):
                    self.calls += 1
                    return object()

                return selected

            def legacy(_obj, _opts, canon_spec=None):
                self.calls += 1
                return object()

            return legacy

    store = _Store()
    facade = _AttemptFacade(
        store,
        _AttemptAuthority(),
        write_methods=frozenset({"put_json"}),
    )
    store.lookups = 0
    with pytest.raises(CanonViolation, match="canonical_writer_profile_unavailable"):
        facade.put_json({"value": 7}, object(), CanonSpec(version="0.3.0"))
    assert store.lookups == 0
    assert store.calls == 0


@pytest.mark.parametrize("selected_api", [False, True], ids=["legacy", "selected"])
def test_attempt_store_binds_default_v2_when_target_exposes_canon_spec(selected_api: bool) -> None:
    ref = ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="test.attempt",
        media_type="application/json",
    )
    observed: list[str] = []

    class _Store:
        @property
        def put_json(self):
            if selected_api:

                def selected(
                    _obj,
                    _opts,
                    canon_spec=_UNREADY_SPEC,
                    *,
                    return_selected_profile=False,
                ):
                    observed.append(canon_spec.version)
                    return ref

                return selected

            def legacy(_obj, _opts, canon_spec=_UNREADY_SPEC):
                observed.append(canon_spec.version)
                return ref

            return legacy

    facade = _AttemptFacade(_Store(), _AttemptAuthority(), write_methods=frozenset({"put_json"}))
    assert facade.put_json({"value": 7}, object()) is ref
    assert observed == ["0.2.0"]


def test_attempt_store_keeps_two_argument_legacy_writer_usable() -> None:
    observed: list[object] = []

    class _Store:
        def put_json(self, value, options):
            observed.append(value)
            return value

    facade = _AttemptFacade(_Store(), _AttemptAuthority(), write_methods=frozenset({"put_json"}))
    assert facade.put_json({"value": 7}, object()) == {"value": 7}
    assert observed == [{"value": 7}]
