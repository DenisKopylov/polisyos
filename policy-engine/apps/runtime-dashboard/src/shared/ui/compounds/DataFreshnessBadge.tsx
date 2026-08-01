import type { ProjectionFreshness } from "@polisyos/runtime-api-client";
import { Badge, type BadgeTone } from "@polisyos/atlas-ui";

import { useI18n } from "@/shared/i18n/LocaleProvider";

type DataFreshnessBadgeProps = {
  freshness?: ProjectionFreshness | null;
};

const FRESHNESS_TONE: Record<ProjectionFreshness["state"], BadgeTone> = {
  artifact_missing: "warn",
  invalid_source: "fail",
  observed: "info",
};

/** Displays producer-observed freshness without deriving a cache-age state. */
export function DataFreshnessBadge({ freshness }: DataFreshnessBadgeProps) {
  const { t } = useI18n();
  if (!freshness) {
    return (
      <Badge data-freshness-state="unknown" kind="outline">
        {t("common.unknown")}
      </Badge>
    );
  }

  const temporalDescription = `Source as of: ${freshness.source_as_of ?? "unknown"}; observed at: ${freshness.observed_at}`;
  return (
    <span className="inline-flex">
      <Badge
        className="tracking-normal normal-case"
        data-freshness-basis={freshness.basis}
        data-freshness-state={freshness.state}
        data-observed-at={freshness.observed_at}
        data-source-as-of={freshness.source_as_of ?? undefined}
        kind={FRESHNESS_TONE[freshness.state]}
        title={temporalDescription}
      >
        {freshness.state}
      </Badge>
      <span className="sr-only">{temporalDescription}</span>
    </span>
  );
}
