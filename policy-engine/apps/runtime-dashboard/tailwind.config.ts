import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      colors: {
        sand: "var(--sand)",
        paper: "var(--paper)",
        ink: "var(--ink)",
        graphite: "var(--graphite)",
        slate: "var(--slate)",
        teal: {
          DEFAULT: "var(--teal)",
          soft: "var(--teal-soft)",
        },
        ember: {
          DEFAULT: "var(--ember)",
          soft: "var(--ember-soft)",
        },
        gold: {
          DEFAULT: "var(--gold)",
          soft: "var(--gold-soft)",
        },
        panel: "var(--panel)",
        panelStrong: "var(--panel-strong)",
        surface: "var(--surface)",
        canvas: "var(--canvas)",
        line: "var(--line)",
        text: "var(--text)",
        muted: "var(--muted)",
        accent: "var(--accent)",
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
      },
      boxShadow: {
        panel: "0 24px 70px rgba(24, 28, 31, 0.16)",
      },
    },
  },
  plugins: [],
} satisfies Config;
