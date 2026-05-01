import type { ConnectorCharacterCard } from "../domain/productionSlice";

import { useI18n } from "@/i18n/LocaleProvider";
import {
  formatDate,
  formatDuration,
  formatNumber,
  formatPercent,
} from "@/lib/utils";
import { Badge, Card, EmptyState } from "@/shared/ui";

function burnKind(burn: number) {
  if (burn >= 0.85) return "fail";
  if (burn >= 0.6) return "warn";
  return "ok";
}

export function ConnectorCharacterCards({
  cards,
}: {
  cards: ConnectorCharacterCard[];
}) {
  const { t } = useI18n();

  if (cards.length === 0) {
    return (
      <Card data-testid="connector-character-cards">
        <EmptyState
          title={t("phase32.connectors.emptyTitle")}
          body={t("phase32.connectors.emptyBody")}
        />
      </Card>
    );
  }

  return (
    <Card className="space-y-4" data-testid="connector-character-cards">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("phase32.connectors.eyebrow")}</p>
          <h3>{t("phase32.connectors.title")}</h3>
          <p className="topbar-subtitle mt-2">{t("phase32.connectors.body")}</p>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <article
            key={card.connectorId}
            className="border-line bg-surface/80 space-y-4 rounded-2xl border p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-base font-semibold">{card.connectorId}</h4>
                <p className="text-muted mt-1 text-xs">
                  {t("phase32.connectors.namespaceVersion", {
                    namespace: card.namespace,
                    version: card.version,
                  })}
                </p>
              </div>
              <Badge kind={card.loaded ? "ok" : "fail"}>
                {card.loaded
                  ? t("phase32.connectors.loaded")
                  : t("phase32.connectors.unavailable")}
              </Badge>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="compact-metric">
                <span>{t("phase32.connectors.latencyP50")}</span>
                <strong>{formatDuration(card.latencyP50Ms)}</strong>
              </div>
              <div className="compact-metric">
                <span>{t("phase32.connectors.latencyP95")}</span>
                <strong>{formatDuration(card.latencyP95Ms)}</strong>
              </div>
              <div className="compact-metric">
                <span>{t("phase32.connectors.cost")}</span>
                <strong>{card.costTier}</strong>
              </div>
              <div className="compact-metric">
                <span>{t("phase32.connectors.retry")}</span>
                <strong>{card.retryProfile}</strong>
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-muted text-xs font-semibold uppercase">
                  {t("phase32.connectors.errorBudget")}
                </span>
                <Badge kind={burnKind(card.errorBudgetBurn)}>
                  {formatPercent(card.errorBudgetBurn, {
                    maximumFractionDigits: 0,
                  })}
                </Badge>
              </div>
              <div className="bg-line h-2 overflow-hidden rounded-full">
                <div
                  className="bg-accent h-full rounded-full"
                  style={{
                    width: `${Math.round(card.errorBudgetBurn * 100)}%`,
                  }}
                />
              </div>
            </div>

            <div className="text-muted grid gap-1 text-xs">
              <span>
                {t("phase32.connectors.datasets", {
                  value: formatNumber(card.datasetCount),
                })}
              </span>
              <span>
                {t("phase32.connectors.profiles", {
                  value: formatNumber(card.profileCount),
                })}
              </span>
              <span>
                {t("phase32.connectors.facts", {
                  value: formatNumber(card.factsThroughConnector),
                })}
              </span>
              <span>
                {t("phase32.connectors.lastGreen", {
                  date: card.lastGreenPull
                    ? formatDate(card.lastGreenPull)
                    : t("common.unavailable"),
                })}
              </span>
            </div>
          </article>
        ))}
      </div>
    </Card>
  );
}
