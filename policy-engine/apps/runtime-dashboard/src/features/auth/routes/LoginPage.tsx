import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { buildLoginNavigationTarget } from "@/features/auth/domain/loginRedirect";
import { parseLoginSearchParams } from "@/features/auth/domain/searchParams";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Button, Card } from "@polisyos/atlas-ui";

export default function LoginPage() {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const { next: nextPath } = parseLoginSearchParams(searchParams);
  const loginTarget = useMemo(
    () => buildLoginNavigationTarget(nextPath),
    [nextPath],
  );

  return (
    <main
      className="mx-auto flex min-h-screen w-full max-w-3xl items-center px-6 py-10"
      data-testid="login-page"
    >
      <Card className="w-full space-y-4">
        <div>
          <p className="eyebrow">{t("pages.login.eyebrow")}</p>
          <h1 className="mt-2 text-3xl font-semibold">
            {t("pages.login.title")}
          </h1>
          <p className="text-muted mt-3 text-sm">{t("pages.login.body")}</p>
        </div>
        <div className="bg-surface/70 border-line text-muted rounded-2xl border p-4 text-sm">
          {t("pages.login.nextRoute", { next: nextPath })}
        </div>
        <div className="flex flex-wrap gap-2">
          {loginTarget.usesDedicatedLogin ? (
            <Button href={loginTarget.href} variant="primary">
              {t("pages.login.continue")}
            </Button>
          ) : (
            <Button
              type="button"
              variant="primary"
              onClick={() => window.location.assign(nextPath)}
            >
              {t("pages.login.retry")}
            </Button>
          )}
          <Button to="/" variant="ghost">
            {t("pages.login.backHome")}
          </Button>
        </div>
      </Card>
    </main>
  );
}
