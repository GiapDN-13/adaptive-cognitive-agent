import type { Config } from 'tailwindcss'
import typography from '@tailwindcss/typography'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#0E7C6B',
        surface: '#141414',
        bg: '#0a0a0a',
      },
    },
  },
  plugins: [typography],
} satisfies Config
