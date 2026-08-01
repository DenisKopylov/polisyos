import { useMemo, useState } from "react";

import { Button } from "../primitives/Button";

export type JsonPreviewLabels = {
  copied: string;
  copy: string;
  empty: string;
};

export type JsonPreviewProps = {
  data: unknown;
  labels?: JsonPreviewLabels;
};

const DEFAULT_LABELS: JsonPreviewLabels = {
  copied: "Copied",
  copy: "Copy",
  empty: "No payload",
};

function stringifyPayload(data: unknown): string {
  if (data === undefined) {
    return "";
  }
  if (typeof data === "string") {
    return data;
  }
  try {
    return (
      JSON.stringify(data, null, 2) ?? Object.prototype.toString.call(data)
    );
  } catch {
    return Object.prototype.toString.call(data);
  }
}

export function JsonPreview({
  data,
  labels = DEFAULT_LABELS,
}: JsonPreviewProps) {
  const [copied, setCopied] = useState(false);
  const payload = useMemo(() => stringifyPayload(data), [data]);

  async function copyPayload() {
    if (!payload || !navigator.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(payload);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1000);
  }

  if (!payload) {
    return <p className="text-muted text-sm">{labels.empty}</p>;
  }

  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            void copyPayload();
          }}
        >
          {copied ? labels.copied : labels.copy}
        </Button>
      </div>
      <pre className="bg-surface/80 border-line text-text overflow-auto rounded-xl border p-3 text-xs leading-5">
        {payload}
      </pre>
    </div>
  );
}
