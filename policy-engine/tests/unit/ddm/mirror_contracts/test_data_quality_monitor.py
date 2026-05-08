from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test_data_quality_monitor_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract('ddm', 'data_quality_monitor')
