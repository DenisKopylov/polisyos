import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";
import {
  authorityStatusBadgeProps,
  issueLegalReviewPresentation,
} from "@/shared/ui/AuthorityStatusPresentation";
import { Badge } from "@polisyos/atlas-ui";

import type { BureaucraticTemplateRef } from "./ast/bureaucratic-document-ast";

type BureaucraticTemplateBadgeProps = {
  template: BureaucraticTemplateRef;
};

export function BureaucraticTemplateBadge({
  template,
}: BureaucraticTemplateBadgeProps) {
  const { t } = useOptionalI18n();
  const legalReview = issueLegalReviewPresentation(
    template.legal_review_status,
  );
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <Badge {...authorityStatusBadgeProps(legalReview)}>{template.id}</Badge>
      <span className="text-muted font-mono">
        {t("pages.artifacts.bureaucratic.templateVersion", {
          version: template.version,
        })}
      </span>
      <span className="text-muted">{template.legal_review_status}</span>
    </div>
  );
}
