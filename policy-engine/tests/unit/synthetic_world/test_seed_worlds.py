from __future__ import annotations

from pathlib import Path

from polisyos.foundry.agent_sim.world import (
    SyntheticWorld,
    SyntheticWorldDGP,
    WorldFamily,
    phase0_seed_world_specs,
)


def _required_targets(family: WorldFamily) -> set[str]:
    if family is WorldFamily.CROSS_SECTIONAL:
        return {
            "causal.ate",
            "bayesian.exact_posterior",
            "bayesian.prior_params",
            "bayesian.latent_states_true",
            "survey.base_weights",
            "survey.design_variance",
            "distributional.quantile.p90",
            "ml.classification.probability",
        }
    if family is WorldFamily.SURVEY_REPEATED_CROSS_SECTION:
        return {
            "survey.design_effect",
            "survey.design_variance",
            "survey.response_probabilities",
            "survey.calibrated_weights",
            "econometrics.wave_effects",
            "forecast.h1.mean",
            "bayesian.reference_posterior",
            "bayesian.posterior_predictive_reference",
        }
    if family is WorldFamily.PANEL_DYNAMIC:
        return {
            "causal.dynamic_ate",
            "causal.dynamic_regime_value",
            "econometrics.panel_fe",
            "econometrics.iv_late",
            "econometrics.irf",
            "forecast.h3.mean",
            "distributional.quantile.p90",
            "bayesian.reference_posterior",
            "bayesian.posterior_predictive_reference",
        }
    return {
        "causal.spatial_ate",
        "forecast.h3.mean",
        "distributional.pdf",
        "distributional.quantile.p90",
        "regime.labels",
        "bayesian.reference_posterior",
        "bayesian.latent_states_true",
    }


def test_phase0_seed_worlds_cover_all_phase0_families_and_publish_truth_manifests() -> None:
    specs = phase0_seed_world_specs()
    assert {spec.family for spec in specs} == {
        WorldFamily.CROSS_SECTIONAL,
        WorldFamily.SURVEY_REPEATED_CROSS_SECTION,
        WorldFamily.PANEL_DYNAMIC,
        WorldFamily.SPATIO_TEMPORAL,
    }

    for spec in specs:
        world = SyntheticWorld.from_spec(spec)
        sample = world.sample(split="train")
        truth = world.truth()
        assert sample.row_count > 0
        assert _required_targets(spec.family).issubset(set(truth.available_targets))
        assert truth.config_hash == spec.config_hash()
        assert set(truth.target_families) >= {
            "bayesian",
            "distributional",
            "survey",
        }


def test_cross_sectional_world_supports_yaml_loading_and_replay() -> None:
    fixture = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "polisyos"
        / "foundry"
        / "agent_sim"
        / "world"
        / "configs"
        / "examples"
        / "phase0_cross_sectional.yaml"
    )
    spec = SyntheticWorldDGP.from_path(fixture)
    world_a = SyntheticWorld.from_spec(spec)
    world_b = SyntheticWorld.from_yaml(fixture)

    sample_a = world_a.sample(split="train")
    sample_b = world_b.sample(split="train")
    truth_a = world_a.truth()
    truth_b = world_b.truth()

    assert sample_a.model_dump(mode="json") == sample_b.model_dump(mode="json")
    assert truth_a.model_dump(mode="json") == truth_b.model_dump(mode="json")
    assert "bayesian.exact_posterior" in truth_a.targets
    assert world_a.sample(split="train", format="records")
    parquet_sample = world_a.sample(split="train", format="parquet")
    assert parquet_sample.format == "parquet"


def test_evaluate_supports_scalar_and_vector_truth_targets() -> None:
    spec = phase0_seed_world_specs()[0]
    world = SyntheticWorld.from_spec(spec)
    truth = world.truth(targets=["causal.ate", "causal.cate"])

    result = world.evaluate(
        predictions={
            "causal.ate": truth.targets["causal.ate"]["value"],
            "causal.cate": {"values": truth.targets["causal.cate"]["values"]},
        },
        hooks=("coverage", "calibration"),
    )

    assert result.metrics["causal.ate.abs_error"] == 0.0
    assert result.metrics["causal.cate.rmse"] == 0.0
    assert result.hooks == ("coverage", "calibration")


def test_survey_repeated_cross_section_supports_prefix_queries_and_plots() -> None:
    spec = next(
        item
        for item in phase0_seed_world_specs()
        if item.family is WorldFamily.SURVEY_REPEATED_CROSS_SECTION
    )
    world = SyntheticWorld.from_spec(spec)
    truth = world.truth(prefixes=["survey.", "forecast."])

    assert "survey.design_effect" in truth.targets
    assert "forecast.h1.mean" in truth.targets

    classification_truth = world.truth(targets=["ml.classification.probability"])
    prediction = {
        "ml.classification.probability": {
            "values": classification_truth.targets["ml.classification.probability"]["values"],
            "labels": world.truth(targets=["ml.classification.label"]).targets[
                "ml.classification.label"
            ]["values"],
        }
    }
    evaluation = world.evaluate(predictions=prediction, hooks=("calibration",))
    assert "ml.classification.probability.brier" in evaluation.metrics
    assert "ml.classification.probability" in evaluation.plots


def test_truth_spec_filters_families_but_preserves_explicit_extra_targets() -> None:
    base_spec = next(
        item
        for item in phase0_seed_world_specs()
        if item.family is WorldFamily.SURVEY_REPEATED_CROSS_SECTION
    )
    spec = base_spec.model_copy(
        update={
            "truth": base_spec.truth.model_copy(
                update={
                    "include_survey": False,
                    "include_forecasting": False,
                    "extra_targets": ("survey.design_effect",),
                }
            )
        }
    )
    world = SyntheticWorld.from_spec(spec)
    truth = world.truth()

    assert "survey.design_effect" in truth.available_targets
    assert "survey.base_weights" not in truth.available_targets
    assert "forecast.h1.mean" not in truth.available_targets


def test_artifact_manifest_carries_versions_and_replay_refs() -> None:
    world = SyntheticWorld.from_spec(phase0_seed_world_specs()[0])
    artifact = world.artifact()

    assert artifact.world_spec_version == "1.0.0"
    assert artifact.truth_schema_version == "1.0.0"
    assert artifact.artifact_schema_version == "1.0.0"
    assert artifact.replay_key
    assert artifact.latent_artifact_ref and artifact.latent_artifact_ref.startswith(
        "synthetic-world://latent/"
    )
    assert artifact.observed_artifact_ref and artifact.observed_artifact_ref.startswith(
        "synthetic-world://observed/"
    )
    assert artifact.truth_artifact_ref and artifact.truth_artifact_ref.startswith(
        "synthetic-world://truth/"
    )


def test_truth_subset_filters_interval_payloads() -> None:
    spec = next(
        item for item in phase0_seed_world_specs() if item.family is WorldFamily.PANEL_DYNAMIC
    )
    world = SyntheticWorld.from_spec(spec)
    full_truth = world.truth(targets=["forecast.h1.interval_90"])
    unit_id = full_truth.targets["forecast.h1.interval_90"]["coords"]["unit_id"][0]

    subset_truth = world.truth(targets=["forecast.h1.interval_90"], subset={"unit_id": unit_id})
    payload = subset_truth.targets["forecast.h1.interval_90"]
    assert payload["coords"]["unit_id"] == [unit_id]
    assert len(payload["lower"]) == 1
    assert len(payload["upper"]) == 1


def test_evaluate_metric_filters_accept_suffix_and_qualified_metric_names() -> None:
    spec = phase0_seed_world_specs()[0]
    world = SyntheticWorld.from_spec(spec)
    classification_truth = world.truth(targets=["ml.classification.probability"])
    labels = world.truth(targets=["ml.classification.label"]).targets["ml.classification.label"][
        "values"
    ]
    prediction = {
        "ml.classification.probability": {
            "values": classification_truth.targets["ml.classification.probability"]["values"],
            "labels": labels,
        }
    }

    suffix_run = world.evaluate(predictions=prediction, metrics=("brier",))
    qualified_run = world.evaluate(
        predictions=prediction, metrics=("ml.classification.probability.log_loss",)
    )

    assert set(suffix_run.metrics) == {"ml.classification.probability.brier"}
    assert set(qualified_run.metrics) == {"ml.classification.probability.log_loss"}
