import type { ReactNode } from "react";

import type {
  AvailableConfidenceLedgerRiskSpendPacket,
  CertificateRouteRow,
  ConditionalDeltaAmount,
  InstrumentDefinitionRow,
  InstrumentInstanceRow,
  ObligationClassRiskSpend,
} from "@polisyos/runtime-api-client";
import { Button, Card, EmptyState } from "@polisyos/atlas-ui";

import type { ConfidenceLedgerRiskSpendProjection } from "@/features/runs/api/useConfidenceLedgerRiskSpend";
import {
  confidenceLedgerPromotionBlockers,
  orderedConfidenceLedgerActualRows,
  type ConfidenceLedgerRiskSpendPacket,
} from "@/features/runs/domain/confidenceLedgerRiskSpend";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { exportCapturedResponseBytes } from "@/shared/ui/dataExport";

import { ConditionalDeltaFigure } from "./ConditionalDeltaFigure";

type ConfidenceLedgerRiskSpendProps = Readonly<{
  projection: ConfidenceLedgerRiskSpendProjection;
}>;

function SemanticValue({
  field,
  value,
}: Readonly<{
  field: string;
  value: boolean | number | string | null;
}>) {
  return (
    <span
      className="font-mono text-xs break-words"
      data-confidence-leaf={field}
      data-confidence-text={`leaf.${field}`}
    >
      {value === null ? "null" : String(value)}
    </span>
  );
}

function SemanticList({
  field,
  values,
}: Readonly<{ field: string; values: readonly string[] }>) {
  if (values.length === 0) {
    return <SemanticValue field={`${field}.count`} value={0} />;
  }
  return (
    <ol className="list-decimal space-y-1 pl-5" data-confidence-list={field}>
      {values.map((value, index) => (
        <li key={`${field}-${index}-${value}`}>
          <SemanticValue field={`${field}.${index}`} value={value} />
        </li>
      ))}
    </ol>
  );
}

function DetailRow({
  label,
  children,
}: Readonly<{ label: string; children: ReactNode }>) {
  return (
    <div className="grid gap-1 py-1.5 md:grid-cols-[minmax(0,12rem)_minmax(0,1fr)]">
      <dt
        className="text-muted-foreground text-xs font-semibold tracking-wide uppercase"
        data-confidence-text={`detail.label.${label}`}
      >
        {label}
      </dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

function SemanticSection({
  children,
  section,
  title,
}: Readonly<{ children: ReactNode; section: string; title: string }>) {
  return (
    <section
      className="border-border space-y-4 border-t pt-5 first:border-t-0 first:pt-0"
      data-confidence-section={section}
    >
      <h2
        className="text-lg font-semibold"
        data-confidence-text={`section.${section}.title`}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function AmountSet({
  allocation,
  coverageEnvelope,
  overspend,
  prefix,
  remaining,
  spent,
}: Readonly<{
  allocation: ConditionalDeltaAmount;
  coverageEnvelope: AvailableConfidenceLedgerRiskSpendPacket["payload"]["coverage_envelope"];
  overspend: ConditionalDeltaAmount;
  prefix: string;
  remaining: ConditionalDeltaAmount;
  spent: ConditionalDeltaAmount;
}>) {
  const { t } = useI18n();
  return (
    <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-4">
      <ConditionalDeltaFigure
        amount={allocation}
        coverageEnvelope={coverageEnvelope}
        label={`${prefix} · ${t("pages.cycleBoard.confidenceLedger.accounting.allocation")}`}
      />
      <ConditionalDeltaFigure
        amount={spent}
        coverageEnvelope={coverageEnvelope}
        label={`${prefix} · ${t("pages.cycleBoard.confidenceLedger.accounting.spent")}`}
      />
      <ConditionalDeltaFigure
        amount={remaining}
        coverageEnvelope={coverageEnvelope}
        label={`${prefix} · ${t("pages.cycleBoard.confidenceLedger.accounting.remaining")}`}
      />
      <ConditionalDeltaFigure
        amount={overspend}
        coverageEnvelope={coverageEnvelope}
        label={`${prefix} · ${t("pages.cycleBoard.confidenceLedger.accounting.overspend")}`}
      />
    </div>
  );
}

function ActualRow({
  coverageEnvelope,
  row,
}: Readonly<{
  coverageEnvelope: AvailableConfidenceLedgerRiskSpendPacket["payload"]["coverage_envelope"];
  row: InstrumentInstanceRow;
}>) {
  const { t } = useI18n();
  return (
    <article className="border-border space-y-3 rounded-lg border p-4">
      <dl>
        <DetailRow label="instance_ref">
          <SemanticValue field="actual.instance_ref" value={row.instance_ref} />
        </DetailRow>
        <DetailRow label="certificate_role">
          <SemanticValue
            field="actual.certificate_role"
            value={row.certificate_role}
          />
        </DetailRow>
        <DetailRow label="instrument_id">
          <SemanticValue
            field="actual.instrument_id"
            value={row.instrument_id}
          />
        </DetailRow>
        <DetailRow label="instrument_family">
          <SemanticValue
            field="actual.instrument_family"
            value={row.instrument_family}
          />
        </DetailRow>
        <DetailRow label="obligation_class">
          <SemanticValue
            field="actual.obligation_class"
            value={row.obligation_class}
          />
        </DetailRow>
        <DetailRow label="execution_status">
          <SemanticValue
            field="actual.execution_status"
            value={row.execution_status}
          />
        </DetailRow>
        <DetailRow label="outcome">
          <SemanticValue field="actual.outcome" value={row.outcome} />
        </DetailRow>
        <DetailRow label="certificate_ref">
          <SemanticValue
            field="actual.certificate_ref"
            value={row.certificate_ref}
          />
        </DetailRow>
        <DetailRow label="certificate_class">
          <SemanticValue
            field="actual.certificate_class"
            value={row.certificate_class}
          />
        </DetailRow>
        <DetailRow label="certificate_route_ref">
          <SemanticValue
            field="actual.certificate_route_ref"
            value={row.certificate_route_ref}
          />
        </DetailRow>
        <DetailRow label="anytime_valid">
          <SemanticValue
            field="actual.anytime_valid"
            value={row.anytime_valid}
          />
        </DetailRow>
        <DetailRow label="eligible_for_promotion">
          <SemanticValue
            field="actual.eligible_for_promotion"
            value={row.eligible_for_promotion}
          />
        </DetailRow>
        <DetailRow label="supports_obligation">
          <SemanticValue
            field="actual.supports_obligation"
            value={row.supports_obligation}
          />
        </DetailRow>
        <DetailRow label="blocker">
          <SemanticValue field="actual.blocker" value={row.blocker} />
        </DetailRow>
        <DetailRow label="proof_profile_id">
          <SemanticValue
            field="actual.proof_profile_id"
            value={row.proof_profile_id}
          />
        </DetailRow>
        <DetailRow label="raw_runtime_refusal_source">
          <SemanticValue
            field="actual.raw_runtime_refusal_source"
            value={row.raw_runtime_refusal_source}
          />
        </DetailRow>
      </dl>
      <ConditionalDeltaFigure
        amount={row.spend}
        coverageEnvelope={coverageEnvelope}
        label={`${row.instance_ref} · ${t("pages.cycleBoard.confidenceLedger.accounting.spent")}`}
      />
    </article>
  );
}

function ClassSpendRow({
  coverageEnvelope,
  row,
}: Readonly<{
  coverageEnvelope: AvailableConfidenceLedgerRiskSpendPacket["payload"]["coverage_envelope"];
  row: ObligationClassRiskSpend;
}>) {
  return (
    <article className="border-border space-y-3 rounded-lg border p-4">
      <h3>
        <SemanticValue
          field="class.obligation_class"
          value={row.obligation_class}
        />
      </h3>
      <dl>
        <DetailRow label="check_refs">
          <SemanticList field="class.check_refs" values={row.check_refs} />
        </DetailRow>
        <DetailRow label="good_event_refs">
          <SemanticList
            field="class.good_event_refs"
            values={row.good_event_refs}
          />
        </DetailRow>
        <DetailRow label="instrument_refs">
          <SemanticList
            field="class.instrument_refs"
            values={row.instrument_refs}
          />
        </DetailRow>
      </dl>
      <AmountSet
        allocation={row.allocation}
        coverageEnvelope={coverageEnvelope}
        overspend={row.overspend_amount}
        prefix={row.obligation_class}
        remaining={row.remaining}
        spent={row.spent}
      />
    </article>
  );
}

function InstrumentDefinition({
  row,
}: Readonly<{ row: InstrumentDefinitionRow }>) {
  return (
    <article className="border-border rounded-lg border p-4">
      <dl>
        <DetailRow label="instrument_id">
          <SemanticValue
            field="definition.instrument_id"
            value={row.instrument_id}
          />
        </DetailRow>
        <DetailRow label="instrument_family">
          <SemanticValue
            field="definition.instrument_family"
            value={row.instrument_family}
          />
        </DetailRow>
        <DetailRow label="proof_profile_id">
          <SemanticValue
            field="definition.proof_profile_id"
            value={row.proof_profile_id}
          />
        </DetailRow>
        <DetailRow label="proof_kernel_id">
          <SemanticValue
            field="definition.proof_kernel_id"
            value={row.proof_kernel_id}
          />
        </DetailRow>
        <DetailRow label="guarantee_kind">
          <SemanticValue
            field="definition.guarantee_kind"
            value={row.guarantee_kind}
          />
        </DetailRow>
        <DetailRow label="certificate_roles">
          <SemanticList
            field="definition.certificate_roles"
            values={row.certificate_roles}
          />
        </DetailRow>
        <DetailRow label="anytime_valid">
          <SemanticValue
            field="definition.anytime_valid"
            value={row.anytime_valid}
          />
        </DetailRow>
        <DetailRow label="deterministic">
          <SemanticValue
            field="definition.deterministic"
            value={row.deterministic}
          />
        </DetailRow>
        <DetailRow label="permits_obligation_satisfaction">
          <SemanticValue
            field="definition.permits_obligation_satisfaction"
            value={row.permits_obligation_satisfaction}
          />
        </DetailRow>
        <DetailRow label="blocker">
          <SemanticValue field="definition.blocker" value={row.blocker} />
        </DetailRow>
      </dl>
    </article>
  );
}

function CertificateRoute({ row }: Readonly<{ row: CertificateRouteRow }>) {
  const entries = Object.entries(row) as Array<
    [keyof CertificateRouteRow, CertificateRouteRow[keyof CertificateRouteRow]]
  >;
  return (
    <article className="border-border rounded-lg border p-4">
      <dl>
        {entries.map(([field, value]) => (
          <DetailRow key={field} label={field}>
            <SemanticValue
              field={`route.${field}`}
              value={value as boolean | number | string | null}
            />
          </DetailRow>
        ))}
      </dl>
    </article>
  );
}

function AvailableRiskSpend({
  packet,
  rawPacketBytes,
}: Readonly<{
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >;
  rawPacketBytes: Uint8Array;
}>) {
  const { locale, t } = useI18n();
  const body = packet.payload;
  const actualRows = orderedConfidenceLedgerActualRows(packet);
  const promotionBlockers = confidenceLedgerPromotionBlockers(packet);
  return (
    <Card
      className="space-y-6 p-5"
      data-confidence-envelope-ref={body.coverage_envelope_ref}
      data-confidence-locale={locale}
      data-confidence-surface="risk-spend"
    >
      <SemanticSection
        section="actual-rows"
        title={t("pages.cycleBoard.confidenceLedger.sections.actualRows")}
      >
        <ol className="space-y-3" data-confidence-list="actual-rows">
          {actualRows.map((row) => (
            <li key={row.instance_ref}>
              <ActualRow coverageEnvelope={body.coverage_envelope} row={row} />
            </li>
          ))}
        </ol>
      </SemanticSection>

      <SemanticSection
        section="risk-accounting"
        title={t("pages.cycleBoard.confidenceLedger.sections.riskAccounting")}
      >
        <article className="space-y-3">
          <h3>
            <SemanticValue field="scope.scope_id" value={body.scope_id} />
          </h3>
          <AmountSet
            allocation={body.scope_total_risk_spend.allocation}
            coverageEnvelope={body.coverage_envelope}
            overspend={body.scope_total_risk_spend.overspend_amount}
            prefix={t(
              "pages.cycleBoard.confidenceLedger.accounting.scopeTotal",
            )}
            remaining={body.scope_total_risk_spend.remaining}
            spent={body.scope_total_risk_spend.spent}
          />
        </article>
        <ol className="space-y-4" data-confidence-list="class-spend">
          {body.obligation_class_risk_spend.map((row) => (
            <li key={row.obligation_class}>
              <ClassSpendRow
                coverageEnvelope={body.coverage_envelope}
                row={row}
              />
            </li>
          ))}
        </ol>
      </SemanticSection>

      <SemanticSection
        section="instrument-denominators"
        title={t("pages.cycleBoard.confidenceLedger.sections.denominators")}
      >
        <h3 data-confidence-text="denominators.instrument_definitions.title">
          {t("pages.cycleBoard.confidenceLedger.instrumentDefinitions")}
        </h3>
        <ol className="space-y-3" data-confidence-list="instrument-definitions">
          {body.instrument_definitions.map((row) => (
            <li key={row.instrument_id}>
              <InstrumentDefinition row={row} />
            </li>
          ))}
        </ol>
        <h3 data-confidence-text="denominators.certificate_routes.title">
          {t("pages.cycleBoard.confidenceLedger.certificateRoutes")}
        </h3>
        <ol className="space-y-3" data-confidence-list="certificate-routes">
          {body.certificate_routes.map((row) => (
            <li key={row.certificate_class}>
              <CertificateRoute row={row} />
            </li>
          ))}
        </ol>
      </SemanticSection>

      <SemanticSection
        section="positive-register"
        title={t("pages.cycleBoard.confidenceLedger.sections.positiveRegister")}
      >
        <div className="space-y-1">
          <h3 data-confidence-text="positive.empty.title">
            {t("pages.cycleBoard.confidenceLedger.positiveEmpty.title")}
          </h3>
          <p data-confidence-text="positive.empty.body">
            {t("pages.cycleBoard.confidenceLedger.positiveEmpty.body", {
              authority: body.positive_register.authority_posture.replaceAll(
                "_",
                " ",
              ),
              count: body.positive_register.population_count,
            })}
          </p>
        </div>
        <dl>
          <DetailRow label="population_state">
            <SemanticValue
              field="positive.population_state"
              value={body.positive_register.population_state ?? null}
            />
          </DetailRow>
          <DetailRow label="population_count">
            <SemanticValue
              field="positive.population_count"
              value={body.positive_register.population_count ?? 0}
            />
          </DetailRow>
          <DetailRow label="authority_posture">
            <SemanticValue
              field="positive.authority_posture"
              value={body.positive_register.authority_posture ?? null}
            />
          </DetailRow>
          <DetailRow label="appointment_denominator_state">
            <SemanticValue
              field="positive.appointment_denominator_state"
              value={
                body.positive_register.appointment_denominator_state ?? null
              }
            />
          </DetailRow>
          <DetailRow label="appointment_sufficiency_state">
            <SemanticValue
              field="positive.appointment_sufficiency_state"
              value={
                body.positive_register.appointment_sufficiency_state ?? null
              }
            />
          </DetailRow>
          <DetailRow label="promotion_blockers">
            <SemanticList
              field="positive.promotion_blockers"
              values={promotionBlockers}
            />
          </DetailRow>
          <DetailRow label="register_blockers">
            <SemanticList
              field="positive.register_blockers"
              values={body.positive_register.blockers.map(
                (row) => `${row.slot}:${row.value}`,
              )}
            />
          </DetailRow>
          <DetailRow label="would_populate_when">
            <SemanticList
              field="positive.would_populate_when"
              values={body.positive_register.would_populate_when}
            />
          </DetailRow>
          <DetailRow label="verified_appointment_refs">
            <SemanticList
              field="positive.verified_appointment_refs"
              values={
                body.positive_register.verified_appointment_refs as string[]
              }
            />
          </DetailRow>
        </dl>
      </SemanticSection>

      <SemanticSection
        section="good-event-source-replay"
        title={t(
          "pages.cycleBoard.confidenceLedger.sections.goodEventSourceReplay",
        )}
      >
        <dl>
          <DetailRow label="coverage_assessment">
            <SemanticValue
              field="posture.coverage_assessment"
              value={body.coverage_assessment}
            />
          </DetailRow>
          <DetailRow label="budget_posture">
            <SemanticValue
              field="posture.budget_posture"
              value={body.budget_posture}
            />
          </DetailRow>
          <DetailRow label="appointment_posture">
            <SemanticValue
              field="posture.appointment_posture"
              value={body.appointment_posture}
            />
          </DetailRow>
          <DetailRow label="packet_may_not_use_for">
            <SemanticList
              field="posture.packet_may_not_use_for"
              values={packet.may_not_use_for ?? []}
            />
          </DetailRow>
          <DetailRow label="envelope_may_not_use_for">
            <SemanticList
              field="posture.envelope_may_not_use_for"
              values={body.coverage_envelope.may_not_use_for}
            />
          </DetailRow>
          <DetailRow label="good_event_clause">
            <SemanticValue
              field="good_event.clause"
              value={body.good_event_posture.good_event_clause}
            />
          </DetailRow>
          <DetailRow label="composition_rule">
            <SemanticValue
              field="good_event.composition_rule"
              value={body.good_event_posture.composition_rule ?? null}
            />
          </DetailRow>
          <DetailRow label="independence_claim">
            <SemanticValue
              field="good_event.independence_claim"
              value={body.good_event_posture.independence_claim ?? false}
            />
          </DetailRow>
          <DetailRow label="executed_probabilistic_good_event_refs">
            <SemanticList
              field="good_event.executed_refs"
              values={
                body.good_event_posture.executed_probabilistic_good_event_refs
              }
            />
          </DetailRow>
          <DetailRow label="source.relative_path">
            <SemanticValue
              field="source.relative_path"
              value={packet.source.relative_path}
            />
          </DetailRow>
          <DetailRow label="source.artifact_content_hash">
            <SemanticValue
              field="source.artifact_content_hash"
              value={packet.source.artifact_content_hash}
            />
          </DetailRow>
          <DetailRow label="source.validator_id">
            <SemanticValue
              field="source.validator_id"
              value={packet.source.validation.validator_id}
            />
          </DetailRow>
          <DetailRow label="source.validator_version">
            <SemanticValue
              field="source.validator_version"
              value={packet.source.validation.validator_version}
            />
          </DetailRow>
          <DetailRow label="source.validation.status">
            <SemanticValue
              field="source.validation_status"
              value={packet.source.validation.status}
            />
          </DetailRow>
          <DetailRow label="worker_validation_receipt_ref">
            <SemanticValue
              field="source.worker_receipt_ref"
              value={packet.worker_validation_receipt_ref}
            />
          </DetailRow>
          <DetailRow label="worker_validation_receipt_hash">
            <SemanticValue
              field="source.worker_receipt_hash"
              value={packet.worker_validation_receipt_hash}
            />
          </DetailRow>
          <DetailRow label="replay_address">
            <SemanticValue
              field="replay.address"
              value={packet.replay_address}
            />
          </DetailRow>
          {Object.entries(packet.replay_pins).map(([field, value]) => (
            <DetailRow key={field} label={`replay_pins.${field}`}>
              <SemanticValue field={`replay.${field}`} value={value} />
            </DetailRow>
          ))}
          <DetailRow label="source_provenance">
            <SemanticList
              field="source.provenance"
              values={body.source_provenance.map(
                (source) =>
                  `${source.source_role}|${source.source_ref}|${source.content_hash}|${source.admission_state}|${source.availability_state}|${source.verifier_ref}`,
              )}
            />
          </DetailRow>
        </dl>
      </SemanticSection>

      <SemanticSection
        section="machine-export"
        title={t("pages.cycleBoard.confidenceLedger.sections.machineExport")}
      >
        <Button
          data-confidence-text="machine.download"
          onClick={() =>
            exportCapturedResponseBytes(
              "confidence-ledger-risk-spend.machine.json",
              rawPacketBytes,
              "application/json",
            )
          }
          type="button"
          variant="outline"
        >
          {t("pages.cycleBoard.confidenceLedger.downloadMachine")}
        </Button>
      </SemanticSection>
    </Card>
  );
}

function NonAvailableRiskSpend({
  packet,
}: Readonly<{
  packet: Exclude<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >;
}>) {
  const { t } = useI18n();
  if (packet.availability === "source_blocked") {
    return (
      <Card
        className="space-y-4 p-5"
        data-confidence-surface="risk-spend-source-blocked"
      >
        <h2>{t("pages.cycleBoard.confidenceLedger.sourceBlocked.title")}</h2>
        <dl>
          <DetailRow label="source_blocked_reason">
            <SemanticValue
              field="blocked.reason"
              value={packet.source_blocked_reason}
            />
          </DetailRow>
          <DetailRow label="source_artifact_content_hash">
            <SemanticValue
              field="blocked.source_hash"
              value={packet.source_artifact_content_hash}
            />
          </DetailRow>
          <DetailRow label="source_schema_version">
            <SemanticValue
              field="blocked.source_schema"
              value={packet.source_schema_version}
            />
          </DetailRow>
          <DetailRow label="source_rule_version">
            <SemanticValue
              field="blocked.source_rule"
              value={packet.source_rule_version}
            />
          </DetailRow>
          <DetailRow label="worker_validation_receipt_ref">
            <SemanticValue
              field="blocked.validator_ref"
              value={packet.worker_validation_receipt_ref}
            />
          </DetailRow>
          <DetailRow label="worker_validation_receipt_hash">
            <SemanticValue
              field="blocked.validator_hash"
              value={packet.worker_validation_receipt_hash}
            />
          </DetailRow>
          <DetailRow label="replay_address">
            <SemanticValue
              field="blocked.replay_address"
              value={packet.replay_address}
            />
          </DetailRow>
          {Object.entries(packet.replay_pins).map(([field, value]) => (
            <DetailRow key={field} label={`replay_pins.${field}`}>
              <SemanticValue field={`blocked.replay.${field}`} value={value} />
            </DetailRow>
          ))}
        </dl>
      </Card>
    );
  }
  return (
    <Card data-confidence-surface={`risk-spend-${packet.availability}`}>
      <EmptyState
        body={packet.absence_reason}
        title={t(
          `pages.cycleBoard.confidenceLedger.${packet.availability}.title`,
        )}
      />
    </Card>
  );
}

/** Four-arm reviewer surface backed only by the protected specialized packet. */
export function ConfidenceLedgerRiskSpend({
  projection,
}: ConfidenceLedgerRiskSpendProps) {
  const { t } = useI18n();
  if (projection.status === "blocked") {
    return (
      <Card
        className="space-y-3 p-5"
        data-confidence-surface="risk-spend-evaluation-blocked"
      >
        <h2>
          {t("pages.cycleBoard.confidenceLedger.evaluationBlocked.title")}
        </h2>
        <p>{t("pages.cycleBoard.confidenceLedger.evaluationBlocked.body")}</p>
        <SemanticValue
          field="evaluation.blocked_reason"
          value={projection.reason}
        />
      </Card>
    );
  }
  return projection.packet.availability === "available" ? (
    <AvailableRiskSpend
      packet={projection.packet}
      rawPacketBytes={projection.rawPacketBytes}
    />
  ) : (
    <NonAvailableRiskSpend packet={projection.packet} />
  );
}
