from importlib import import_module


def test_environment_parsers_are_owned_by_common_config() -> None:
    config_module = import_module("polisyos.common.config")
    security_settings = import_module("polisyos.core.security.settings")
    slsa_config = import_module("polisyos.core.security.slsa.config")

    assert config_module.ProcessBootstrapConfig.__module__ == "polisyos.common.config"
    assert config_module.parse_bool.__module__ == "polisyos.common.config"
    assert config_module.parse_int.__module__ == "polisyos.common.config"
    assert config_module._parse_float_env.__module__ == "polisyos.common.config"

    assert security_settings._parse_bool is config_module.parse_bool
    assert security_settings._parse_int is config_module.parse_int
    assert security_settings._parse_float is config_module._parse_float_env
    assert slsa_config.parse_bool is config_module.parse_bool
    assert slsa_config.parse_int is config_module.parse_int
    assert slsa_config.parse_float is config_module._parse_float_env

    assert config_module.parse_bool(None, True) is True
    assert config_module.parse_bool(" YES ", False) is True
    assert config_module.parse_bool("unknown", True) is False
    assert config_module.parse_int("invalid", 3) == 3
    assert config_module._parse_float_env("invalid", 2.0) == 2.0
