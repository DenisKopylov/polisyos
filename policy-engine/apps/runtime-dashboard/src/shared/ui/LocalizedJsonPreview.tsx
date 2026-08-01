import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  JsonPreview,
  type JsonPreviewLabels,
  type JsonPreviewProps,
} from "@polisyos/atlas-ui";

type LocalizedJsonPreviewProps = Omit<JsonPreviewProps, "labels">;

/** Bind the package-owned JSON presentation to the dashboard locale authority. */
export function LocalizedJsonPreview(props: LocalizedJsonPreviewProps) {
  const { t } = useI18n();
  const labels: JsonPreviewLabels = {
    copied: t("common.copied"),
    copy: t("common.copy"),
    empty: t("common.noPayload"),
  };

  return <JsonPreview {...props} labels={labels} />;
}
