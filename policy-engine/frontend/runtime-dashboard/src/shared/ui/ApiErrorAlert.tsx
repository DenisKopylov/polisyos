import { RuntimeApiRequestError } from "@/api/http";
import { useI18n } from "@/shared/i18n/LocaleProvider";

type ApiErrorAlertProps = {
  error: unknown;
  title?: string;
};

export function ApiErrorAlert({ error, title }: ApiErrorAlertProps) {
  const { t } = useI18n();
  const resolvedTitle = title ?? t("common.requestFailed");

  if (error instanceof RuntimeApiRequestError) {
    return (
      <div className="atlas-error">
        <p className="text-danger font-semibold">{resolvedTitle}</p>
        <p className="text-danger mt-1">{error.detail}</p>
        <p className="text-danger/80 mt-2 font-mono text-xs">
          <span>
            {t("shared.ui.apiErrorAlert.status", { status: error.status })}
          </span>{" "}
          <span>{t("shared.ui.apiErrorAlert.code", { code: error.code })}</span>
          {error.requestId ? (
            <>
              {" "}
              <span>
                {t("shared.ui.apiErrorAlert.requestId", {
                  requestId: error.requestId,
                })}
              </span>
            </>
          ) : null}
        </p>
      </div>
    );
  }

  return (
    <div className="atlas-error text-danger">
      <p className="font-semibold">{resolvedTitle}</p>
      <p className="mt-1">{String(error)}</p>
    </div>
  );
}
