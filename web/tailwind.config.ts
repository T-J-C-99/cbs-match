import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        cbs: {
          navy: "#1D3557",
          ink: "#0F2742",
          columbia: "#B9D9EB",
          sky: "#EAF4FA",
          slate: "#5C6B7A",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
