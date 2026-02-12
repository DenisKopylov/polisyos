import { useMemo, useState } from "react";

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

export default function JsonPreview({ data, emptyLabel = "No payload" }: JsonPreviewProps) {
  const [copied, setCopied] = useState(false);
  const payload = useMemo(() => stringifyPayload(data), [data]);

  async function copyPayload() {
    if (!payload || !navigator?.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(payload);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1000);
  }

  if (!payload) {
    return <p className="text-sm text-muted">{emptyLabel}</p>;
  }

  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={copyPayload}
          className="rounded-lg border border-line bg-panel px-3 py-1.5 text-xs font-semibold"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-auto rounded-xl border border-line bg-[#f8fbff] p-3 text-xs leading-5 text-text">
        {payload}
      </pre>
    </div>
  );
}
