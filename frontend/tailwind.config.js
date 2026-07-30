/**
 * Design tokens from CLAUDE.md Section 9.
 * Two audiences, two looks, one token file:
 *  - consumer.*  : calm, trust-forward, light, deep-teal accent
 *  - authority.* : serious dark command-center
 *  - verdict.*   : colour-blind-safe semantic colours (always paired with
 *                  an icon + label in the UI, never colour alone)
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Consumer app (light, trust-forward)
        consumer: {
          bg: "#F5F7FA",
          surface: "#FFFFFF",
          ink: "#141A22",
          muted: "#5B6472",
          accent: "#0B6E7A", // guardian teal — calm authority
          "accent-dark": "#095059",
        },
        // Authority dashboard (dark institutional command center)
        authority: {
          base: "#0E1522",
          surface: "#18212F",
          border: "#26303F",
          text: "#E6EAF2",
          muted: "#8A97AC",
          cyan: "#22B8CF",
          amber: "#E0A020",
          red: "#FF4D4D",
        },
        // Verdict semantics (colour-blind-safe pairings)
        verdict: {
          safe: "#1B8A5A",
          suspicious: "#C77A0A",
          danger: "#D12E2E",
        },
        // The signature interrupt red
        interrupt: "#C4161C",
      },
      fontFamily: {
        display: ['"Archivo"', '"Space Grotesk"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        phone: "0 20px 60px -12px rgba(11, 22, 34, 0.35)",
        card: "0 1px 3px rgba(20, 26, 34, 0.08), 0 1px 2px rgba(20,26,34,0.04)",
      },
      keyframes: {
        "pulse-ring": {
          "0%, 100%": { opacity: "0.9" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        "pulse-ring": "pulse-ring 1.1s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
