import {
  BookOpen,
  ExternalLink,
  FileText,
  GitBranch,
  MapPinned,
  Scale,
  ScrollText,
  ShieldCheck,
} from "lucide-react";

import type {
  ArgumentMapNode,
  ConfidenceLadderItem,
  SignedPublicDecisionPacket,
} from "@/features/runs/domain/publicationPacket";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn, formatDate, formatNumber } from "@/lib/utils";
import { Badge, Button } from "@/shared/ui";

function nodeKind(node: ArgumentMapNode) {
  if (node.status === "certified") {
    return "ok";
  }
  if (node.status === "open") {
    return "warn";
  }
  return "fail";
}

function ladderKind(item: ConfidenceLadderItem) {
  if (item.score >= 0.7) {
    return "ok";
  }
  if (item.score >= 0.4) {
    return "warn";
  }
  return "fail";
}

export function PublicationPacketPanel({
  packet,
  publicMode = false,
}: {
  packet: SignedPublicDecisionPacket;
  publicMode?: boolean;
}) {
  const { t } = useI18n();

  return (
    <section className="space-y-4" data-testid="publication-packet-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("phase35.eyebrow")}</p>
          <h3>{t("phase35.title")}</h3>
          <p className="topbar-subtitle mt-2">
            {publicMode ? t("phase35.publicBody") : t("phase35.body")}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Badge kind="ok">{packet.signature}</Badge>
          {!publicMode ? (
            <Button href={packet.publicUrlPath} variant="ghost">
              <ExternalLink className="size-4" aria-hidden="true" />
              {t("phase35.openPublicViewer")}
            </Button>
          ) : null}
        </div>
      </div>

      <section
        className="border-line bg-surface/80 rounded-2xl border p-4"
        data-testid="signed-public-summary"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="eyebrow">{t("phase35.publicSummary.eyebrow")}</p>
            <h4>{packet.decision.headline}</h4>
            <p className="text-muted mt-2 text-sm">
              {packet.decision.policySummary}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge kind="neutral">{packet.packetHash}</Badge>
            <Badge kind={packet.decision.confidence === "HIGH" ? "ok" : "warn"}>
              {packet.decision.confidence}
            </Badge>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="argument-map-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase35.argument.eyebrow")}</p>
              <h4 className="flex items-center gap-2">
                <GitBranch className="size-4" aria-hidden="true" />
                {t("phase35.argument.title")}
              </h4>
            </div>
            <Badge kind="neutral">
              {formatNumber(packet.argumentMap.nodes.length)}
            </Badge>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-2">
            {packet.argumentMap.nodes.map((node) => (
              <article
                key={node.id}
                className={cn(
                  "border-line bg-background/55 rounded-xl border p-3",
                  node.id === packet.argumentMap.rootClaimId &&
                    "border-accent/40 bg-accent/10",
                )}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">{node.label}</p>
                  <Badge kind={nodeKind(node)}>
                    {t(`phase35.argument.status.${node.status}`)}
                  </Badge>
                </div>
                <p className="text-muted mt-1 text-sm">{node.detail}</p>
                <p className="text-muted mt-2 font-mono text-xs">
                  {node.kind} / {node.refs.join(", ") || "-"}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="confidence-ladder-panel"
        >
          <div>
            <p className="eyebrow">{t("phase35.ladder.eyebrow")}</p>
            <h4 className="flex items-center gap-2">
              <ShieldCheck className="size-4" aria-hidden="true" />
              {t("phase35.ladder.title")}
            </h4>
          </div>
          <div className="mt-4 space-y-2">
            {packet.confidenceLadder.map((item) => (
              <article
                key={item.id}
                className="border-line bg-background/55 rounded-xl border p-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">{item.label}</p>
                    <p className="text-muted mt-1 text-sm">{item.reason}</p>
                  </div>
                  <Badge kind={ladderKind(item)}>
                    {formatNumber(item.score, {
                      maximumFractionDigits: 2,
                    })}
                  </Badge>
                </div>
                <p className="text-muted mt-2 font-mono text-xs">
                  {t(`phase35.ladder.rung.${item.rung}`)} / {item.targetRef}
                </p>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section
        className="border-line bg-surface/80 rounded-2xl border p-4"
        data-testid="deterministic-explanations-panel"
      >
        <div>
          <p className="eyebrow">{t("phase35.explanations.eyebrow")}</p>
          <h4 className="flex items-center gap-2">
            <BookOpen className="size-4" aria-hidden="true" />
            {t("phase35.explanations.title")}
          </h4>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {packet.deterministicExplanations.map((explanation) => (
            <article
              key={explanation.id}
              className="border-line bg-background/55 rounded-xl border p-3"
            >
              <p className="font-semibold">{explanation.label}</p>
              <p className="text-muted mt-1 text-sm">{explanation.narrative}</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                {explanation.parts.map((part) => (
                  <div key={part.label} className="compact-metric">
                    <span>{part.label}</span>
                    <strong>
                      {formatNumber(part.contributionShare * 100, {
                        maximumFractionDigits: 0,
                      })}
                      %
                    </strong>
                  </div>
                ))}
              </div>
              <ol className="mt-3 space-y-1 text-xs">
                {explanation.derivationPath.map((step) => (
                  <li key={step.id} className="text-muted">
                    <span className="font-mono">{step.kind}</span> /{" "}
                    {step.label}
                  </li>
                ))}
              </ol>
            </article>
          ))}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="citation-model-card-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase35.modelCard.eyebrow")}</p>
              <h4 className="flex items-center gap-2">
                <FileText className="size-4" aria-hidden="true" />
                {packet.modelCard.title}
              </h4>
            </div>
            <Badge kind="neutral">{packet.modelCard.modelId}</Badge>
          </div>
          <div className="mt-4 space-y-2">
            {packet.modelCard.sections.map((section) => (
              <article key={section.id} className="border-line border-t pt-2">
                <p className="font-semibold">{section.title}</p>
                <p className="text-muted mt-1 text-sm">{section.body}</p>
                <p className="text-muted mt-1 font-mono text-xs">
                  {section.provenanceRefs.join(", ") || "-"}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="coverage-caveat-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase35.coverage.eyebrow")}</p>
              <h4 className="flex items-center gap-2">
                <MapPinned className="size-4" aria-hidden="true" />
                {t("phase35.coverage.title")}
              </h4>
            </div>
            <Badge
              kind={packet.coverageCaveat.status === "clear" ? "ok" : "warn"}
            >
              {t(`phase35.coverage.status.${packet.coverageCaveat.status}`)}
            </Badge>
          </div>
          <p className="text-muted mt-2 text-sm">
            {packet.coverageCaveat.summary}
          </p>
          <div className="mt-4 space-y-2">
            {packet.coverageCaveat.regions.map((region) => (
              <article
                key={region.label}
                className="border-line bg-background/55 rounded-xl border p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">{region.label}</p>
                  <Badge
                    kind={
                      region.status === "high"
                        ? "ok"
                        : region.status === "medium"
                          ? "warn"
                          : "fail"
                    }
                  >
                    {formatNumber(region.density, {
                      maximumFractionDigits: 2,
                    })}
                  </Badge>
                </div>
                <p className="text-muted mt-1 text-sm">{region.caveat}</p>
              </article>
            ))}
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="threshold-contract-panel"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">{t("phase35.threshold.eyebrow")}</p>
              <h4 className="flex items-center gap-2">
                <Scale className="size-4" aria-hidden="true" />
                {t("phase35.threshold.title")}
              </h4>
            </div>
            <Badge kind="neutral">
              {formatNumber(packet.thresholdContract.threshold, {
                maximumFractionDigits: 2,
              })}
            </Badge>
          </div>
          <p className="text-muted mt-2 text-sm">
            {packet.thresholdContract.calibrationCaveat}
          </p>
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <div className="compact-metric">
              <span>{t("phase35.threshold.near")}</span>
              <strong>
                {formatNumber(packet.thresholdContract.nearLineCount)}
              </strong>
            </div>
            <div className="compact-metric">
              <span>{t("phase35.threshold.above")}</span>
              <strong>
                {formatNumber(packet.thresholdContract.aboveCount)}
              </strong>
            </div>
            <div className="compact-metric">
              <span>{t("phase35.threshold.below")}</span>
              <strong>
                {formatNumber(packet.thresholdContract.belowCount)}
              </strong>
            </div>
          </div>
          <div className="mt-3 space-y-2">
            {packet.thresholdContract.edgeCases.map((edge) => (
              <div
                key={edge.id}
                className="border-line bg-background/55 flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3 text-sm"
              >
                <span>{edge.label}</span>
                <Badge kind={edge.side === "above" ? "ok" : "warn"}>
                  {edge.side} {formatNumber(edge.distance)}
                </Badge>
              </div>
            ))}
          </div>
        </section>

        <section
          className="border-line bg-surface/80 rounded-2xl border p-4"
          data-testid="bureaucratic-forms-panel"
        >
          <div>
            <p className="eyebrow">{t("phase35.forms.eyebrow")}</p>
            <h4 className="flex items-center gap-2">
              <ScrollText className="size-4" aria-hidden="true" />
              {t("phase35.forms.title")}
            </h4>
          </div>
          <div className="mt-4 space-y-2">
            {packet.bureaucraticForms.map((form) => (
              <article
                key={form.genre}
                className="border-line bg-background/55 rounded-xl border p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">{form.label}</p>
                  <Badge kind="neutral">{form.locale}</Badge>
                </div>
                <p className="text-muted mt-1 text-sm">
                  {form.legalOrder.join(" -> ")}
                </p>
                <p className="text-muted mt-1 font-mono text-xs">
                  {form.astPatchContract}
                </p>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section
        className="border-line bg-surface/80 rounded-2xl border p-4"
        data-testid="glossary-lens-panel"
      >
        <div>
          <p className="eyebrow">{t("phase35.glossary.eyebrow")}</p>
          <h4>{t("phase35.glossary.title")}</h4>
        </div>
        <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {packet.glossary.map((term) => (
            <article
              key={term.term}
              className="border-line bg-background/55 rounded-xl border p-3"
            >
              <p className="font-semibold">{term.term}</p>
              <p className="text-muted mt-1 text-sm">{term.definition}</p>
              <p className="text-muted mt-2 text-xs">
                {term.owner} / {formatDate(term.fixedAt)} / {term.provenanceRef}
              </p>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
