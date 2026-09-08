import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0b0e14",
        surface: "#131722",
        border: "#1f2430",
        accent: "#5b8cff",
      },
    },
  },
  plugins: [],
};
export default config;
