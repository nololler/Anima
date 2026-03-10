/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Syne"', 'sans-serif'],
        body: ['"IBM Plex Mono"', 'monospace'],
        ui: ['"DM Sans"', 'sans-serif'],
      },
      colors: {
        void: '#07080a',
        surface: '#0e1014',
        panel: '#13161b',
        border: '#1e2229',
        muted: '#2a2f3a',
        dim: '#4a5366',
        ghost: '#6b7a94',
        text: '#c8d0e0',
        bright: '#e8edf5',
        accent: '#7c9ef5',
        thought: '#b07cf5',
        kernel: '#4a9e8a',
        warm: '#e5956a',
        danger: '#e56a6a',
        initiated: '#f5c842',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.25s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'blink': 'blink 1s step-end infinite',
      },
      keyframes: {
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        pulseSoft: { '0%,100%': { opacity: 0.6 }, '50%': { opacity: 1 } },
        blink: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } },
      },
    },
  },
  plugins: [],
}
