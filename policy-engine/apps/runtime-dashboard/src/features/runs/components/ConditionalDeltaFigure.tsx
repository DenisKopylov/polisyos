import { useId, useState } from "react";

import type {
  AvailableConfidenceLedgerRiskSpendPacket,
  ConditionalDeltaAmount,
  ObligationCoverageEnvelope,
} from "@polisyos/runtime-api-client";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@polisyos/atlas-ui";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  epochNonreceipt,
  TimeSemanticsLabel,
} from "@/shared/ui/temporal/TimeSemanticsLabel";

type ConditionalDeltaFigureProps = Readonly<{
  amount: ConditionalDeltaAmount;
  coverageEnvelope: ObligationCoverageEnvelope;
  label: string;
}>;

type EnvelopeFieldProps = Readonly<{
  field: string;
  label: string;
  values: readonly string[];
}>;

export type ConfidenceLedgerEnvelopeField = Readonly<{
  field: string;
  label: string;
  values: readonly string[];
}>;

/** Renders this file's once-owned packet temporal semantics. */
export function ConfidenceLedgerTemporalOwner({
  packet,
}: Readonly<{ packet: AvailableConfidenceLedgerRiskSpendPacket }>) {
  return (
    <div data-testid="confidence-ledger-conditional-time-semantics">
      <TimeSemanticsLabel
        epochSemantics={epochNonreceipt()}
        freshness={packet.freshness}
        payloadAsOf={packet.as_of}
      />
    </div>
  );
}

/** Complete governed dialog projection of the packet-owned envelope. */
export function confidenceLedgerEnvelopeFields(
  envelope: ObligationCoverageEnvelope,
): readonly ConfidenceLedgerEnvelopeField[] {
  const fields: ConfidenceLedgerEnvelopeField[] = [];
  const append = (field: string, value: unknown): void => {
    if (Array.isArray(value)) {
      if (value.every((item) => item === null || typeof item !== "object")) {
        fields.push({
          field,
          label: field,
          values: value.map((item) => (item === null ? "null" : String(item))),
        });
        return;
      }
      value.forEach((item, index) => append(`${field}.${index}`, item));
      return;
    }
    if (typeof value === "object" && value !== null) {
      Object.entries(value).forEach(([nestedField, nestedValue]) =>
        append(field ? `${field}.${nestedField}` : nestedField, nestedValue),
      );
      return;
    }
    fields.push({
      field,
      label: field,
      values: [value === null ? "null" : String(value)],
    });
  };
  append("", envelope);
  return Object.freeze(fields);
}

function EnvelopeField({ field, label, values }: EnvelopeFieldProps) {
  return (
    <div className="border-border grid gap-1 border-b py-2 last:border-b-0 md:grid-cols-[minmax(0,13rem)_minmax(0,1fr)]">
      <dt
        className="text-muted-foreground text-xs font-semibold tracking-wide uppercase"
        data-confidence-text={`dialog.field.${field}.label`}
      >
        {label}
      </dt>
      <dd className="min-w-0 text-sm break-words">
        {values.length === 0 ? (
          <span data-confidence-text={`dialog.field.${field}.empty`}>[]</span>
        ) : values.length === 1 ? (
          <span data-confidence-text={`dialog.field.${field}.value.0`}>
            {values[0]}
          </span>
        ) : (
          <ol
            className="list-none space-y-1 pl-5"
            style={{ listStyle: "none" }}
          >
            {values.map((item, index) => (
              <li
                data-confidence-text={`dialog.field.${field}.value.${index}`}
                key={`${label}-${index}-${item}`}
              >
                {item}
              </li>
            ))}
          </ol>
        )}
      </dd>
    </div>
  );
}

function ConditionalEnvelopeDetails({
  envelope,
}: Readonly<{ envelope: ObligationCoverageEnvelope }>) {
  return (
    <dl className="border-border rounded-md border px-3">
      {confidenceLedgerEnvelopeFields(envelope).map((field) => (
        <EnvelopeField key={field.field} {...field} />
      ))}
    </dl>
  );
}

/** Exact local amount whose sole chip carries both mandatory conditionality riders. */
export function ConditionalDeltaFigure({
  amount,
  coverageEnvelope,
  label,
}: ConditionalDeltaFigureProps) {
  const { t } = useI18n();
  const [isOpen, setIsOpen] = useState(false);
  const triggerId = `confidence-ledger-trigger-${useId()}`;
  const riders = `${amount.declared_set_rider} — ${amount.locality_rider}`;
  const dialogTitle = `${label}: ${t("pages.cycleBoard.confidenceLedger.figure.dialogTitle")}`;

  return (
    <figure className="border-border bg-card space-y-2 rounded-md border p-3">
      <figcaption
        className="text-sm font-semibold"
        data-confidence-text="figure.caption"
      >
        {label}
      </figcaption>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <output
          className="font-mono text-lg font-semibold"
          data-confidence-leaf="rational-display"
          data-confidence-text="figure.rational_display"
        >
          {amount.rational_display}
        </output>
        <span className="text-muted-foreground text-xs">
          <span data-confidence-text="figure.canonical_decimal_label">
            {t("pages.cycleBoard.confidenceLedger.figure.canonicalDecimal")}:
          </span>{" "}
          <span data-confidence-leaf="canonical-decimal">
            <span data-confidence-text="figure.canonical_decimal">
              {amount.canonical_decimal}
            </span>
          </span>
        </span>
      </div>
      <Dialog modal={false} open={isOpen} onOpenChange={setIsOpen}>
        <DialogTrigger asChild>
          <button
            aria-label={`${label}: ${riders}`}
            className="border-border bg-muted/40 hover:bg-muted focus-visible:ring-ring inline-flex w-full rounded-full border px-3 py-1.5 text-left text-xs leading-5 focus-visible:ring-2 focus-visible:outline-none"
            data-confidence-amount-hash={amount.amount_hash}
            data-confidence-declared-classes-hash={
              amount.declared_obligation_classes_hash
            }
            data-confidence-envelope-ref={amount.coverage_envelope_ref}
            data-confidence-leaf="conditionality-riders"
            data-confidence-scope-id={amount.scope_id}
            data-confidence-semantic-role={amount.semantic_role}
            data-confidence-text="figure.conditionality_riders"
            data-confidence-trigger="conditional-delta"
            id={triggerId}
            style={{ appearance: "none" }}
            type="button"
          >
            {riders}
          </button>
        </DialogTrigger>
        <DialogContent
          className="max-h-[86vh] max-w-4xl overflow-y-auto"
          closeLabel={t("common.close")}
          data-confidence-amount-hash={amount.amount_hash}
          data-confidence-declared-classes-hash={
            amount.declared_obligation_classes_hash
          }
          data-confidence-dialog-envelope-ref={coverageEnvelope.envelope_ref}
          data-confidence-dialog-trigger-id={triggerId}
          data-confidence-scope-id={amount.scope_id}
          data-confidence-semantic-role={amount.semantic_role}
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          <style>
            {
              "[data-confidence-dialog-envelope-ref] > button { appearance: none; }"
            }
          </style>
          <DialogHeader>
            <DialogTitle data-confidence-text="dialog.title">
              {dialogTitle}
            </DialogTitle>
            <DialogDescription data-confidence-text="dialog.description">
              {t("pages.cycleBoard.confidenceLedger.figure.dialogDescription")}
            </DialogDescription>
          </DialogHeader>
          <ConditionalEnvelopeDetails envelope={coverageEnvelope} />
        </DialogContent>
      </Dialog>
    </figure>
  );
}
