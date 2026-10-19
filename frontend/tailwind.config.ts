import type { Config } from 'tailwindcss'
import colors from 'tailwindcss/colors'
import typography from '@tailwindcss/typography'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // The Setu accent. Change this one line to re-theme the whole app.
      colors: { brand: colors.green },
      // `short:` applies on short windows (e.g. laptops with browser chrome) so the welcome screen still fits.
      screens: { short: { raw: '(max-height: 760px)' } },
      keyframes: {
        'typing-dot': { '0%, 80%, 100%': { opacity: '0.25' }, '40%': { opacity: '1' } },
        'fade-in': { from: { opacity: '0', transform: 'translateY(4px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
      animation: { 'typing-dot': 'typing-dot 1.2s infinite ease-in-out', 'fade-in': 'fade-in 200ms ease-out' },
    },
  },
  plugins: [typography],
} satisfies Config
