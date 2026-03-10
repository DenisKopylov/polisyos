import { normalizeSimulationPayload } from "@/lib/domain/simulation";

describe("simulation domain", () => {
  it("normalizes metrics payloads with bounds, series, and embedded distributional data", () => {
    const model = normalizeSimulationPayload("foundry.metrics", {
      distributional: {
        breakdowns: [
          {
            cohorts: [
              {
                cohort_id: "low",
                cohort_label: "Low income",
                impact_direction: "down",
                is_vulnerable: true,
                metric_deltas: { delta: -0.5 },
                population_share: "0.2",
              },
            ],
            dimension: "income_group",
            gini_after: "0.35",
            gini_before: "0.4",
            gini_delta: "-0.05",
            primary_metric: "delta",
          },
        ],
        losers_count: "4",
        losers_share: "0.25",
        overall_gini_after: "0.35",
        overall_gini_before: "0.4",
        overall_gini_delta: "-0.05",
        winners_count: "12",
        winners_share: "0.75",
      },
      extra_metric_history: [5, 6, 7],
      series_comparison: {
        observed_income: {
          model: [11, 13],
          real: [10, 12],
          time: [1, 2],
        },
      },
      time_series: {
        gdp_change: {
          baseline: [1, 2],
          lower_1sigma: [0.8, 1.8],
          policy: [3, 4],
          upper_1sigma: [1.2, 2.2],
        },
      },
      uncertainty_bounds: {
        gdp_change_ci_level: 0.95,
        gdp_change_lower: 0.1,
        gdp_change_upper: 0.14,
        inflation_change_point: -0.03,
      },
      values: {
        gdp_change: 0.12,
        inflation_change: -0.03,
        schema_version: "v1",
      },
    });

    expect(model).toMatchObject({
      boundsByMetric: {
        gdp_change: {
          ciLevel: 0.95,
          lower: 0.1,
          point: null,
          upper: 0.14,
        },
        inflation_change: {
          ciLevel: null,
          lower: null,
          point: -0.03,
          upper: null,
        },
      },
      distributional: {
        breakdowns: [
          {
            cohorts: [
              {
                cohortId: "low",
                cohortLabel: "Low income",
                delta: -0.5,
                impactDirection: "down",
                isVulnerable: true,
                populationShare: 0.2,
              },
            ],
            dimensionLabel: "Income Group",
            primaryMetric: "delta",
          },
        ],
      },
      notes: [],
      sourceKind: "metrics",
    });
    expect(model?.metrics).toEqual([
      {
        ciLevel: 0.95,
        ciLower: 0.1,
        ciUpper: 0.14,
        formatted: "+12.00",
        key: "gdp_change",
        label: "GDP Change",
        severity: "high",
        unit: "%",
        value: 12,
      },
      {
        ciLevel: null,
        ciLower: null,
        ciUpper: null,
        formatted: "-3.00",
        key: "inflation_change",
        label: "Inflation Change",
        severity: "low",
        unit: "%",
        value: -3,
      },
    ]);
    expect(model?.timeSeries).toEqual([
      {
        id: "gdp_change",
        label: "Gdp Change",
        mode: "baseline_policy",
        points: [
          {
            baseline: 1,
            lower1: 0.8,
            lower2: undefined,
            policy: 3,
            step: 0,
            upper1: 1.2,
            upper2: undefined,
          },
          {
            baseline: 2,
            lower1: 1.8,
            lower2: undefined,
            policy: 4,
            step: 1,
            upper1: 2.2,
            upper2: undefined,
          },
        ],
        supportsUncertainty: true,
      },
      {
        id: "observed_income",
        label: "Observed Income",
        mode: "observed_fitted",
        points: [
          { fitted: 11, observed: 10, step: 1 },
          { fitted: 13, observed: 12, step: 2 },
        ],
        supportsUncertainty: false,
      },
      {
        id: "extra_metric_history",
        label: "Extra Metric History",
        mode: "single",
        points: [
          { step: 0, value: 5 },
          { step: 1, value: 6 },
          { step: 2, value: 7 },
        ],
        supportsUncertainty: false,
      },
    ]);
  });

  it("normalizes calibration reports into metrics, charts, and fit summaries", () => {
    const model = normalizeSimulationPayload("foundry.calibration_report", {
      calibrated_params: {
        beta: "0.3",
      },
      fit_quality: {
        per_target: {
          gdp: {
            mae: "0.8",
            mse: "1.0",
            n: "100",
            r2: "0.9",
            rmse: "1.2",
          },
        },
      },
      grad_norm_history: [0.9, 0.4],
      loss_history: [3, 2, 1],
      series_comparison: {
        gdp: {
          model: [1.1, 2.1],
          real: [1, 2],
          time: [0, 1],
        },
      },
      total_loss: "0.25",
      uncertainties: {
        method: "bootstrap",
        params: ["seed", 2],
      },
      uncertainty_envelopes: {
        beta: {
          confidence_interval: [0.2, 0.4],
        },
      },
    });

    expect(model).toMatchObject({
      calibration: {
        fitRows: [
          {
            mae: 0.8,
            mse: 1,
            n: 100,
            r2: 0.9,
            rmse: 1.2,
            target: "gdp",
          },
        ],
        gradNormHistory: [0.9, 0.4],
        lossHistory: [3, 2, 1],
        params: [
          {
            ciLower: 0.2,
            ciUpper: 0.4,
            name: "beta",
            value: 0.3,
          },
        ],
        series: [
          {
            points: [
              { fitted: 1.1, observed: 1, step: 0 },
              { fitted: 2.1, observed: 2, step: 1 },
            ],
            target: "gdp",
          },
        ],
        totalLoss: 0.25,
        uncertaintyMethod: "bootstrap",
        uncertaintyParams: ["seed", "2"],
      },
      metrics: [
        expect.objectContaining({
          formatted: "+0.25",
          key: "total_loss",
          label: "Total Loss",
        }),
      ],
      sourceKind: "calibration_report",
    });
  });

  it("normalizes uncertainty envelopes and scientist result payloads", () => {
    const envelope = normalizeSimulationPayload("ir.uncertainty_envelope", {
      confidence_interval: [1.2, 1.8],
      confidence_level: "0.95",
      interval_semantics: "central",
      point_estimate: "1.5",
      propagation_method: "bootstrap",
      source: "monte_carlo",
    });

    expect(envelope).toMatchObject({
      envelope: {
        ciLevel: 0.95,
        ciLower: 1.2,
        ciUpper: 1.8,
        intervalSemantics: "central",
        pointEstimate: 1.5,
        propagationMethod: "bootstrap",
        source: "monte_carlo",
      },
      sourceKind: "uncertainty_envelope",
    });

    const scientist = normalizeSimulationPayload(
      "scientist.simulation_results",
      {
        custom_delta: 2.5,
      },
    );

    expect(scientist).toMatchObject({
      metrics: [
        expect.objectContaining({
          formatted: "+2.50",
          key: "custom_delta",
          label: "Custom Delta",
          severity: "high",
          value: 2.5,
        }),
      ],
      notes: ["No time series arrays were detected."],
      sourceKind: "scientist.simulation_results",
    });
  });

  it("adds empty-state notes for ref-only simulation artifacts", () => {
    expect(
      normalizeSimulationPayload("foundry.simulation_result", {
        artifact_ref: "artifact-1",
      }),
    ).toMatchObject({
      metrics: [],
      notes: [
        "SimulationResult mostly stores refs; inspect linked artifacts for full metrics and charts.",
        "No numeric metrics were detected in this payload.",
        "No time series arrays were detected.",
      ],
      sourceKind: "foundry.simulation_result",
    });
    expect(normalizeSimulationPayload("foundry.metrics", null)).toBeNull();
  });
});
