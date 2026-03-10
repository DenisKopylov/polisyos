import { isRouteErrorResponse, useRouteError } from "react-router-dom";

import { useI18n } from "@/i18n/LocaleProvider";
import { Card, EmptyState } from "@/shared/ui";

function getErrorMessage(error: unknown) {
  if (isRouteErrorResponse(error)) {
    return `${error.status} ${error.statusText || "Route error"}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown route error";
}

export function RouteErrorElement() {
  const error = useRouteError();
  const { t } = useI18n();

  return (
    <div className="workspace-frame workspace-frame--full-width">
      <Card>
        <EmptyState
          title={t("common.pageErrorTitle")}
          body={`${t("common.pageErrorBody")} ${getErrorMessage(error)}`}
        />
      </Card>
    </div>
  );
}
