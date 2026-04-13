/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./frontend/templates/**/*.html'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Manrope', 'sans-serif'],
        mono: ['Geist Mono', 'monospace'],
        editorial: ['"DM Sans"', 'sans-serif'],
      },
      colors: {
        stage:          'var(--color-stage)',
        'stage-raised': 'var(--color-stage-raised)',
        'stage-sunken': 'var(--color-stage-sunken)',
        rail:           'var(--color-rail)',
        hairline:       'var(--color-hairline)',
        ink:            'var(--color-ink)',
        'ink-dim':      'var(--color-ink-dim)',
        'ink-mute':     'var(--color-ink-mute)',
        cyan:           'var(--color-cyan)',
        'cyan-soft':    'var(--color-cyan-soft)',
        magenta:        'var(--color-magenta)',
        amber:          'var(--color-amber)',
        success:        'var(--color-success)',
        danger:         'var(--color-danger)',
      },
      boxShadow: {
        'glow-cyan':    '0 0 24px rgba(0, 240, 255, 0.18)',
        'glow-magenta': '0 0 24px rgba(255, 45, 149, 0.18)',
      },
    },
  },
  plugins: [],
};
