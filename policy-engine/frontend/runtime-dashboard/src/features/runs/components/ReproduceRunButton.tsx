import { useState, useCallback } from "react";

import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/LocaleProvider";
import { Button } from "@/shared/ui/primitives";

type ReproduceRunButtonProps = {
  runId: string;
  parameters?: Record<string, unknown>;
  onReproduce: (params: {
    sourceRunId: string;
    parameters: Record<string, unknown>;
  }) => Promise<{ runId?: string } | undefined>;
  disabled?: boolean;
  className?: string;
};

export function ReproduceRunButton({
  runId,
  parameters = {},
  onReproduce,
  disabled = false,
  className,
}: ReproduceRunButtonProps) {
  const { t } = useI18n();
  const [state, setState] = useState<
    "idle" | "confirming" | "submitting" | "done" | "error"
  >("idle");
  const [newRunId, setNewRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleClick = useCallback(() => {
    if (state === "idle") {
      setState("confirming");
    }
  }, [state]);

  const handleConfirm = useCallback(async () => {
    setState("submitting");
    setError(null);
    try {
      const result = await onReproduce({
        sourceRunId: runId,
        parameters,
      });
      setNewRunId(result?.runId ?? null);
      setState("done");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("pages.runs.reproduce.failed"),
      );
      setState("error");
    }
  }, [runId, parameters, onReproduce, t]);

  const handleCancel = useCallback(() => {
    setState("idle");
    setError(null);
  }, []);

  if (state === "done") {
    return (
      <div className={cn("flex items-center gap-2 text-sm", className)}>
        <span className="text-[var(--chart-success)]">{"\u2713"}</span>
        <span>
          {t("pages.runs.reproduce.done")}
          {newRunId && (
            <span className="text-muted ms-1 font-mono">({newRunId})</span>
          )}
        </span>
      </div>
    );
  }

  if (state === "confirming" || state === "submitting") {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <span className="text-sm">
          {t("pages.runs.reproduce.confirmPrompt", { runId })}
        </span>
        <Button
          type="button"
          variant="primary"
          onClick={handleConfirm}
          disabled={state === "submitting"}
        >
          {state === "submitting"
            ? t("pages.runs.reproduce.submitting")
            : t("common.confirm")}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={handleCancel}
          disabled={state === "submitting"}
        >
          {t("common.cancel")}
        </Button>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <span className="text-sm text-[var(--chart-alert)]">
          {error ?? t("pages.runs.reproduce.failed")}
        </span>
        <Button type="button" variant="ghost" onClick={handleCancel}>
          {t("common.dismiss")}
        </Button>
      </div>
    );
  }

  return (
    <Button
      type="button"
      variant="ghost"
      onClick={handleClick}
      disabled={disabled}
      className={className}
    >
      {t("pages.runs.reproduce.action")}
    </Button>
  );
}
