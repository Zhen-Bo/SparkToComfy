/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        // observatory palette — direct tokens
        dome: 'hsl(var(--dome))',
        plate: 'hsl(var(--plate))',
        elevated: 'hsl(var(--elevated))',
        inset: 'hsl(var(--inset))',
        hairline: 'hsl(var(--hairline))',
        edgeline: 'hsl(var(--edgeline))',
        control: 'hsl(var(--control))',
        amber: {
          DEFAULT: 'hsl(var(--amber))',
          bright: 'hsl(var(--amber-bright))',
          dim: 'hsl(var(--amber-dim))',
        },
        'ink-faint': 'hsl(var(--ink-faint))',
        'plate-bg': 'hsl(var(--plate-bg))',
        overlay: 'hsl(var(--overlay))',
        glow: 'hsl(var(--glow))',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['"Taipei Sans TC"', 'system-ui', 'sans-serif'],
        disp: ['"Chakra Petch"', '"Taipei Sans TC"', 'sans-serif'],
        mono: ['"Chivo Mono"', '"Taipei Sans TC"', 'monospace'],
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        /* Zoom in: only for elements with no translate of their own.
           See Dialog.vue, where the centering box and the animation box are separate. */
        'zoom-in': {
          from: { opacity: '0', transform: 'scale(.97)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        /* Exit is faster than entry.
           It touches opacity only, never transform, so it cannot override the -translate-x/y-1/2 centering utility on DialogContent. */
        'fade-out': {
          from: { opacity: '1' },
          to: { opacity: '0' },
        },
      },
      animation: {
        'fade-in': 'fade-in .15s ease-out',
        'zoom-in': 'zoom-in .18s ease-out',
        'fade-out': 'fade-out .13s ease-out',
      },
    },
  },
  plugins: [],
}
