"""Tests for source profiles: models, registry, resolver."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config


class TestSourceProfileModel:
    def test_valid_profile(self):
        profile = SourceProfile(
            profile_id="test_profile",
            display_name="Test Profile",
            connector_family="worldbank",
            base_url="https://api.example.com",
        )
        assert profile.profile_id == "test_profile"
        assert profile.auth_policy == "none"
        assert profile.timeout_seconds == 30

    def test_profile_id_validation(self):
        with pytest.raises(ValidationError):
            SourceProfile(
                profile_id="INVALID",
                display_name="Bad",
                connector_family="x",
                base_url="https://x.com",
            )

    def test_profile_id_must_start_with_letter(self):
        with pytest.raises(ValidationError):
            SourceProfile(
                profile_id="9bad",
                display_name="Bad",
                connector_family="x",
                base_url="https://x.com",
            )

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            SourceProfile(
                profile_id="test",
                display_name="Test",
                connector_family="x",
                base_url="https://x.com",
                unknown_field="bad",
            )

    def test_all_fields(self):
        profile = SourceProfile(
            profile_id="full",
            display_name="Full Profile",
            description="A complete profile",
            connector_family="sdmx",
            base_url="https://api.ecb.europa.eu",
            headers={"X-SDMX-Agency": "ECB"},
            auth_policy="api_key",
            timeout_seconds=60,
            max_retries=5,
            rate_limit_rps=3.0,
            dataset_discovery_hints=["EXR", "BSI"],
            tags=["ecb", "finance"],
            source_organization="ECB",
            source_url="https://ecb.europa.eu",
            estimated_datasets=600,
        )
        assert profile.headers == {"X-SDMX-Agency": "ECB"}
        assert profile.rate_limit_rps == 3.0
        assert profile.estimated_datasets == 600


class TestSourceProfileRegistry:
    def setup_method(self):
        SourceProfileRegistry.reset_instance()

    def teardown_method(self):
        SourceProfileRegistry.reset_instance()

    def test_get_instance_bootstraps(self):
        reg = SourceProfileRegistry.get_instance()
        profiles = reg.list_all()
        assert len(profiles) > 0
        ids = {p.profile_id for p in profiles}
        assert "worldbank_wdi" in ids
        assert "wvs_wave7" in ids
        assert "ecb_sdmx" in ids

    def test_get_existing(self):
        reg = SourceProfileRegistry.get_instance()
        profile = reg.get("worldbank_wdi")
        assert profile is not None
        assert profile.connector_family == "worldbank"

    def test_get_existing_wvs(self):
        reg = SourceProfileRegistry.get_instance()
        profile = reg.get("wvs_wave7")
        assert profile is not None
        assert profile.connector_family == "wvs"

    def test_get_missing(self):
        reg = SourceProfileRegistry.get_instance()
        assert reg.get("nonexistent") is None

    def test_list_all_sorted(self):
        reg = SourceProfileRegistry.get_instance()
        profiles = reg.list_all()
        ids = [p.profile_id for p in profiles]
        assert ids == sorted(ids)

    def test_list_by_family(self):
        reg = SourceProfileRegistry.get_instance()
        sdmx = reg.list_by_family("sdmx")
        assert len(sdmx) >= 3
        for p in sdmx:
            assert p.connector_family == "sdmx"

    def test_list_by_family_empty(self):
        reg = SourceProfileRegistry.get_instance()
        assert reg.list_by_family("nonexistent") == []

    def test_register_custom(self):
        reg = SourceProfileRegistry.get_instance()
        custom = SourceProfile(
            profile_id="custom_test",
            display_name="Custom",
            connector_family="custom",
            base_url="https://custom.api.com",
        )
        reg.register(custom)
        assert reg.get("custom_test") is not None

    def test_register_duplicate_raises(self):
        reg = SourceProfileRegistry.get_instance()
        custom = SourceProfile(
            profile_id="worldbank_wdi",
            display_name="Dup",
            connector_family="worldbank",
            base_url="https://x.com",
        )
        with pytest.raises(ValueError, match="already registered"):
            reg.register(custom)

    def test_register_override(self):
        reg = SourceProfileRegistry.get_instance()
        custom = SourceProfile(
            profile_id="worldbank_wdi",
            display_name="Overridden",
            connector_family="worldbank",
            base_url="https://new.url",
        )
        reg.register(custom, override=True)
        assert reg.get("worldbank_wdi").display_name == "Overridden"

    def test_snapshot_all_is_detached_from_later_override(self):
        reg = SourceProfileRegistry.get_instance()
        original = reg.get("worldbank_wdi")
        assert original is not None
        original = original.model_copy(
            update={"headers": {"X-PolicyOS-Snapshot": "before"}}, deep=True
        )
        reg.register(original, override=True)

        snapshot = reg.snapshot_all()
        captured = next(item for item in snapshot if item.profile_id == "worldbank_wdi")
        replacement = captured.model_copy(
            update={"headers": {"X-PolicyOS-Snapshot": "after"}}, deep=True
        )
        reg.register(replacement, override=True)

        assert captured.headers == {"X-PolicyOS-Snapshot": "before"}
        assert reg.get("worldbank_wdi").headers == {"X-PolicyOS-Snapshot": "after"}

    def test_singleton(self):
        reg1 = SourceProfileRegistry.get_instance()
        reg2 = SourceProfileRegistry.get_instance()
        assert reg1 is reg2

    def test_reset(self):
        reg1 = SourceProfileRegistry.get_instance()
        SourceProfileRegistry.reset_instance()
        reg2 = SourceProfileRegistry.get_instance()
        assert reg1 is not reg2


class TestResolveConnectionConfig:
    def test_basic_profile(self):
        profile = SourceProfile(
            profile_id="test",
            display_name="Test",
            connector_family="worldbank",
            base_url="https://api.worldbank.org/v2",
            timeout_seconds=45,
            max_retries=5,
        )
        config = resolve_connection_config(profile)
        assert config.url == "https://api.worldbank.org/v2"
        assert config.timeout_seconds == 45
        assert config.max_retries == 5
        assert config.auth_method is None
        assert config.source_profile_fingerprint is not None
        assert config.cache_scope_fingerprint.startswith("sha256:")

    def test_same_profile_id_with_changed_material_has_distinct_cache_identity(self):
        original = SourceProfile(
            profile_id="stable_id",
            display_name="Stable",
            connector_family="fixture",
            base_url="fixture://source-a",
            headers={"Authorization": "secret-a"},
        )
        changed = original.model_copy(
            update={
                "base_url": "fixture://source-b",
                "headers": {"Authorization": "secret-b"},
            }
        )

        first = resolve_connection_config(original)
        second = resolve_connection_config(changed)

        assert first.source_profile_fingerprint != second.source_profile_fingerprint
        assert first.cache_scope_fingerprint != second.cache_scope_fingerprint
        assert "secret-a" not in str(first.to_dict(redact=True))
        assert "secret-b" not in str(second.to_dict(redact=True))
        assert (
            first.to_dict(redact=True)["source_profile_fingerprint"]
            == first.source_profile_fingerprint
        )

    def test_profile_with_headers(self):
        profile = SourceProfile(
            profile_id="ecb",
            display_name="ECB",
            connector_family="sdmx",
            base_url="https://data-api.ecb.europa.eu/service",
            headers={"X-SDMX-Agency": "ECB", "X-Custom": "value"},
        )
        config = resolve_connection_config(profile)
        assert config.headers == {"X-SDMX-Agency": "ECB", "X-Custom": "value"}

    def test_profile_with_auth(self):
        profile = SourceProfile(
            profile_id="authed",
            display_name="Authed",
            connector_family="rest",
            base_url="https://api.example.com",
            auth_policy="api_key",
        )
        config = resolve_connection_config(profile)
        assert config.auth_method == "api_key"

    def test_rate_limit(self):
        profile = SourceProfile(
            profile_id="limited",
            display_name="Limited",
            connector_family="worldbank",
            base_url="https://api.worldbank.org/v2",
            rate_limit_rps=5.0,
        )
        config = resolve_connection_config(profile)
        assert config.rate_limit_rps == 5.0
