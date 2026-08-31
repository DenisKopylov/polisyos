import {
  epochNonreceipt,
  type EpochSemantics,
} from "@/shared/lib/domain/epochSemantics";

export type ShareKind = "run" | "compare" | "scenario";
export type ShareTrustStatus =
  | "verified"
  | "pending"
  | "stale"
  | "disputed"
  | "untraced";

export type PublicShareSummary = {
  epochSemantics: EpochSemantics;
  kind: ShareKind;
  title: string;
  subtitle?: string;
  keyQuantity: {
    label: string;
    value: string;
    unit?: string;
  };
  trustStatus: ShareTrustStatus;
  temporalScope: {
    validAt?: string | null;
    txAt?: string | null;
    branch?: string | null;
    scenarioId?: string | null;
  };
  state: "draft" | "verified";
  href: string;
  summary?: string;
};

export const runShareFixture: PublicShareSummary = {
  epochSemantics: epochNonreceipt(),
  href: "https://polisyos.local/runs/R_core_api_001?trust=compact",
  keyQuantity: {
    label: "Decision score",
    unit: "ratio",
    value: "0.67",
  },
  kind: "run",
  state: "draft",
  subtitle: "Run R_core_api_001",
  summary: "Governance requires review before this decision can be reused.",
  temporalScope: {
    txAt: "2026-04-16T09:20:00Z",
    validAt: "2026-04-15T12:00:00Z",
  },
  title: "Reject or replan",
  trustStatus: "untraced",
};

export const compareShareFixture: PublicShareSummary = {
  ...runShareFixture,
  href: "https://polisyos.local/compare/R_core_api_001/R_core_api_002",
  keyQuantity: {
    label: "Employment delta",
    unit: "pp",
    value: "+1.4",
  },
  kind: "compare",
  state: "verified",
  subtitle: "Baseline vs latest governed run",
  title: "Policy diff",
  trustStatus: "verified",
};

export const scenarioShareFixture: PublicShareSummary = {
  ...runShareFixture,
  href: "https://polisyos.local/scenarios/scn_rate_cut_25bps",
  keyQuantity: {
    label: "Scenario delta",
    unit: "ratio",
    value: "+0.03",
  },
  kind: "scenario",
  state: "draft",
  subtitle: "Actual + Scenario",
  temporalScope: {
    scenarioId: "scn_rate_cut_25bps",
    txAt: "2026-04-16T09:20:00Z",
    validAt: "2026-04-15T12:00:00Z",
  },
  title: "Rate cut 25 bps",
  trustStatus: "pending",
};

export const emailFixtures = {
  compare: compareShareFixture,
  run: runShareFixture,
  scenario: scenarioShareFixture,
} as const;
