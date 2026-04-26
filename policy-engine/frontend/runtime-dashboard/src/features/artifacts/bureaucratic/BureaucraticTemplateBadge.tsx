import { useOptionalI18n } from "@/i18n/LocaleProvider";
import { Badge } from "@/shared/ui";

import type { BureaucraticTemplateRef } from "./ast/bureaucratic-document-ast";

type BureaucraticTemplateBadgeProps = {
  template: BureaucraticTemplateRef;
};

export function BureaucraticTemplateBadge({
  template,
}: BureaucraticTemplateBadgeProps) {
  const { t } = useOptionalI18n();
  const kind =
    template.legal_review_status === "approved" ? ("ok" as const) : "warn";
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <Badge kind={kind}>{template.id}</Badge>
      <span className="text-muted font-mono">
        {t("pages.artifacts.bureaucratic.templateVersion", {
          version: template.version,
        })}
      </span>
      <span className="text-muted">{template.legal_review_status}</span>
    </div>
  );
}
