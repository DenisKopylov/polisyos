import { useMaybeAuthz } from "@/app/authz/AuthzProvider";
import { useFeatureFlags } from "@/app/providers/FeatureFlagProvider";
import { PrefetchNavLink } from "@/app/routes/PrefetchNavLink";
import { getWorkspaceNavigationWithOptions } from "@/app/workspaces";
import { getBlockedRunCount, useRunsSample } from "@/features/runs";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn } from "@/lib/utils";

export default function Sidebar() {
  const { t } = useI18n();
  const { flags } = useFeatureFlags();
  const authz = useMaybeAuthz();
  const runsQuery = useRunsSample();
  const blockedCount = getBlockedRunCount(runsQuery.data?.runs ?? []);
  const navigation = getWorkspaceNavigationWithOptions(flags, {
    isAllowed: (workspace) =>
      authz ? authz.isWorkspaceAllowed(workspace.key) : true,
  });

  return (
    <aside
      className="side-rail"
      data-testid="shell-sidebar"
      aria-label={t("shell.navAriaLabel")}
    >
      <div>
        <p className="eyebrow">{t("shell.eyebrow")}</p>
        <h1 className="mt-2">{t("shell.title")}</h1>
        <p className="mt-4 text-sm leading-7 text-[rgba(245,240,230,0.72)]">
          {t("shell.subtitle")}
        </p>
      </div>

      <nav aria-label={t("shell.navAriaLabel")}>
        {navigation.map((link) => (
          <PrefetchNavLink
            key={link.path}
            to={link.path}
            data-testid={`shell-nav-${link.key}`}
            prefetch="intent"
            className={({ isActive }) => cn("block", isActive ? "active" : "")}
          >
            {t(`shell.nav.${link.key}`)}
          </PrefetchNavLink>
        ))}
      </nav>

      <div className="rail-card">
        <p className="eyebrow">{t("shell.watchStatusTitle")}</p>
        <strong>
          {blockedCount > 0
            ? t("shell.watchStatusBlocked")
            : t("shell.watchStatusStable")}
        </strong>
        <span>
          {blockedCount > 0
            ? t("shell.watchStatusBlockedDetail", {
                count: String(blockedCount),
              })
            : t("shell.watchStatusStableDetail")}
        </span>
      </div>
    </aside>
  );
}
