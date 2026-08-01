import { useState, type SyntheticEvent } from "react";
import { GitCompareArrows } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useCompareCandidates } from "@/api/hooks/useCompareRuns";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Button } from "@polisyos/atlas-ui";

import { buildPolicyDiffHref } from "../domain/searchParams";

type CompareCommandDialogProps = {
  currentRunId?: string;
  targetRunId?: string;
};

export function CompareCommandDialog({
  currentRunId,
  targetRunId,
}: CompareCommandDialogProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [runA, setRunA] = useState(currentRunId ?? "");
  const [runB, setRunB] = useState(targetRunId ?? "");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const candidatesQuery = useCompareCandidates(currentRunId, { enabled: open });

  function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!runA.trim() || !runB.trim()) {
      return;
    }
    setOpen(false);
    navigate(buildPolicyDiffHref(runA.trim(), runB.trim(), searchParams));
  }

  return (
    <div className="relative">
      <Button
        type="button"
        variant="ghost"
        leading={<GitCompareArrows className="size-4" aria-hidden="true" />}
        onClick={() => {
          setRunA(currentRunId ?? runA);
          setRunB(targetRunId ?? runB);
          setOpen((value) => !value);
        }}
        aria-expanded={open}
      >
        {t("pages.runs.policyDiff.compareRuns")}
      </Button>
      {open ? (
        <div
          role="dialog"
          aria-label={t("pages.runs.policyDiff.compareRuns")}
          className="border-line bg-surface absolute right-0 z-20 mt-2 w-[min(92vw,420px)] rounded-[var(--radius-panel)] border p-4 shadow-xl"
        >
          <form className="space-y-3" onSubmit={submit}>
            <div>
              <label className="text-sm font-semibold" htmlFor="compare-run-a">
                {t("pages.runs.policyDiff.runA")}
              </label>
              <input
                id="compare-run-a"
                className="border-line bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm"
                value={runA}
                onChange={(event) => setRunA(event.target.value)}
              />
            </div>
            <div>
              <label className="text-sm font-semibold" htmlFor="compare-run-b">
                {t("pages.runs.policyDiff.runB")}
              </label>
              <input
                id="compare-run-b"
                className="border-line bg-background mt-1 w-full rounded-md border px-3 py-2 text-sm"
                value={runB}
                onChange={(event) => setRunB(event.target.value)}
              />
            </div>
            {candidatesQuery.data?.candidates?.length ? (
              <div className="space-y-2">
                <p className="text-muted text-xs font-semibold uppercase">
                  {t("pages.runs.policyDiff.suggestedComparators")}
                </p>
                {candidatesQuery.data.candidates
                  .slice(0, 3)
                  .map((candidate) => (
                    <button
                      key={candidate.run_id}
                      type="button"
                      className="border-line hover:bg-muted/30 w-full rounded-md border px-2 py-2 text-left text-sm"
                      onClick={() => setRunB(candidate.run_id)}
                    >
                      <span className="font-semibold">{candidate.run_id}</span>
                      <span className="text-muted block text-xs">
                        {t(
                          `pages.runs.policyDiff.relation.${candidate.relation}`,
                        )}{" "}
                        · {candidate.comparability.status}
                      </span>
                    </button>
                  ))}
              </div>
            ) : null}
            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setOpen(false)}
              >
                {t("common.cancel")}
              </Button>
              <Button type="submit" variant="primary">
                {t("pages.runs.policyDiff.openDiff")}
              </Button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
