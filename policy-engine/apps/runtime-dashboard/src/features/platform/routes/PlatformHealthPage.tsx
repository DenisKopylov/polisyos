import { useCapabilities } from "@/api/hooks/useCapabilities";
import {
  createCapabilitySearchRequest,
  useCapabilitySearch,
} from "@/api/hooks/useCapabilitySearch";
import { useConnectors } from "@/api/hooks/useConnectors";
import { useHealth } from "@/api/hooks/useHealth";
import { useRuns } from "@/api/hooks/useRuns";
import { usePermission } from "@/app/authz/AuthzProvider";
import { useTelemetryReadyMark } from "@/app/providers/TelemetryProvider";
import { PrefetchButton } from "@/app/routes/PrefetchButton";
import { AppearanceSection } from "@/features/platform/settings/AppearanceSection";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatDate, formatNumber } from "@/shared/lib/utils";
import { Badge, Card } from "@polisyos/atlas-ui";
import { ApiErrorAlert, DataFreshnessBadge } from "@/shared/ui";

export default function PlatformHealth() {
  const { t } = useI18n();
  const canLaunchRuns = usePermission("runs.launch");
  const canViewAdminAffordances = usePermission("platform.admin");
  const healthQuery = useHealth();
  const capabilitiesQuery = useCapabilities();
  const capabilitySearchQuery = useCapabilitySearch(
    createCapabilitySearchRequest("", "platform-capability-discovery"),
  );
  const connectorsQuery = useConnectors();
  const runsQuery = useRuns({ limit: 12 });

  const connectors = connectorsQuery.data?.connectors ?? [];
  const capabilityCandidates =
    capabilitySearchQuery.data?.response.results ?? [];
  const capabilityCount = capabilitySearchQuery.data?.response.results.length;
  const capabilityState =
    capabilitySearchQuery.data?.response.frontier.completeness_status ??
    t("common.unknown");

  useTelemetryReadyMark("platform.health.page", { routeId: "platform.health" });

  return (
    <div className="space-y-5" data-testid="platform-page">
      <Card>
        <p className="text-muted text-xs font-semibold tracking-[0.24em] uppercase">
          {t("pages.platform.title")}
        </p>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-3xl font-semibold">
              {t("pages.platform.heroTitle")}
            </h2>
            <p className="text-muted mt-2 max-w-3xl text-sm">
              {t("pages.platform.subtitle")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {healthQuery.data ? (
              <Badge kind={healthQuery.data.status === "ok" ? "ok" : "warn"}>
                {String(healthQuery.data.status ?? t("common.unknown"))}
              </Badge>
            ) : null}
            <DataFreshnessBadge />
            <Badge kind="neutral">Candidate rows: {capabilityCount ?? 0}</Badge>
            <Badge kind="warn">Frontier: {capabilityState}</Badge>
          </div>
        </div>
      </Card>

      <AppearanceSection />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <p className="text-muted text-xs uppercase">
            {t("pages.platform.runtimeStatus")}
          </p>
          <p className="text-2xl font-semibold">
            {String(healthQuery.data?.status ?? t("common.unknown"))}
          </p>
          <p className="text-muted text-xs">
            {healthQuery.data?.service ??
              t("pages.platform.runtimeServiceFallback")}
          </p>
        </Card>
        <Card>
          <p className="text-muted text-xs uppercase">
            {t("pages.platform.capabilityManifest")}
          </p>
          <p className="text-2xl font-semibold">
            {capabilitiesQuery.data?.runtime_api_version ?? t("common.unknown")}
          </p>
          <p className="text-muted text-xs">
            {capabilitiesQuery.data?.default_execution_profile ??
              t("common.unknown")}{" "}
            execution profile
          </p>
          {capabilitiesQuery.isError ? (
            <ApiErrorAlert
              title={t("pages.platform.loadCapabilityManifestError")}
              error={capabilitiesQuery.error}
            />
          ) : null}
        </Card>
        <Card>
          <p className="text-muted text-xs uppercase">
            {t("pages.platform.connectors")}
          </p>
          <p className="text-2xl font-semibold">
            {formatNumber(connectors.filter((item) => item.loaded).length)}
          </p>
          <p className="text-muted text-xs">
            {t("pages.platform.registeredConnectors", {
              count: formatNumber(connectors.length),
            })}
          </p>
        </Card>
        <Card>
          <p className="text-muted text-xs uppercase">
            {t("pages.platform.recentRuns")}
          </p>
          <p className="text-2xl font-semibold">
            {formatNumber(runsQuery.data?.runs.length ?? 0)}
          </p>
          <p className="text-muted text-xs">
            {t("pages.platform.latestControlPlaneSample")}
          </p>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
        <Card>
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-lg font-semibold">
              {t("pages.platform.capabilityRegistry")}
            </h3>
            {canLaunchRuns ? (
              <PrefetchButton
                to="/compose"
                prefetch="intent"
                size="sm"
                variant="ghost"
              >
                {t("pages.platform.useInComposer")}
              </PrefetchButton>
            ) : (
              <span className="text-muted text-xs">
                {t("common.accessDenied")}
              </span>
            )}
          </div>
          {capabilitySearchQuery.isLoading ? (
            <p className="text-muted text-sm">
              Loading candidate capability rows...
            </p>
          ) : null}
          {capabilitySearchQuery.isError ? (
            <ApiErrorAlert
              title="Unable to search capability registry"
              error={capabilitySearchQuery.error}
            />
          ) : null}
          {!capabilitySearchQuery.isLoading &&
          !capabilitySearchQuery.isError ? (
            <div className="space-y-3">
              {capabilityCandidates.map((candidate) => (
                <div
                  key={candidate.capability_ref}
                  className="bg-surface/80 border-line rounded-2xl border p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold">{candidate.label}</p>
                      <p className="text-muted mt-1 text-sm">
                        {candidate.description}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge kind="neutral">
                        Candidate · {candidate.discovery_result.state}
                      </Badge>
                      <span className="border-line bg-panel text-muted rounded-full border px-2 py-1 text-xs">
                        {candidate.resource_kind} ·{" "}
                        {candidate.execution_result.state} ·{" "}
                        {candidate.authority_result.state}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
              {capabilitySearchQuery.data &&
              capabilityCandidates.length === 0 ? (
                <p className="text-muted text-sm">
                  No candidate rows · {capabilityState}
                  {capabilitySearchQuery.data.response.frontier
                    .incompleteness_reasons.length > 0
                    ? " · " +
                      capabilitySearchQuery.data.response.frontier.incompleteness_reasons.join(
                        ", ",
                      )
                    : ""}
                </p>
              ) : null}
            </div>
          ) : null}
        </Card>

        <div className="space-y-4">
          {canViewAdminAffordances ? (
            <Card>
              <h3 className="text-lg font-semibold">
                {t("pages.platform.constraints")}
              </h3>
              {capabilitiesQuery.data ? (
                <div className="mt-3 space-y-2 text-sm">
                  {Object.entries(capabilitiesQuery.data.constraints ?? {}).map(
                    ([key, value]) => (
                      <div
                        key={key}
                        className="bg-surface/80 border-line rounded-xl border px-3 py-2"
                      >
                        <p className="text-muted text-xs uppercase">{key}</p>
                        <p className="font-semibold">
                          {typeof value === "object"
                            ? JSON.stringify(value)
                            : String(value)}
                        </p>
                      </div>
                    ),
                  )}
                </div>
              ) : null}
            </Card>
          ) : null}

          <Card>
            <h3 className="text-lg font-semibold">
              {t("pages.platform.runtimeHealth")}
            </h3>
            {healthQuery.isError ? (
              <ApiErrorAlert
                title={t("pages.platform.loadRuntimeHealthError")}
                error={healthQuery.error}
              />
            ) : null}
            {healthQuery.data ? (
              <div className="mt-3 space-y-2 text-sm">
                <div className="bg-surface/80 border-line rounded-xl border px-3 py-2">
                  <p className="text-muted text-xs uppercase">
                    {t("pages.platform.service")}
                  </p>
                  <p className="font-semibold">
                    {healthQuery.data.service ??
                      t("pages.platform.runtimeFallback")}
                  </p>
                </div>
                <div className="bg-surface/80 border-line rounded-xl border px-3 py-2">
                  <p className="text-muted text-xs uppercase">
                    {t("pages.platform.timestamp")}
                  </p>
                  <p className="font-semibold">
                    {formatDate(healthQuery.data.ts)}
                  </p>
                </div>
              </div>
            ) : null}
          </Card>

          <Card>
            <h3 className="text-lg font-semibold">
              {t("pages.platform.connectorReadiness")}
            </h3>
            {connectors.slice(0, 5).map((connector) => (
              <div
                key={connector.connector_id}
                className="bg-surface/80 border-line mt-2 rounded-xl border px-3 py-2 text-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">{connector.connector_id}</p>
                  <Badge kind={connector.loaded ? "ok" : "warn"}>
                    {connector.loaded
                      ? t("pages.platform.connectorHealthy")
                      : t("pages.platform.connectorUnavailable")}
                  </Badge>
                </div>
                <p className="text-muted mt-1 text-xs">
                  {connector.last_health_check
                    ? formatDate(connector.last_health_check)
                    : t("pages.platform.noHealthCheckYet")}
                </p>
              </div>
            ))}
          </Card>
        </div>
      </div>
    </div>
  );
}
