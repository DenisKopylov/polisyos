from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test__store_serialization_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract('fabric', '_store_serialization')
