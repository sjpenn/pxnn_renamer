/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./frontend/templates/**/*.html'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', 'sans-serif'],
        display: ['"DM Sans"', 'sans-serif'],
        mono: ['Geist Mono', 'monospace'],
        editorial: ['"DM Sans"', 'sans-serif'],
      },
      colors: {
        // rgb(var(--x-rgb) / <alpha-value>) enables opacity modifiers like bg-cyan/10.
        // The -rgb triplet variables are defined in base.html alongside the hex tokens.
        stage:          'rgb(var(--color-stage-rgb) / <alpha-value>)',
        'stage-raised': 'rgb(var(--color-stage-raised-rgb) / <alpha-value>)',
        'stage-sunken': 'rgb(var(--color-stage-sunken-rgb) / <alpha-value>)',
        rail:           'rgb(var(--color-rail-rgb) / <alpha-value>)',
        hairline:       'var(--color-hairline)',
        ink:            'rgb(var(--color-ink-rgb) / <alpha-value>)',
        'ink-dim':      'rgb(var(--color-ink-dim-rgb) / <alpha-value>)',
        'ink-mute':     'rgb(var(--color-ink-mute-rgb) / <alpha-value>)',
        'ink-soft':     'rgb(var(--color-ink-soft-rgb) / <alpha-value>)',
        cyan:           'rgb(var(--color-cyan-rgb) / <alpha-value>)',
        'cyan-soft':    'rgb(var(--color-cyan-soft-rgb) / <alpha-value>)',
        magenta:        'rgb(var(--color-magenta-rgb) / <alpha-value>)',
        amber:          'rgb(var(--color-amber-rgb) / <alpha-value>)',
        success:        'rgb(var(--color-success-rgb) / <alpha-value>)',
        danger:         'rgb(var(--color-danger-rgb) / <alpha-value>)',
      },
      boxShadow: {
        'glow-cyan':    '0 0 24px rgba(201, 166, 107, 0.10)',
        'glow-magenta': 'none',
      },
    },
  },
  plugins: [],
};
