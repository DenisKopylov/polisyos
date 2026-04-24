import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/ibm-plex-mono/cyrillic-ext-400.css";
import "@fontsource/ibm-plex-mono/cyrillic-ext-500.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "@fontsource/manrope/cyrillic-ext-400.css";
import "@fontsource/manrope/cyrillic-ext-500.css";
import "@fontsource/manrope/cyrillic-ext-600.css";
import "@fontsource/manrope/cyrillic-ext-700.css";
import "@fontsource/manrope/cyrillic-ext-800.css";
import "@fontsource/manrope/latin-400.css";
import "@fontsource/manrope/latin-500.css";
import "@fontsource/manrope/latin-600.css";
import "@fontsource/manrope/latin-700.css";
import "@fontsource/manrope/latin-800.css";
import { registerSW } from "virtual:pwa-register";

import App from "./app/App";
import { AppProviders } from "./app/providers/AppProviders";
import "./i18n/typography/plexCyrillicFix.css";
import "./styles.css";

if (typeof window !== "undefined" && !window.__RUNTIME_DASHBOARD_TEST__) {
  registerSW({
    immediate: false,
  });
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AppProviders>
      <App />
    </AppProviders>
  </React.StrictMode>,
);
