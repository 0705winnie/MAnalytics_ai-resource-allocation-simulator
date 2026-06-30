/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        hud: {
          accent: "#60a5fa",
          "accent-hover": "#3b82f6",
          positive: "#a3e635",
          "positive-hover": "#84cc16",
        },
      },
      boxShadow: {
        "hud-accent": "0 0 15px rgba(59, 130, 246, 0.35)",
        "hud-positive": "0 0 12px rgba(163, 230, 53, 0.28)",
      },
    },
  },
  plugins: [],
};
