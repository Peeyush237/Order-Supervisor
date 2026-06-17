import type { Config } from "tailwindcss";

export default {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      colors: {
        canvas: "#f4f5f7",
        line: "#e6e8ec",
      },
    },
  },
  plugins: [],
} satisfies Config;
