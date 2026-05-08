from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test__manifest_lifecycle_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract('core', '_manifest_lifecycle')
