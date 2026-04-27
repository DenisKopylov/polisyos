"""Small policy-relevant tabular benchmark suite for BERL release tests."""

from __future__ import annotations


def eligibility_rows() -> list[dict[str, float]]:
    """Return deterministic policy-like eligibility rows."""

    rows: list[dict[str, float]] = []
    for income_bucket in range(4):
        for household_size in range(1, 5):
            income = float(800 + (income_bucket * 450))
            assets = float(300 + (income_bucket * 250))
            employment = float(income_bucket > 1)
            need_score = float(household_size) / max(income / 1000.0, 1.0)
            risk = need_score - (assets / 5000.0) - (0.25 * employment)
            rows.append(
                {
                    "income": income,
                    "assets": assets,
                    "employment_status": employment,
                    "household_size": float(household_size),
                    "eligibility_risk": risk,
                }
            )
    return rows


def eligibility_score_model(features: dict[str, float]) -> float:
    """Policy-like scalar risk score used by BERL smoke benchmarks."""

    return (
        (0.9 * features["household_size"])
        - (0.0012 * features["income"])
        - (0.0008 * features["assets"])
        - (0.4 * features["employment_status"])
    )
