import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Space Grotesk", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      colors: {
        panel: "var(--panel)",
        canvas: "var(--canvas)",
        line: "var(--line)",
        text: "var(--text)",
        muted: "var(--muted)",
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
      },
      boxShadow: {
        panel: "0 10px 30px rgba(9, 23, 43, 0.15)",
      },
    },
  },
  plugins: [],
} satisfies Config;
