import type { DecisionGrade } from "@polisyos/runtime-api-client";
import { z } from "zod";

const decisionGradePolicyByGrade = {
  unsupported: { simulationRequiresCalibration: false },
  descriptive_only: { simulationRequiresCalibration: false },
  advisory_admissible: { simulationRequiresCalibration: true },
  decision_admissible: { simulationRequiresCalibration: true },
} as const satisfies Record<
  DecisionGrade,
  Readonly<{ simulationRequiresCalibration: boolean }>
>;

/** Validate a wire decision grade against the generated Runtime vocabulary. */
export const decisionGradeSchema = z
  .string()
  .refine(isDecisionGrade, "unknown generated decision grade");

/** Return whether the owner grade requires calibration for simulation evidence. */
export function simulationGradeRequiresCalibration(
  value: string | null | undefined,
): boolean {
  return (
    value != null &&
    Object.hasOwn(decisionGradePolicyByGrade, value) &&
    decisionGradePolicyByGrade[value as DecisionGrade]
      .simulationRequiresCalibration
  );
}

/** Preserve an unknown wire value as an unrecognized owner grade. */
export function isDecisionGrade(value: string): value is DecisionGrade {
  return Object.hasOwn(decisionGradePolicyByGrade, value);
}
