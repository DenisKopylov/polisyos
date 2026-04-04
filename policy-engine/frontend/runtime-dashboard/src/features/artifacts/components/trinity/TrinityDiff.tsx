import { useMemo } from "react";

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
  previousTitle = "previous bundle",
}: TrinityDiffProps) {
  const diff = useMemo(() => {
    if (!previousPayload) {
      return null;
    }
    return diffTrinityBundles(currentPayload, previousPayload);
  }, [currentPayload, previousPayload]);

  if (!previousPayload) {
    return (
      <div className="bg-canvas/40 border-line text-muted rounded-xl border border-dashed p-3 text-sm">
        Trinity diff unavailable: {previousTitle} not found in payload.
      </div>
    );
  }

  if (!diff) {
    return (
      <div className="bg-canvas/40 border-line text-muted rounded-xl border border-dashed p-3 text-sm">
        Trinity diff unavailable: unable to parse one of bundles.
      </div>
    );
  }

  if (!hasChanges(diff)) {
    return (
      <div className="bg-success/10 border-line text-success rounded-xl border p-3 text-sm">
        No intervention-level changes detected versus {previousTitle}.
      </div>
    );
  }

  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div className="border-line rounded-xl border p-3">
        <p className="text-muted mb-2 text-xs font-semibold uppercase">Added</p>
        {diff.addedInterventions.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {diff.addedInterventions.map((id) => (
              <li key={id} className="font-mono">
                + {id}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted text-sm">None</p>
        )}
      </div>

      <div className="border-line rounded-xl border p-3">
        <p className="text-muted mb-2 text-xs font-semibold uppercase">
          Removed
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
          <p className="text-muted text-sm">None</p>
        )}
      </div>

      <div className="border-line rounded-xl border p-3">
        <p className="text-muted mb-2 text-xs font-semibold uppercase">
          Changed Params
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
          <p className="text-muted text-sm">None</p>
        )}
      </div>
    </div>
  );
}
