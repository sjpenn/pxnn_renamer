/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./frontend/templates/**/*.html'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Manrope', 'sans-serif'],
        mono: ['Geist Mono', 'monospace'],
      },
      colors: {
        stage:          '#0a0b0f',
        'stage-raised': '#13151c',
        'stage-sunken': '#07080b',
        rail:           '#1c1f2a',
        hairline:       '#232836',
        ink:            '#eef2ff',
        'ink-dim':      '#8b92a8',
        'ink-mute':     '#7a8299',
        cyan:           '#00f0ff',
        'cyan-soft':    '#0088a3',
        magenta:        '#ff2d95',
        amber:          '#ffb300',
        success:        '#2de89a',
        danger:         '#ff4e5b',
      },
      boxShadow: {
        'glow-cyan':    '0 0 24px rgba(0, 240, 255, 0.18)',
        'glow-magenta': '0 0 24px rgba(255, 45, 149, 0.18)',
      },
    },
  },
  plugins: [],
};
