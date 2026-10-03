/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0A0A",
        surface: "#141414",
        card: "#1C1C1C",
        line: "#2A2A2A",
        action: "#FF6A00",
        "action-hover": "#FF8533",
        copy: "#F5F5F5",
        muted: "#9A9A9A",
        err: "#E5484D",
      },
      fontFamily: {
        sans: ["'Fira Sans'", "sans-serif"],
        display: ["'Museo Sans'", "'Fira Sans'", "sans-serif"],
      },
    },
  },
  plugins: [],
};
