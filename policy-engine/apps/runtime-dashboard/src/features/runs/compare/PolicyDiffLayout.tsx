import {
  useCallback,
  useRef,
  useState,
  type ReactNode,
  type UIEvent,
} from "react";
import { Link2Off, LinkIcon } from "lucide-react";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Button } from "@/shared/ui";

type PolicyDiffLayoutProps = {
  leftPane: ReactNode;
  deltaRail: ReactNode;
  rightPane: ReactNode;
};

export function PolicyDiffLayout({
  deltaRail,
  leftPane,
  rightPane,
}: PolicyDiffLayoutProps) {
  const { t } = useI18n();
  const [syncScroll, setSyncScroll] = useState(true);
  const leftRef = useRef<HTMLDivElement | null>(null);
  const rightRef = useRef<HTMLDivElement | null>(null);
  const syncingRef = useRef(false);

  const syncPeer = useCallback(
    (event: UIEvent<HTMLDivElement>, side: "left" | "right") => {
      if (!syncScroll || syncingRef.current) {
        return;
      }
      const source = event.currentTarget;
      const target = side === "left" ? rightRef.current : leftRef.current;
      if (!target) {
        return;
      }
      const maxSource = source.scrollHeight - source.clientHeight;
      const maxTarget = target.scrollHeight - target.clientHeight;
      const ratio = maxSource > 0 ? source.scrollTop / maxSource : 0;
      syncingRef.current = true;
      target.scrollTop = ratio * Math.max(maxTarget, 0);
      requestAnimationFrame(() => {
        syncingRef.current = false;
      });
    },
    [syncScroll],
  );

  return (
    <section
      className="space-y-3"
      aria-label={t("pages.runs.policyDiff.layoutLabel")}
    >
      <div className="flex justify-end">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          leading={
            syncScroll ? (
              <LinkIcon className="size-4" aria-hidden="true" />
            ) : (
              <Link2Off className="size-4" aria-hidden="true" />
            )
          }
          onClick={() => setSyncScroll((value) => !value)}
          aria-pressed={syncScroll}
        >
          {syncScroll
            ? t("pages.runs.policyDiff.syncedScroll")
            : t("pages.runs.policyDiff.independentScroll")}
        </Button>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(7.5rem,10rem)_minmax(0,1fr)]">
        <div
          ref={leftRef}
          data-testid="policy-diff-left-pane"
          className="max-h-[720px] min-h-[360px] overflow-auto"
          onScroll={(event) => syncPeer(event, "left")}
        >
          {leftPane}
        </div>
        <div className="lg:sticky lg:top-28 lg:self-start">{deltaRail}</div>
        <div
          ref={rightRef}
          data-testid="policy-diff-right-pane"
          className="max-h-[720px] min-h-[360px] overflow-auto"
          onScroll={(event) => syncPeer(event, "right")}
        >
          {rightPane}
        </div>
      </div>
    </section>
  );
}
