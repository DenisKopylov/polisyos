import { useMemo, useState } from "react";

import { useI18n } from "@/i18n/LocaleProvider";

import { Button } from "./Button";

type JsonPreviewProps = {
  data: unknown;
  emptyLabel?: string;
};

function stringifyPayload(data: unknown): string {
  if (data === undefined) {
    return "";
  }
  if (typeof data === "string") {
    return data;
  }
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

export default function JsonPreview({ data, emptyLabel }: JsonPreviewProps) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const payload = useMemo(() => stringifyPayload(data), [data]);
  const resolvedEmptyLabel = emptyLabel ?? t("common.noPayload");

  async function copyPayload() {
    if (!payload || !navigator?.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(payload);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1000);
  }

  if (!payload) {
    return <p className="text-sm text-muted">{resolvedEmptyLabel}</p>;
  }

  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <Button type="button" variant="ghost" size="sm" onClick={copyPayload}>
          {copied ? t("common.copied") : t("common.copy")}
        </Button>
      </div>
      <pre className="bg-surface/80 overflow-auto rounded-xl border border-line p-3 text-xs leading-5 text-text">
        {payload}
      </pre>
    </div>
  );
}
