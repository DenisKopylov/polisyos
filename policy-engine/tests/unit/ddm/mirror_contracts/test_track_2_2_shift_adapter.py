from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test_track_2_2_shift_adapter_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract('ddm', 'track_2_2_shift_adapter')
