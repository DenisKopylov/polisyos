import {
  BookOpen,
  ExternalLink,
  FileText,
  GitBranch,
  MapPinned,
  Scale,
  ShieldAlert,
  ScrollText,
  ShieldCheck,
} from "lucide-react";

import type { SignedPublicDecisionPacket } from "@/features/runs/domain/publicationPacket";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn, formatDate, formatNumber } from "@/shared/lib/utils";
import { Quantity } from "@/shared/ui/quantity";
import { TimeSemanticsLabel } from "@/shared/ui/temporal/TimeSemanticsLabel";
import { Badge, Button } from "@polisyos/atlas-ui";

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
          <Badge
            data-kind="neutral"
            data-testid="frontend-integrity-signature-token"
            kind="neutral"
            title={packet.trustFraming.integritySignatureNotice.authorityCaveat}
          >
            {packet.signature}
          </Badge>
          <span
            className="flex flex-wrap gap-2"
            data-testid="publication-projection-semantics"
          >
            <Badge kind="neutral">
              {packet.projectionSemantics.primaryDisplayState.label}
            </Badge>
            <Badge kind="neutral">
              {packet.projectionSemantics.authorityRole ??
                t("common.unavailable")}
            </Badge>
          </span>
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
            <Badge kind="neutral">
              {packet.decision.confidence ?? t("common.unknown")}
            </Badge>
          </div>
        </div>
      </section>

      <section
        className="border-line bg-surface/80 rounded-2xl border p-4"
        data-testid="signed-epoch-semantics"
      >
        <TimeSemanticsLabel
          epochSemantics={packet.epochSemantics}
          payloadAsOf={packet.decision.generatedAt}
        />
      </section>

      <section
        className="border-line bg-surface/80 rounded-2xl border p-4"
        data-testid="trust-framing-caveats"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="eyebrow">{t("phase35.trust.eyebrow")}</p>
            <h4 className="flex items-center gap-2">
              <ShieldAlert className="size-4" aria-hidden="true" />
              {t("phase35.trust.title")}
            </h4>
          </div>
          <Badge kind="neutral">{packet.trustFraming.authorityRole}</Badge>
        </div>
        <p className="text-muted mt-2 text-sm">
          {packet.trustFraming.visibleCaveat}
        </p>
        <p
          className="text-muted mt-1 text-sm"
          data-testid="trust-framing-closeout-caveat"
        >
          {packet.trustFraming.closeoutAuthorityCaveat}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {packet.trustFraming.mayNotBeUsedFor.map((authority) => (
            <Badge key={authority} kind="neutral">
              {authority}
            </Badge>
          ))}
        </div>
        <article
          className="border-line bg-background/55 mt-4 rounded-xl border p-3"
          data-kind="neutral"
          data-testid="frontend-integrity-signature-notice"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">
              {packet.trustFraming.integritySignatureNotice.label}
            </p>
            <Badge data-kind="neutral" kind="neutral">
              {packet.trustFraming.integritySignatureNotice.badge}
            </Badge>
          </div>
          <p className="text-muted mt-1 text-sm">
            {packet.trustFraming.integritySignatureNotice.authorityCaveat}
          </p>
          <p className="text-muted mt-2 font-mono text-xs">
            {packet.trustFraming.integritySignatureNotice.signatureCue}
          </p>
        </article>
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
                  <Badge kind="neutral">{node.kind}</Badge>
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
                  <span data-quantity-metric-id={item.score.metric_id}>
                    <Quantity
                      value={item.score}
                      precision={2}
                      variant="dense"
                    />
                  </span>
                </div>
                <p className="text-muted mt-2 font-mono text-xs">
                  {item.rung ? `${item.rung} / ` : ""}
                  {item.targetRef}
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
              <span data-quantity-metric-id={explanation.quantity.metric_id}>
                <Quantity value={explanation.quantity} variant="dense" />
              </span>
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
              data-interaction-state={packet.coverageCaveat.caveatState.label}
              kind="neutral"
            >
              {t(
                `phase35.coverage.status.${packet.coverageCaveat.caveatState.label}`,
              )}
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
                    data-interaction-state={region.displayState.label}
                    kind="neutral"
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
            <Badge data-kind="neutral" kind="neutral">
              {t("common.unknown")}
            </Badge>
          </div>
          <p className="text-muted mt-2 text-sm">
            {packet.thresholdContract.calibrationCaveat}
          </p>
          <div
            className="compact-metric mt-4"
            data-testid="threshold-evaluation-unavailable"
          >
            <span>{t("common.unknown")}</span>
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
