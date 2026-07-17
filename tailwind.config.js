/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        hud: {
          // Berkeley Blue — primary accent (nav, focus, links, structural highlights)
          accent: "#002676",
          "accent-hover": "#173F7A",
          // Success/validation green — kept as a distinct semantic color from
          // the two brand accents (checkmarks, "done" states, completed steps)
          positive: "#2E7D32",
          "positive-hover": "#256A28",
          // California Gold — secondary accent, used sparingly for the most
          // important calls to action (primary run button, save, next-step CTAs)
          gold: "#FDB515",
          "gold-hover": "#E3A30E",
        },
        // Light theme neutrals — soft blue-gray, not plain gray
        paper: "#F4F7FA",       // page background
        well: "#EEF3F9",        // recessed panels: code blocks, inputs, nested banners
        chip: "#E7EDF5",        // pill/badge/chip background
        line: "#DCE3EC",        // default border
        "line-strong": "#C3D0DF", // stronger border: inputs, dividers, secondary buttons
        ink: "#0F2247",              // primary text / headings — dark navy
        "ink-dim": "#3E5872",        // secondary / body text
        "ink-faint": "#5B7290",      // tertiary / label text
        "ink-faintest": "#8598AF",   // placeholder / disabled / faint text
      },
      boxShadow: {
        "hud-accent": "0 0 0 3px rgba(0, 38, 118, 0.15)",
        "hud-positive": "0 0 0 3px rgba(46, 125, 50, 0.18)",
        card: "0 1px 2px rgba(15, 34, 71, 0.04), 0 2px 10px rgba(15, 34, 71, 0.05)",
      },
    },
  },
  plugins: [],
};
