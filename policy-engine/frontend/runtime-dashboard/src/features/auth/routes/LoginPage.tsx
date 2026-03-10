import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { parseLoginSearchParams } from "@/features/auth/domain/searchParams";
import { useI18n } from "@/i18n/LocaleProvider";
import { LOGIN_PATH, LOGIN_URL } from "@/lib/constants";
import { Button, Card } from "@/shared/ui";

function buildLoginHref(nextPath: string) {
  if (LOGIN_URL.startsWith("/")) {
    return nextPath || "/";
  }
  const url = new URL(LOGIN_URL);
  url.searchParams.set("next", nextPath || "/");
  return url.toString();
}

export default function LoginPage() {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const { next: nextPath } = parseLoginSearchParams(searchParams);
  const loginHref = useMemo(() => buildLoginHref(nextPath), [nextPath]);
  const usesExternalLogin = LOGIN_URL !== LOGIN_PATH;

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
          <p className="mt-3 text-sm text-muted">{t("pages.login.body")}</p>
        </div>
        <div className="bg-surface/70 rounded-2xl border border-line p-4 text-sm text-muted">
          {t("pages.login.nextRoute", { next: nextPath })}
        </div>
        <div className="flex flex-wrap gap-2">
          {usesExternalLogin ? (
            <Button href={loginHref} variant="primary">
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
