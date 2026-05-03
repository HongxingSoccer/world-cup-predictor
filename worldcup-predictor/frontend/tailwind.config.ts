import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      fontFamily: {
        // Project standard: Noto Sans SC for Chinese, with platform fallbacks.
        sans: [
          'Noto Sans SC',
          'PingFang SC',
          'system-ui',
          '-apple-system',
          'sans-serif',
        ],
      },
      colors: {
        brand: {
          50:  '#f0fdf4',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          900: '#14532d',
        },
        signal: {
          strong: '#22c55e',  // ⭐⭐⭐
          medium: '#f59e0b',  // ⭐⭐
          weak:   '#3b82f6',  // ⭐
          none:   '#64748b',  // 0
        },
      },
      animation: {
        'pulse-soft': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
};

export default config;
