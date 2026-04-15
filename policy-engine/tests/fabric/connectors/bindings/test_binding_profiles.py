"""Tests for binding profiles: models, registry, builtins, and resolver."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from polisyos.fabric.connectors.bindings import (
    BindingProfile,
    BindingProfileRegistry,
    BindingRuleSpec,
    BindingTransformSpec,
)
from polisyos.fabric.connectors.bindings.builtin_profiles import (
    BUILTIN_BINDING_PROFILES,
)
from polisyos.fabric.connectors.bindings.resolver import (
    persist_binding_rules_artifact,
    resolve_binding_rules,
)


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestBindingTransformSpec:
    def test_defaults(self):
        t = BindingTransformSpec()
        assert t.op == "identity"
        assert t.params == {}

    def test_with_params(self):
        t = BindingTransformSpec(op="round", params={"digits": 4})
        assert t.op == "round"
        assert t.params["digits"] == 4

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            BindingTransformSpec(op="test", unknown="field")


class TestBindingRuleSpec:
    def test_minimal(self):
        rule = BindingRuleSpec(
            binding_id="test.rule",
            source_path="COL_A",
            target_slot_id="macro.value",
        )
        assert rule.binding_id == "test.rule"
        assert rule.required is False
        assert rule.default_value is None
        assert rule.transforms == []

    def test_with_transforms(self):
        rule = BindingRuleSpec(
            binding_id="test.rule",
            source_path="value",
            target_slot_id="macro.observed_value",
            required=True,
            transforms=[
                BindingTransformSpec(op="to_decimal"),
                BindingTransformSpec(op="round", params={"digits": 2}),
            ],
        )
        assert len(rule.transforms) == 2
        assert rule.transforms[0].op == "to_decimal"

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            BindingRuleSpec(
                binding_id="test",
                source_path="x",
                target_slot_id="y",
                unknown="field",
            )


class TestBindingProfile:
    def test_minimal(self):
        profile = BindingProfile(
            profile_id="test_profile",
            display_name="Test Profile",
            schema_family="timeseries",
        )
        assert profile.profile_id == "test_profile"
        assert profile.strategy == "auto"
        assert profile.rules == []
        assert profile.tags == []

    def test_profile_id_pattern_valid(self):
        BindingProfile(
            profile_id="ts_single_indicator",
            display_name="Test",
            schema_family="timeseries",
        )

    def test_profile_id_pattern_invalid_uppercase(self):
        with pytest.raises(Exception):
            BindingProfile(
                profile_id="TS_UPPER",
                display_name="Test",
                schema_family="timeseries",
            )

    def test_profile_id_pattern_invalid_start_with_number(self):
        with pytest.raises(Exception):
            BindingProfile(
                profile_id="1invalid",
                display_name="Test",
                schema_family="timeseries",
            )

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            BindingProfile(
                profile_id="test",
                display_name="Test",
                schema_family="ts",
                unknown="field",
            )


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestBindingProfileRegistry:
    @pytest.fixture(autouse=True)
    def _reset_registry(self):
        BindingProfileRegistry.reset_instance()
        yield
        BindingProfileRegistry.reset_instance()

    def test_singleton(self):
        r1 = BindingProfileRegistry.get_instance()
        r2 = BindingProfileRegistry.get_instance()
        assert r1 is r2

    def test_bootstrap_loads_builtins(self):
        registry = BindingProfileRegistry.get_instance()
        all_profiles = registry.list_all()
        assert len(all_profiles) == len(BUILTIN_BINDING_PROFILES)

    def test_get_existing(self):
        registry = BindingProfileRegistry.get_instance()
        profile = registry.get("ts_single_indicator")
        assert profile is not None
        assert profile.profile_id == "ts_single_indicator"

    def test_get_nonexistent(self):
        registry = BindingProfileRegistry.get_instance()
        assert registry.get("nonexistent") is None

    def test_register_new(self):
        registry = BindingProfileRegistry.get_instance()
        new_profile = BindingProfile(
            profile_id="custom_profile",
            display_name="Custom",
            schema_family="cross_section",
        )
        registry.register(new_profile)
        assert registry.get("custom_profile") is not None

    def test_register_duplicate_raises(self):
        registry = BindingProfileRegistry.get_instance()
        profile = BindingProfile(
            profile_id="ts_single_indicator",
            display_name="Dup",
            schema_family="timeseries",
        )
        with pytest.raises(ValueError, match="already registered"):
            registry.register(profile)

    def test_register_override(self):
        registry = BindingProfileRegistry.get_instance()
        profile = BindingProfile(
            profile_id="ts_single_indicator",
            display_name="Override",
            schema_family="timeseries",
        )
        registry.register(profile, override=True)
        loaded = registry.get("ts_single_indicator")
        assert loaded.display_name == "Override"

    def test_list_by_family(self):
        registry = BindingProfileRegistry.get_instance()
        ts_profiles = registry.list_by_family("timeseries")
        assert len(ts_profiles) >= 2  # at least single + multi indicator
        for p in ts_profiles:
            assert p.schema_family == "timeseries"

    def test_list_by_family_empty(self):
        registry = BindingProfileRegistry.get_instance()
        result = registry.list_by_family("nonexistent_family")
        assert result == []

    def test_list_all_sorted(self):
        registry = BindingProfileRegistry.get_instance()
        profiles = registry.list_all()
        ids = [p.profile_id for p in profiles]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Builtin profiles tests
# ---------------------------------------------------------------------------


class TestBuiltinProfiles:
    def test_builtin_count(self):
        assert len(BUILTIN_BINDING_PROFILES) == 3

    def test_builtin_profile_ids(self):
        ids = {p.profile_id for p in BUILTIN_BINDING_PROFILES}
        assert "ts_single_indicator" in ids
        assert "ts_multi_indicator" in ids
        assert "ts_exchange_rate" in ids

    def test_single_indicator_rules(self):
        profile = next(
            p for p in BUILTIN_BINDING_PROFILES if p.profile_id == "ts_single_indicator"
        )
        assert len(profile.rules) == 2
        rule_ids = {r.binding_id for r in profile.rules}
        assert "ts.time_period" in rule_ids
        assert "ts.value" in rule_ids

    def test_multi_indicator_rules(self):
        profile = next(
            p for p in BUILTIN_BINDING_PROFILES if p.profile_id == "ts_multi_indicator"
        )
        assert len(profile.rules) == 4

    def test_exchange_rate_has_transforms(self):
        profile = next(
            p for p in BUILTIN_BINDING_PROFILES if p.profile_id == "ts_exchange_rate"
        )
        value_rule = next(r for r in profile.rules if r.binding_id == "exr.value")
        assert len(value_rule.transforms) == 2
        assert value_rule.transforms[0].op == "to_decimal"
        assert value_rule.transforms[1].op == "round"

    def test_exchange_rate_has_default_value(self):
        profile = next(
            p for p in BUILTIN_BINDING_PROFILES if p.profile_id == "ts_exchange_rate"
        )
        denom_rule = next(
            r for r in profile.rules if r.binding_id == "exr.currency_denom"
        )
        assert denom_rule.default_value == "EUR"
        assert denom_rule.required is False


# ---------------------------------------------------------------------------
# Resolver tests
# ---------------------------------------------------------------------------


class TestResolveBindingRules:
    def test_basic_resolve(self):
        profile = BindingProfile(
            profile_id="test_resolve",
            display_name="Test",
            schema_family="timeseries",
            rules=[
                BindingRuleSpec(
                    binding_id="r1",
                    source_path="COL_A",
                    target_slot_id="macro.value",
                    required=True,
                ),
            ],
        )
        rules = resolve_binding_rules(profile)
        assert len(rules) == 1
        assert rules[0]["binding_id"] == "r1"
        assert rules[0]["source_path"] == "COL_A"
        assert rules[0]["target_slot_id"] == "macro.value"
        assert rules[0]["required"] is True

    def test_resolve_with_transforms(self):
        profile = BindingProfile(
            profile_id="test_transforms",
            display_name="Test",
            schema_family="timeseries",
            rules=[
                BindingRuleSpec(
                    binding_id="r1",
                    source_path="value",
                    target_slot_id="macro.observed_value",
                    transforms=[
                        BindingTransformSpec(op="to_decimal"),
                        BindingTransformSpec(op="round", params={"digits": 2}),
                    ],
                ),
            ],
        )
        rules = resolve_binding_rules(profile)
        assert "transforms" in rules[0]
        assert len(rules[0]["transforms"]) == 2

    def test_resolve_with_default_value(self):
        profile = BindingProfile(
            profile_id="test_default",
            display_name="Test",
            schema_family="timeseries",
            rules=[
                BindingRuleSpec(
                    binding_id="r1",
                    source_path="CURRENCY_DENOM",
                    target_slot_id="monetary.currency_denom",
                    default_value="EUR",
                ),
            ],
        )
        rules = resolve_binding_rules(profile)
        assert rules[0]["default_value"] == "EUR"

    def test_resolve_empty_profile(self):
        profile = BindingProfile(
            profile_id="test_empty",
            display_name="Empty",
            schema_family="timeseries",
        )
        rules = resolve_binding_rules(profile)
        assert rules == []


class TestPersistBindingRulesArtifact:
    def test_persist_uses_protocol_owned_store_contract(self):
        captured: dict[str, object] = {}

        class FakeStore:
            def put_json(self, obj, opts, canon_spec=None):
                captured["payload"] = obj
                captured["opts"] = opts
                captured["canon_spec"] = canon_spec

                class _Ref:
                    artifact_id = "sha256:" + ("0" * 64)

                return _Ref()

        profile = BindingProfile(
            profile_id="test_protocol_store",
            display_name="Protocol Store",
            schema_family="timeseries",
        )

        ref = persist_binding_rules_artifact(
            FakeStore(),
            profile,
            data_snapshot_ref="snap_protocol",
        )

        assert ref.artifact_id == "sha256:" + ("0" * 64)
        assert captured["payload"] == {
            "profile_id": "test_protocol_store",
            "schema_family": "timeseries",
            "strategy": "auto",
            "rules": [],
            "expected_columns": [],
            "data_snapshot_ref": "snap_protocol",
        }
        assert captured["opts"].kind == "fabric.binding_rules"
        assert captured["opts"].schema.name == "polisyos.fabric.BindingRules"

    def test_persist_roundtrip(self, tmp_path: Path):
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.core.canon import from_canonical_bytes

        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)

        profile = BindingProfile(
            profile_id="test_persist",
            display_name="Test Persist",
            schema_family="timeseries",
            rules=[
                BindingRuleSpec(
                    binding_id="r1",
                    source_path="TIME_PERIOD",
                    target_slot_id="macro.time_index",
                    required=True,
                ),
            ],
            expected_columns=["TIME_PERIOD"],
        )

        ref = persist_binding_rules_artifact(
            store, profile, data_snapshot_ref="snap_abc123",
        )
        assert ref is not None

        # Verify the artifact can be loaded
        raw = store.get_bytes(ref.artifact_id)
        payload = from_canonical_bytes(raw)
        assert payload["profile_id"] == "test_persist"
        assert payload["data_snapshot_ref"] == "snap_abc123"
        assert len(payload["rules"]) == 1

    def test_persist_without_snapshot_ref(self, tmp_path: Path):
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.core.canon import from_canonical_bytes

        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)

        profile = BindingProfile(
            profile_id="test_no_snap",
            display_name="Test",
            schema_family="timeseries",
        )

        ref = persist_binding_rules_artifact(store, profile)
        raw = store.get_bytes(ref.artifact_id)
        payload = from_canonical_bytes(raw)
        assert "data_snapshot_ref" not in payload
