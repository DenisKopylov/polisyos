import type { RunLaunchResponse } from "@polisyos/runtime-api-client";
import type { BadgeTone } from "@polisyos/atlas-ui";

const LAUNCH_STATUS_TONE: Record<RunLaunchResponse["status"], BadgeTone> = {
  accepted: "ok",
  rejected: "fail",
};

export function launchStatusTone(
  status: RunLaunchResponse["status"],
): BadgeTone {
  return LAUNCH_STATUS_TONE[status];
}
