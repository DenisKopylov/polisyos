import { useMemo } from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import type { TrinityDiffSummary } from "@/lib/domain/trinity";
import { diffTrinityBundles } from "@/lib/domain/trinity";

type TrinityDiffProps = {
  currentPayload: unknown;
  previousPayload: unknown;
  previousTitle?: string;
};

function hasChanges(diff: TrinityDiffSummary): boolean {
  return (
    diff.addedInterventions.length > 0 ||
    diff.removedInterventions.length > 0 ||
    diff.changedInterventions.length > 0
  );
}

export default function TrinityDiff({
  currentPayload,
  previousPayload,
  previousTitle,
}: TrinityDiffProps) {
  const { t } = useI18n();
  const resolvedPreviousTitle =
    previousTitle ?? t("pages.artifacts.trinity.previousBundle");
  const diff = useMemo(() => {
    if (!previousPayload) {
      return null;
    }
    return diffTrinityBundles(currentPayload, previousPayload);
  }, [currentPayload, previousPayload]);

  if (!previousPayload) {
    return (
      <div className="bg-canvas/40 border-line text-muted rounded-xl border border-dashed p-3 text-sm">
        {t("pages.artifacts.trinity.diffUnavailableNotFound", {
          title: resolvedPreviousTitle,
        })}
      </div>
    );
  }

  if (!diff) {
    return (
      <div className="bg-canvas/40 border-line text-muted rounded-xl border border-dashed p-3 text-sm">
        {t("pages.artifacts.trinity.diffUnavailableParse")}
      </div>
    );
  }

  if (!hasChanges(diff)) {
    return (
      <div className="bg-success/10 border-line text-success rounded-xl border p-3 text-sm">
        {t("pages.artifacts.trinity.noChanges", {
          title: resolvedPreviousTitle,
        })}
      </div>
    );
  }

  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div className="border-line rounded-xl border p-3">
        <p className="text-muted mb-2 text-xs font-semibold uppercase">
          {t("pages.artifacts.trinity.added")}
        </p>
        {diff.addedInterventions.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {diff.addedInterventions.map((id) => (
              <li key={id} className="font-mono">
                + {id}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted text-sm">{t("common.none")}</p>
        )}
      </div>

      <div className="border-line rounded-xl border p-3">
        <p className="text-muted mb-2 text-xs font-semibold uppercase">
          {t("pages.artifacts.trinity.removed")}
        </p>
        {diff.removedInterventions.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {diff.removedInterventions.map((id) => (
              <li key={id} className="font-mono">
                - {id}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted text-sm">{t("common.none")}</p>
        )}
      </div>

      <div className="border-line rounded-xl border p-3">
        <p className="text-muted mb-2 text-xs font-semibold uppercase">
          {t("pages.artifacts.trinity.changedParams")}
        </p>
        {diff.changedInterventions.length > 0 ? (
          <ul className="space-y-2 text-sm">
            {diff.changedInterventions.map((item) => (
              <li key={item.id}>
                <p className="font-mono">{item.id}</p>
                <p className="text-muted text-xs">
                  {item.changedParams.join(", ")}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted text-sm">{t("common.none")}</p>
        )}
      </div>
    </div>
  );
}
