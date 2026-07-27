/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        blinkit: {
          green: "#0c831f",
          "green-dark": "#0a6e19",
          "green-light": "#e8f5e9",
          yellow: "#f8cb46",
          "yellow-dark": "#e6b73a",
        },
      },
      borderRadius: {
        xl2: "1.25rem",
      },
      boxShadow: {
        soft: "0 4px 14px rgba(0,0,0,0.08)",
      },
    },
  },
  plugins: [],
};
