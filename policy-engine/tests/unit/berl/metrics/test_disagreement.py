from __future__ import annotations

from polisyos.berl.metrics.disagreement import AttributionVector, compare_attribution_vectors


def test_disagreement_surfaces_rank_and_sign_conflicts() -> None:
    summary = compare_attribution_vectors(
        [
            AttributionVector("kernel_shap", {"income": 0.7, "assets": 0.2, "age": 0.1}),
            AttributionVector("lime", {"income": -0.5, "assets": 0.4, "age": 0.1}),
            AttributionVector("ale_local_bin", {"assets": 0.8, "income": 0.1, "age": 0.1}),
        ],
        top_k=1,
        agreement_floor=0.75,
    )

    assert "income" in summary.sign_conflict_features
    assert "methods_disagree_on_rank_order" in summary.flags
    assert summary.top_k_jaccard_median < 1.0


def test_agreeing_attributions_do_not_surface_rank_or_sign_conflicts() -> None:
    summary = compare_attribution_vectors(
        [
            AttributionVector("kernel_shap", {"income": 0.7, "assets": 0.2, "age": 0.1}),
            AttributionVector("lime", {"income": 0.6, "assets": 0.3, "age": 0.1}),
        ],
        top_k=1,
        agreement_floor=0.75,
    )

    assert not summary.sign_conflict_features
    assert "methods_disagree_on_rank_order" not in summary.flags
    assert summary.top_k_jaccard_median == 1.0
