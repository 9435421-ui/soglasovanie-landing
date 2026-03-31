/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        terion: {
          green: '#2E7D32',
          black: '#1A1A1A',
          white: '#F8F9FA',
          amber: '#FF6F00',
          blue: '#1976D2',
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
