import { useMemo } from "react";

import type { TrinityDiffSummary } from "../../lib/domain/trinity";
import { diffTrinityBundles } from "../../lib/domain/trinity";

type TrinityDiffProps = {
  currentPayload: unknown;
  previousPayload: unknown | null;
  previousTitle?: string;
};

function hasChanges(diff: TrinityDiffSummary): boolean {
  return (
    diff.addedInterventions.length > 0
    || diff.removedInterventions.length > 0
    || diff.changedInterventions.length > 0
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
      <div className="rounded-xl border border-dashed border-line bg-canvas/40 p-3 text-sm text-muted">
        Trinity diff unavailable: {previousTitle} not found in payload.
      </div>
    );
  }

  if (!diff) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-canvas/40 p-3 text-sm text-muted">
        Trinity diff unavailable: unable to parse one of bundles.
      </div>
    );
  }

  if (!hasChanges(diff)) {
    return (
      <div className="rounded-xl border border-line bg-success/10 p-3 text-sm text-success">
        No intervention-level changes detected versus {previousTitle}.
      </div>
    );
  }

  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div className="rounded-xl border border-line p-3">
        <p className="mb-2 text-xs font-semibold uppercase text-muted">Added</p>
        {diff.addedInterventions.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {diff.addedInterventions.map((id) => (
              <li key={id} className="font-mono">
                + {id}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">None</p>
        )}
      </div>

      <div className="rounded-xl border border-line p-3">
        <p className="mb-2 text-xs font-semibold uppercase text-muted">Removed</p>
        {diff.removedInterventions.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {diff.removedInterventions.map((id) => (
              <li key={id} className="font-mono">
                - {id}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">None</p>
        )}
      </div>

      <div className="rounded-xl border border-line p-3">
        <p className="mb-2 text-xs font-semibold uppercase text-muted">Changed Params</p>
        {diff.changedInterventions.length > 0 ? (
          <ul className="space-y-2 text-sm">
            {diff.changedInterventions.map((item) => (
              <li key={item.id}>
                <p className="font-mono">{item.id}</p>
                <p className="text-xs text-muted">{item.changedParams.join(", ")}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">None</p>
        )}
      </div>
    </div>
  );
}
