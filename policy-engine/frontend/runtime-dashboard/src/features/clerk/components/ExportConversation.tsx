import { useCallback } from "react";

import { cn, formatDate } from "@/lib/utils";
import { Button } from "@/shared/ui/primitives";
import { useI18n } from "@/i18n/LocaleProvider";

import { useChatStore, type ChatMessage } from "../state/useChatStore";

type ExportFormat = "markdown" | "json" | "text";

type ExportConversationProps = {
  className?: string;
};

function formatTimestamp(ts: number): string {
  return formatDate(ts, undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function toMarkdown(messages: ChatMessage[]): string {
  const lines: string[] = [];
  lines.push("# PolicyOS Analysis Conversation");
  lines.push("");
  lines.push(`**Exported:** ${formatTimestamp(Date.now())}`);
  lines.push("");
  lines.push("---");
  lines.push("");

  for (const msg of messages) {
    const role = msg.role === "user" ? "User" : "PolicyOS";
    lines.push(`### ${role}`);
    lines.push(`*${formatTimestamp(msg.timestamp)}*`);
    lines.push("");

    if (msg.content) {
      lines.push(msg.content);
      lines.push("");
    }

    if (msg.structured) {
      const s = msg.structured;
      if (s.verdict) {
        lines.push(`**Verdict:** ${s.verdict}`);
      }
      if (s.confidence != null) {
        lines.push(
          `**Confidence:** ${Math.round(s.confidence * 100)}% (${s.confidenceLevel ?? "unknown"})`,
        );
      }
      if (s.methodology) {
        lines.push(`**Methodology:** ${s.methodology}`);
      }
      if (s.keyFactors && s.keyFactors.length > 0) {
        lines.push("");
        lines.push("**Key Factors:**");
        for (const f of s.keyFactors) {
          const arrow =
            f.direction === "positive"
              ? "\u2191"
              : f.direction === "negative"
                ? "\u2193"
                : "\u2022";
          lines.push(
            `- ${arrow} ${f.label} (magnitude: ${Math.round(f.magnitude * 100)}%)`,
          );
        }
      }
      if (s.sources && s.sources.length > 0) {
        lines.push("");
        lines.push("**Sources:**");
        for (const src of s.sources) {
          const link = src.url ? ` [link](${src.url})` : "";
          lines.push(`- [${src.type}] ${src.label}${link}`);
        }
      }
      lines.push("");
    }

    if (msg.runId) {
      lines.push(`*Run ID: ${msg.runId}*`);
    }
    if (msg.runStatus) {
      lines.push(`*Status: ${msg.runStatus}*`);
    }

    lines.push("");
    lines.push("---");
    lines.push("");
  }

  return lines.join("\n");
}

function toPlainText(messages: ChatMessage[]): string {
  const lines: string[] = [];
  lines.push("PolicyOS Analysis Conversation");
  lines.push(`Exported: ${formatTimestamp(Date.now())}`);
  lines.push("=".repeat(60));
  lines.push("");

  for (const msg of messages) {
    const role = msg.role === "user" ? "USER" : "POLISYOS";
    lines.push(`[${role}] ${formatTimestamp(msg.timestamp)}`);
    if (msg.content) lines.push(msg.content);
    if (msg.structured?.verdict) {
      lines.push(`Verdict: ${msg.structured.verdict}`);
    }
    if (msg.runId) lines.push(`Run: ${msg.runId}`);
    lines.push("-".repeat(40));
    lines.push("");
  }

  return lines.join("\n");
}

function toJson(messages: ChatMessage[]): string {
  return JSON.stringify(
    {
      exportedAt: new Date().toISOString(),
      messages: messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        timestamp: new Date(m.timestamp).toISOString(),
        runId: m.runId,
        runStatus: m.runStatus,
        structured: m.structured,
      })),
    },
    null,
    2,
  );
}

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ExportConversation({ className }: ExportConversationProps) {
  const { t } = useI18n();
  const { messages } = useChatStore();

  const handleExport = useCallback(
    (format: ExportFormat) => {
      if (messages.length === 0) return;

      const timestamp = new Date().toISOString().slice(0, 10);
      switch (format) {
        case "markdown": {
          const md = toMarkdown(messages);
          downloadBlob(
            md,
            `polisyos-conversation-${timestamp}.md`,
            "text/markdown",
          );
          break;
        }
        case "json": {
          const json = toJson(messages);
          downloadBlob(
            json,
            `polisyos-conversation-${timestamp}.json`,
            "application/json",
          );
          break;
        }
        case "text": {
          const txt = toPlainText(messages);
          downloadBlob(
            txt,
            `polisyos-conversation-${timestamp}.txt`,
            "text/plain",
          );
          break;
        }
      }
    },
    [messages],
  );

  if (messages.length === 0) return null;

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="text-xs font-semibold text-[var(--slate)]">
        {t("clerk.export")}:
      </span>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => handleExport("markdown")}
      >
        {t("clerk.exportMarkdown")}
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => handleExport("json")}
      >
        {t("clerk.exportJson")}
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => handleExport("text")}
      >
        {t("clerk.exportText")}
      </Button>
    </div>
  );
}

export { toMarkdown, toPlainText, toJson };
