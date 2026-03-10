/// <reference types="vite-plugin-pwa/client" />

export {};

interface ImportMetaEnv {
  readonly VITE_AUTH_REFRESH_URL?: string;
  readonly VITE_CSP_REPORT_URI?: string;
  readonly VITE_SENTRY_DSN?: string;
  readonly VITE_SENTRY_ENVIRONMENT?: string;
  readonly VITE_SENTRY_RELEASE?: string;
  readonly VITEST?: boolean;
}

declare global {
  interface Window {
    __RUNTIME_DASHBOARD_FLAGS__?: unknown;
    __RUNTIME_DASHBOARD_TEST__?: boolean;
  }
}
