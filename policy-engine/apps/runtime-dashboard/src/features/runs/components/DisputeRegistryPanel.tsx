import { useMemo, useState } from "react";

import type { GovernanceIssueView } from "@/shared/lib/domain/governance";
import { useAuthz } from "@/app/authz/AuthzProvider";
import type { AuthorityLocalScope } from "@/app/offline/authorityLocalState";
import {
  buildDisputeRecords,
  createDisputeStatus,
  type DisputeRecord,
  readStoredDisputes,
  writeStoredDisputes,
} from "@/features/runs/domain/disputes";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatDate, formatNumber } from "@/shared/lib/utils";
import { Badge, Button, Card, Input, Label, Select } from "@polisyos/atlas-ui";

function statusKind(status: DisputeRecord["status"]) {
  if (status.label === "resolved") return "ok";
  if (status.label === "open") return "fail";
  return "warn";
}

function DisputeRegistryPanel({
  issues,
  runId,
  scope,
}: {
  issues: GovernanceIssueView[];
  runId: string;
  scope: AuthorityLocalScope | null;
}) {
  const { t } = useI18n();
  const [draftTitle, setDraftTitle] = useState("");
  const [draftBasis, setDraftBasis] = useState("policy");
  const [localDisputes, setLocalDisputes] = useState<DisputeRecord[]>(() =>
    readStoredDisputes(scope, runId),
  );
  const disputes = buildDisputeRecords(issues, localDisputes);
  const openCount = disputes.filter(
    (dispute) => dispute.status.label === "open",
  ).length;

  return (
    <Card className="space-y-4" data-testid="dispute-registry-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("phase32.disputes.eyebrow")}</p>
          <h3>{t("phase32.disputes.title")}</h3>
          <p className="topbar-subtitle mt-2">{t("phase32.disputes.body")}</p>
        </div>
        <Badge kind={openCount > 0 ? "fail" : "ok"}>
          {t("phase32.disputes.openCount", {
            value: formatNumber(openCount),
          })}
        </Badge>
      </div>

      <div className="border-line bg-surface/80 grid gap-3 rounded-2xl border p-3 md:grid-cols-[minmax(0,1fr)_10rem_auto]">
        <div>
          <Label htmlFor="dispute-title">
            {t("phase32.disputes.titleLabel")}
          </Label>
          <Input
            id="dispute-title"
            value={draftTitle}
            onChange={(event) => setDraftTitle(event.target.value)}
            placeholder={t("phase32.disputes.placeholder")}
          />
        </div>
        <div>
          <Label htmlFor="dispute-basis">{t("phase32.disputes.basis")}</Label>
          <Select
            id="dispute-basis"
            value={draftBasis}
            onChange={(event) => setDraftBasis(event.target.value)}
          >
            <option value="policy">{t("phase32.disputes.basisPolicy")}</option>
            <option value="data">{t("phase32.disputes.basisData")}</option>
            <option value="legal">{t("phase32.disputes.basisLegal")}</option>
          </Select>
        </div>
        <div className="flex items-end">
          <Button
            type="button"
            disabled={!draftTitle.trim()}
            onClick={() => {
              let now: string;
              try {
                now = new Date().toISOString();
              } catch {
                return;
              }
              const next = [
                {
                  actor: "reviewer",
                  authorityPurpose: "case_management_note",
                  basis: draftBasis,
                  id: `local:${runId}:${now}`,
                  openedAt: now,
                  status: createDisputeStatus("open"),
                  target: "decision",
                  title: draftTitle.trim(),
                },
                ...localDisputes,
              ] satisfies DisputeRecord[];
              if (!writeStoredDisputes(scope, runId, next)) {
                return;
              }
              setLocalDisputes(next);
              setDraftTitle("");
            }}
            variant="primary"
          >
            {t("phase32.disputes.add")}
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        {disputes.map((dispute) => (
          <article
            key={dispute.id}
            className="border-line bg-surface/70 rounded-2xl border p-3"
            data-authority-purpose={dispute.authorityPurpose}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold">{dispute.title}</p>
                <p className="text-muted mt-1 text-xs">
                  {t("phase32.disputes.meta", {
                    actor:
                      dispute.actor === "governance"
                        ? t("phase32.disputes.actorGovernance")
                        : t("phase32.disputes.actorReviewer"),
                    basis: dispute.basis,
                    date: formatDate(dispute.openedAt),
                    target: dispute.target,
                  })}
                </p>
              </div>
              <Badge kind={statusKind(dispute.status)}>
                {dispute.status.label}
              </Badge>
            </div>
            <p className="text-muted mt-2 font-mono text-xs">
              {dispute.authorityPurpose === "case_management_note"
                ? t("phase32.disputes.caseManagementNote")
                : t("phase32.disputes.governanceProjection")}
            </p>
          </article>
        ))}
        {disputes.length === 0 ? (
          <p className="text-muted text-sm">{t("phase32.disputes.empty")}</p>
        ) : null}
      </div>
    </Card>
  );
}

function ScopedDisputeRegistryPanel({
  issues,
  runId,
}: {
  issues: GovernanceIssueView[];
  runId: string;
}) {
  const authz = useAuthz();
  const scope = useMemo<AuthorityLocalScope | null>(
    () =>
      authz.status === "ready" && authz.user?.tenant_id && authz.user.user_id
        ? {
            tenantId: authz.user.tenant_id,
            userId: authz.user.user_id,
          }
        : null,
    [authz.status, authz.user?.tenant_id, authz.user?.user_id],
  );
  const persistenceBinding = JSON.stringify(
    scope
      ? ["scoped", scope.tenantId, scope.userId, runId]
      : ["unscoped", runId],
  );

  return (
    <DisputeRegistryPanel
      key={persistenceBinding}
      issues={issues}
      runId={runId}
      scope={scope}
    />
  );
}

export { ScopedDisputeRegistryPanel as DisputeRegistryPanel };
