/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Segoe UI', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Consolas', 'monospace'],
      },
      colors: {
        navy: { 950: '#0a1f38', 900: '#0f2a4a', 800: '#163a63', 700: '#1f4c80', 600: '#2b5f9e', 100: '#e3ebf5', 50: '#f1f5fa' },
        brand: { 700: '#9a3412', 600: '#c2410c', 500: '#ea7a1e', 400: '#f59e0b', 100: '#ffedd5', 50: '#fff7ed' },
        canvas: '#f3f5f8',
      },
      boxShadow: { card: '0 1px 2px rgba(15,42,74,.06), 0 1px 3px rgba(15,42,74,.04)' },
      keyframes: {
        pulsering: { '0%': { boxShadow: '0 0 0 0 rgba(234,122,30,.45)' }, '100%': { boxShadow: '0 0 0 10px rgba(234,122,30,0)' } },
        slidein: { '0%': { opacity: 0, transform: 'translateY(6px)' }, '100%': { opacity: 1, transform: 'none' } },
        shimmer: { '0%': { backgroundPosition: '-400px 0' }, '100%': { backgroundPosition: '400px 0' } },
      },
      animation: {
        pulsering: 'pulsering 1.4s ease-out infinite',
        slidein: 'slidein .25s ease-out',
        shimmer: 'shimmer 1.4s linear infinite',
      },
    },
  },
  plugins: [],
}
