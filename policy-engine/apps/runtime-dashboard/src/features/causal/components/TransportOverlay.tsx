import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import type { CausalEdgeData } from "../types";

type TransportOverlayProps = {
  edges: CausalEdgeData[];
  className?: string;
};

export function TransportOverlay({ edges, className }: TransportOverlayProps) {
  const { t } = useI18n();
  const transportable = edges.filter((e) => e.transportable);
  const nonTransportable = edges.filter((e) => !e.transportable);

  return (
    <div
      className={cn(
        "bg-surface/90 border-line rounded-xl border p-3 text-xs backdrop-blur-sm",
        className,
      )}
    >
      <p className="mb-2 font-semibold">{t("causal.transportOverlay.title")}</p>
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1">
            <span
              className="inline-block size-2.5 rounded-full"
              style={{ background: "var(--chart-secondary)" }}
            />
            <span
              className="inline-block h-0.5 w-4"
              style={{ background: "var(--chart-primary)" }}
            />
          </span>
          <span>
            {t("causal.transportOverlay.transportable")}{" "}
            <span className="font-bold text-[var(--chart-secondary)]">
              {transportable.length}
            </span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-0.5 w-5 opacity-30"
            style={{ background: "var(--chart-neutral)" }}
          />
          <span className="text-muted">
            {t("causal.transportOverlay.nonTransportableCount", {
              count: nonTransportable.length,
            })}
          </span>
        </div>
      </div>
      {transportable.length > 0 && (
        <div className="mt-2 space-y-0.5">
          {transportable.map((e) => (
            <p key={e.id} className="text-muted truncate">
              {e.source} {"->"} {e.target}
              {e.methodology && (
                <span className="ml-1 opacity-60">({e.methodology})</span>
              )}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
