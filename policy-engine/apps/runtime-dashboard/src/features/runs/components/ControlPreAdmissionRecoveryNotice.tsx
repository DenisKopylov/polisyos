import type { ControlPreAdmissionRecoveryData } from "@/api/hooks/useControlPreAdmissionRecovery";
import { useI18n } from "@/shared/i18n/LocaleProvider";

export function ControlPreAdmissionRecoveryNotice({
  data,
  error,
}: {
  data: ControlPreAdmissionRecoveryData | null;
  error: unknown;
}) {
  const { t } = useI18n();
  if (data === null && !error) return null;
  const record = data?.record ?? null;
  const attempt = data?.attempt ?? null;
  const status = attempt?.status ?? record?.status ?? "unknown";
  const attemptId = attempt?.attempt_id ?? record?.attemptId;
  const jobId = attempt?.job_id ?? record?.jobId;
  const runId = attempt?.run_id ?? record?.runId;
  const events = attempt?.producer_event_ids ?? record?.producerEventIds ?? [];

  return (
    <section
      aria-live="polite"
      className="rounded-xl border border-amber-500/40 bg-amber-50/70 p-4 text-sm"
      data-testid="control-pre-admission-recovery"
      role="status"
    >
      <h3 className="font-semibold">{t("common.admissionRecovery.title")}</h3>
      <p className="mt-1">
        {error
          ? t("common.admissionRecovery.unverified")
          : attempt
            ? t("common.admissionRecovery.serverObserved")
            : t("common.admissionRecovery.pending")}
      </p>
      <dl className="mt-3 grid gap-1">
        <div>
          <dt className="inline font-medium">
            {t("common.admissionRecovery.status")}:{" "}
          </dt>
          <dd className="inline" data-testid="pre-admission-recovery-status">
            {status}
          </dd>
        </div>
        {attemptId ? (
          <div>
            <dt className="inline font-medium">
              {t("common.admissionRecovery.attempt")}:{" "}
            </dt>
            <dd className="inline">{attemptId}</dd>
          </div>
        ) : null}
        {runId ? (
          <div>
            <dt className="inline font-medium">
              {t("common.admissionRecovery.run")}:{" "}
            </dt>
            <dd className="inline">{runId}</dd>
          </div>
        ) : null}
        {jobId ? (
          <div>
            <dt className="inline font-medium">
              {t("common.admissionRecovery.job")}:{" "}
            </dt>
            <dd className="inline">{jobId}</dd>
          </div>
        ) : null}
        {events.length > 0 ? (
          <div>
            <dt className="font-medium">
              {t("common.admissionRecovery.producerEvents")}
            </dt>
            <dd>
              <ul className="list-disc pl-5">
                {events.map((eventId) => (
                  <li key={eventId}>{eventId}</li>
                ))}
              </ul>
            </dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}
