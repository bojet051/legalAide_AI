/** @type {import('tailwindcss').Config} */
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          navy: "#0b2242",
          slate: "#1f2937",
          gold: "#d8b055",
          sky: "#e5edf7",
        },
      },
    },
  },
  plugins: [],
}
