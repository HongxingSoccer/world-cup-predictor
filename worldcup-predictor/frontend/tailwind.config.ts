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
          50:  '#ecfeff',
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2',
          700: '#0e7490',
          900: '#164e63',
        },
        accent: {
          // Tasteful amber for hero numbers (ROI, hit rate, key probabilities).
          400: '#fbbf24',
          500: '#f59e0b',
        },
        ink: {
          // Background gradient anchors — used by globals.css.
          950: '#070b15',
          900: '#0a0e1a',
          800: '#0f172a',
          700: '#1e293b',
          600: '#334155',
        },
        signal: {
          strong: '#34d399',  // ⭐⭐⭐ emerald
          medium: '#fbbf24',  // ⭐⭐  amber
          weak:   '#22d3ee',  // ⭐    cyan
          none:   '#64748b',  // 0
        },
      },
      boxShadow: {
        // Subtle cyan glow for cards on hover — restrained, not gaudy.
        'glow-cyan': '0 0 0 1px rgba(34, 211, 238, 0.16), 0 8px 32px -12px rgba(34, 211, 238, 0.35)',
      },
      animation: {
        'pulse-soft': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      backgroundImage: {
        'app-gradient':
          'radial-gradient(at 20% 0%, rgba(8, 145, 178, 0.18) 0px, transparent 50%), radial-gradient(at 100% 100%, rgba(245, 158, 11, 0.08) 0px, transparent 60%), linear-gradient(180deg, #070b15 0%, #0a0e1a 50%, #0f172a 100%)',
      },
    },
  },
  plugins: [],
};

export default config;
