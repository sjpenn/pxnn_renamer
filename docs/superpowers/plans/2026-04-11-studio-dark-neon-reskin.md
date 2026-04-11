# Studio Dark / Neon DAW Reskin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current "Precision Slate" look with a Studio Dark / Neon DAW aesthetic across all existing pages, with zero functional regressions.

**Architecture:** Token swap at the Tailwind config layer + a focused `@layer components` block in `static/css/style.css` + per-template class rewrites + 4 inline SVG partials + 2 hero photos. No new routes, no componentization of `app.html`, no build step introduced.

**Tech Stack:** Tailwind CSS (CDN), Jinja2, HTMX, vanilla JS, Material Symbols Outlined, Geist Mono / Inter / Manrope (Google Fonts, already loaded).

**Spec reference:** `docs/superpowers/specs/2026-04-11-studio-dark-neon-reskin-design.md`
**Stitch reference screenshots:** `docs/stitch-reference/`

---

## Files & Responsibilities

| Path | Responsibility | Action |
|---|---|---|
| `frontend/templates/base.html` | Global Tailwind config, body class, noise overlay | Modify |
| `frontend/static/css/style.css` | Component utilities (`.btn-*`, `.card*`, `.input`, `.table`, `.pill-*`, `.glow-cyan`, `.hairline`, `.shadow-glow-cyan`, hero photo recipe, noise overlay). Legacy classes (`wizard-step`, `dropzone`, `token-chip`, `filename-*`, `feature-card`) retuned to new tokens. | Modify |
| `frontend/templates/partials/svg/waveform_line.html` | Reusable sinusoidal waveform SVG | Create |
| `frontend/templates/partials/svg/eq_bars.html` | Animated EQ bars SVG | Create |
| `frontend/templates/partials/svg/spectrogram_grid.html` | Dotted grid background SVG | Create |
| `frontend/templates/partials/svg/wordmark_glyph.html` | Cyan square-waveform nav glyph SVG | Create |
| `frontend/templates/partials/nav.html` | Top nav reskin | Modify |
| `frontend/templates/partials/footer.html` | Footer reskin | Modify |
| `frontend/templates/home.html` | Landing reskin (8 sections) | Modify |
| `frontend/templates/auth/login.html` | Split-layout reskin | Modify |
| `frontend/templates/auth/register.html` | Mirrored split-layout reskin | Modify |
| `frontend/templates/profile.html` | 5-card reskin + delete dialog | Modify |
| `frontend/templates/app.html` | Wizard reskin (token sweep + 3 targeted sections) | Modify |
| `frontend/static/img/hero/studio-hero.jpg` | Home hero background photo | Create |
| `frontend/static/img/hero/console-panel.jpg` | Auth split-panel photo | Create |
| `frontend/static/img/hero/CREDITS.md` | Photo credits & licenses | Create |
| `docs/superpowers/evidence/2026-04-11-studio-dark-neon-reskin/` | Playwright screenshots (before/after) | Create |

---

## Conventions

Because this is a visual reskin, "tests" are:

1. **Grep gates** — after each file is touched, a `grep` for specific legacy tokens in that file must return zero hits.
2. **Playwright screenshot capture** — before/after shots of every reskinned page at 1280px (desktop) and 375px (mobile for `home.html` + `app.html`).
3. **Smoke click-through** — at the end, manually verify the wizard still completes end-to-end.

Commits are small and conventional (`feat:`, `style:`, `chore:`). Every task ends with a commit.

Use `Grep` (not bash `grep`) per tool discipline.

---

## Task 1: Create feature branch and baseline screenshots

**Files:**
- Create: `docs/superpowers/evidence/2026-04-11-studio-dark-neon-reskin/before/` (directory with Playwright screenshots)

- [ ] **Step 1: Create the feature branch**

```bash
git checkout -b feat/studio-dark-neon-reskin
git status
```

Expected: branch created, clean working tree.

- [ ] **Step 2: Boot the app locally**

```bash
docker-compose up --build -d
```

Wait ~15s, then confirm it's up:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8000/
```

Expected: `200`.

- [ ] **Step 3: Capture baseline screenshots with Playwright MCP**

Create the evidence directory:

```bash
mkdir -p docs/superpowers/evidence/2026-04-11-studio-dark-neon-reskin/before
mkdir -p docs/superpowers/evidence/2026-04-11-studio-dark-neon-reskin/after
```

Then, using `mcp__playwright__browser_navigate` followed by `mcp__playwright__browser_take_screenshot` (full page, PNG), capture all 5 routes at 1280px viewport:

| URL | Filename |
|---|---|
| `http://localhost:8000/` | `before/home-1280.png` |
| `http://localhost:8000/login` | `before/login-1280.png` |
| `http://localhost:8000/register` | `before/register-1280.png` |
| `http://localhost:8000/app` (redirects if logged out — accept) | `before/app-1280.png` |
| `http://localhost:8000/profile` (redirects if logged out — accept) | `before/profile-1280.png` |

Before capturing each, resize viewport: `mcp__playwright__browser_resize` with `width=1280, height=900`.

Also capture mobile (`width=375, height=812`) for home and app:
- `before/home-375.png`
- `before/app-375.png`

- [ ] **Step 4: Commit the baseline evidence**

```bash
git add docs/superpowers/evidence/2026-04-11-studio-dark-neon-reskin/before/
git commit -m "chore(evidence): capture baseline screenshots before reskin"
```

---

## Task 2: Replace Tailwind config tokens in base.html

**Files:**
- Modify: `frontend/templates/base.html`

- [ ] **Step 1: Replace the `tailwind.config` block**

Open `frontend/templates/base.html`. Replace the entire `<script>tailwind.config = {...}</script>` block (lines 18–47) with:

```html
<script>
    tailwind.config = {
        theme: {
            extend: {
                fontFamily: {
                    sans: ['Inter', 'sans-serif'],
                    display: ['Manrope', 'sans-serif'],
                    mono: ['Geist Mono', 'monospace'],
                },
                colors: {
                    stage:           '#0a0b0f',
                    'stage-raised':  '#13151c',
                    'stage-sunken':  '#07080b',
                    rail:            '#1c1f2a',
                    hairline:        '#232836',
                    ink:             '#eef2ff',
                    'ink-dim':       '#8b92a8',
                    'ink-mute':      '#545a6e',
                    cyan:            '#00f0ff',
                    'cyan-soft':     '#0088a3',
                    magenta:         '#ff2d95',
                    amber:           '#ffb300',
                    success:         '#2de89a',
                    danger:          '#ff4e5b',
                },
                boxShadow: {
                    'glow-cyan':    '0 0 24px rgba(0, 240, 255, 0.18)',
                    'glow-magenta': '0 0 24px rgba(255, 45, 149, 0.18)',
                },
            },
        },
    };
</script>
```

Note: the old custom `borderRadius` block (`3xl: 1.5rem`, `4xl: 2rem`) is intentionally removed. Tailwind's built-in `rounded-3xl` (1.5rem) still exists as a default utility, but we won't use it — Task 15 rewrites all `rounded-3xl`/`rounded-4xl` usages.

- [ ] **Step 2: Update the body default class**

In `frontend/templates/base.html`, find the `<body>` line (line 53 in the current file):

```html
<body class="min-h-full font-sans text-deep-slate antialiased {% block body_class %}bg-surface-bright{% endblock %}">
```

Replace with:

```html
<body class="min-h-full font-sans text-ink antialiased relative {% block body_class %}bg-stage{% endblock %}">
```

- [ ] **Step 3: Verify no other tokens leaked into base.html**

Use `Grep` to search `frontend/templates/base.html` for these terms — each must return zero matches:

```
primary-container
primary-fixed
surface-bright
surface-container-high
deep-slate
inverse-surface
inverse-on-surface
```

Expected: 0 matches across the whole file for every term.

- [ ] **Step 4: Commit**

```bash
git add frontend/templates/base.html
git commit -m "feat(theme): swap Tailwind tokens to Studio Dark / Neon DAW palette"
```

---

## Task 3: Add component CSS layer to style.css

**Files:**
- Modify: `frontend/static/css/style.css`

- [ ] **Step 1: Prepend the new component layer**

Open `frontend/static/css/style.css`. Insert this block **at the very top of the file**, before the existing `.app-noise` rule:

```css
/* ================================================================
   STUDIO DARK / NEON DAW — Component layer
   Spec: docs/superpowers/specs/2026-04-11-studio-dark-neon-reskin-design.md
   ================================================================ */

/* --- Noise grain overlay on body ---------------------------------- */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  opacity: 0.02;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");
  mix-blend-mode: overlay;
}
body > * { position: relative; z-index: 1; }

/* --- Buttons ------------------------------------------------------ */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border-radius: 0.75rem; /* 12px / md */
  padding: 0.625rem 1.25rem;
  font-weight: 600;
  font-size: 0.875rem;
  line-height: 1.25rem;
  transition: background-color 150ms ease, border-color 150ms ease, box-shadow 150ms ease, color 150ms ease;
  border: 1px solid transparent;
  cursor: pointer;
}
.btn:focus-visible {
  outline: 2px solid #00f0ff;
  outline-offset: 2px;
}
.btn-primary {
  background-color: #00f0ff;
  color: #0a0b0f;
}
.btn-primary:hover { background-color: #ffffff; box-shadow: 0 0 24px rgba(0,240,255,0.18); }
.btn-primary:disabled { background-color: #1c1f2a; color: #545a6e; cursor: not-allowed; box-shadow: none; }

.btn-ghost {
  background-color: transparent;
  color: #eef2ff;
  border-color: #232836;
}
.btn-ghost:hover { border-color: #00f0ff; color: #00f0ff; }

.btn-danger {
  background-color: transparent;
  color: #ff4e5b;
  border-color: #232836;
}
.btn-danger:hover { background-color: rgba(255,78,91,0.10); border-color: #ff4e5b; }

.btn-icon {
  padding: 0.5rem;
  border-radius: 0.5rem;
  background: transparent;
  color: #8b92a8;
  border: 1px solid transparent;
}
.btn-icon:hover { color: #00f0ff; border-color: #232836; }

/* --- Cards -------------------------------------------------------- */
.card {
  background-color: #13151c;
  border: 1px solid #232836;
  border-radius: 1.25rem; /* 20px / xl */
  padding: 1.5rem;
}
.card-inset {
  background-color: #07080b;
  border: 1px solid #232836;
  border-radius: 1rem; /* 16px / lg */
  padding: 1.25rem;
}
.card-hover { transition: border-color 150ms ease, box-shadow 150ms ease; }
.card-hover:hover { border-color: rgba(0,240,255,0.4); }
.card-active { border-color: #00f0ff; box-shadow: 0 0 24px rgba(0,240,255,0.18); }

/* --- Inputs ------------------------------------------------------- */
.input {
  width: 100%;
  background-color: #07080b;
  border: 1px solid #232836;
  color: #eef2ff;
  border-radius: 0.75rem;
  padding: 0.75rem 1rem;
  font-size: 0.875rem;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}
.input::placeholder { color: #545a6e; }
.input:focus {
  outline: none;
  border-color: #00f0ff;
  box-shadow: 0 0 0 2px rgba(0,240,255,0.30);
}
.input--error { border-color: #ff4e5b; }
.input--error:focus { box-shadow: 0 0 0 2px rgba(255,78,91,0.30); }

.field-label {
  display: block;
  font-size: 0.6875rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #8b92a8;
  margin-bottom: 0.375rem;
  font-family: 'Geist Mono', monospace;
}

/* --- Tables ------------------------------------------------------- */
.ui-table {
  width: 100%;
  font-size: 0.875rem;
  border-collapse: separate;
  border-spacing: 0;
}
.ui-table th {
  text-align: left;
  font-family: 'Inter', sans-serif;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #8b92a8;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #232836;
}
.ui-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #232836;
  font-family: 'Geist Mono', monospace;
  color: #eef2ff;
}
.ui-table tbody tr:hover td {
  background-color: rgba(28, 31, 42, 0.5);
}

/* --- Status pills ------------------------------------------------- */
.pill {
  display: inline-flex;
  align-items: center;
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-radius: 9999px;
  padding: 0.125rem 0.5rem;
  border: 1px solid;
}
.pill-match      { color: #2de89a; background: rgba(45,232,154,0.15); border-color: rgba(45,232,154,0.3); }
.pill-conflict   { color: #ff4e5b; background: rgba(255,78,91,0.15); border-color: rgba(255,78,91,0.3); }
.pill-processing { color: #ffb300; background: rgba(255,179,0,0.15); border-color: rgba(255,179,0,0.3); animation: pill-pulse 1.6s ease-in-out infinite; }
.pill-queued     { color: #8b92a8; background: rgba(139,146,168,0.12); border-color: rgba(139,146,168,0.3); }

@keyframes pill-pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.55; }
}

/* --- Hero photo treatment ----------------------------------------- */
.hero-photo {
  position: relative;
  overflow: hidden;
  background-color: #0a0b0f;
  border-radius: 1.25rem;
}
.hero-photo__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: brightness(0.55) contrast(1.15) saturate(0.9);
}
.hero-photo::after {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, transparent 0%, #0a0b0f 100%),
    radial-gradient(circle at 85% 85%, rgba(255,45,149,0.18), transparent 45%),
    rgba(0,49,58,0.40);
  mix-blend-mode: multiply;
  pointer-events: none;
}

/* --- EQ bars animation (used by eq_bars.html SVG) ----------------- */
@keyframes eq-bar {
  0%, 100% { transform: scaleY(0.35); }
  50%      { transform: scaleY(1); }
}
.eq-bar {
  transform-origin: bottom center;
  animation: eq-bar 1.2s ease-in-out infinite;
}
.eq-bar:nth-child(1) { animation-delay: 0.00s; }
.eq-bar:nth-child(2) { animation-delay: 0.10s; }
.eq-bar:nth-child(3) { animation-delay: 0.22s; }
.eq-bar:nth-child(4) { animation-delay: 0.08s; }
.eq-bar:nth-child(5) { animation-delay: 0.18s; }
.eq-bar:nth-child(6) { animation-delay: 0.30s; }
.eq-bar:nth-child(7) { animation-delay: 0.14s; }
.eq-bar:nth-child(8) { animation-delay: 0.24s; }
```

- [ ] **Step 2: Retune the existing legacy class blocks to new tokens**

Still in `frontend/static/css/style.css`, find and replace these **existing** rules (they live below what you just added). Replace the entire body of each rule with the version below. These keep the same class names so templates that reference them (`wizard-step`, `dropzone`, `token-chip`, `filename-*`, `feature-card`) continue to work.

Replace the entire `.app-noise` block with:

```css
.app-noise {
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at top left, rgba(0, 240, 255, 0.04), transparent 35%),
    radial-gradient(circle at 80% 20%, rgba(255, 45, 149, 0.03), transparent 25%);
}
```

Replace the entire `.nav-link` / `.nav-link:hover` / `.nav-link.active` block with:

```css
.nav-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-radius: 0.75rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #8b92a8;
  transition: all 180ms ease;
}
.nav-link:hover {
  background-color: rgba(28, 31, 42, 0.6);
  color: #eef2ff;
}
.nav-link.active {
  background-color: rgba(0, 240, 255, 0.10);
  color: #00f0ff;
}
```

Replace the entire `.wizard-step` and its variants (`:hover`, `-index`, `-label`, `-copy`, `.is-active`, `.is-complete`, `.is-locked`) with:

```css
.wizard-step {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
  border-radius: 1rem;
  border: 1px solid #232836;
  padding: 1.25rem;
  background-color: #13151c;
  transition: all 180ms ease;
}
.wizard-step:hover {
  border-color: rgba(0, 240, 255, 0.4);
}
.wizard-step-index {
  display: inline-flex;
  height: 2.5rem;
  width: 2.5rem;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  background-color: #1c1f2a;
  color: #8b92a8;
  font-family: 'Manrope', sans-serif;
  font-size: 0.875rem;
  font-weight: 700;
  border: 1px solid #232836;
}
.wizard-step-label {
  display: block;
  font-weight: 600;
  color: #eef2ff;
}
.wizard-step-copy {
  display: block;
  margin-top: 0.25rem;
  color: #8b92a8;
  font-size: 0.875rem;
  line-height: 1.5;
}
.wizard-step.is-active {
  border-color: #00f0ff;
  background-color: #13151c;
  box-shadow: 0 0 24px rgba(0, 240, 255, 0.18);
}
.wizard-step.is-active .wizard-step-index {
  background-color: #00f0ff;
  color: #0a0b0f;
  border-color: #00f0ff;
}
.wizard-step.is-complete {
  border-color: #232836;
  background-color: #13151c;
  opacity: 0.8;
}
.wizard-step.is-complete .wizard-step-index {
  background-color: #2de89a;
  color: #0a0b0f;
  border-color: #2de89a;
}
.wizard-step.is-locked {
  opacity: 0.5;
  background-color: #07080b;
}
```

Replace the entire `.dropzone` / `.dropzone.is-dragging` block with:

```css
.dropzone {
  position: relative;
  overflow: hidden;
  border: 2px dashed #232836;
  background-color: #07080b;
  color: #8b92a8;
  transition: all 220ms ease;
  border-radius: 1rem;
}
.dropzone:hover {
  border-color: rgba(0, 240, 255, 0.5);
}
.dropzone.is-dragging {
  border-color: #00f0ff;
  border-style: solid;
  background-color: rgba(0, 240, 255, 0.05);
  box-shadow: inset 0 0 60px rgba(0, 240, 255, 0.12);
}
```

Replace the entire `.token-chip`, `.field-chip`, `.field-chip-light`, `.field-chip-dark` block with:

```css
.token-chip,
.field-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  padding: 0.25rem 0.625rem;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.025em;
  font-family: 'Geist Mono', monospace;
}
.token-chip {
  background-color: rgba(0, 240, 255, 0.10);
  color: #00f0ff;
  border: 1px solid rgba(0, 240, 255, 0.3);
}
.field-chip-light {
  background-color: rgba(139, 146, 168, 0.12);
  color: #8b92a8;
  border: 1px solid #232836;
}
.field-chip-dark {
  background-color: #1c1f2a;
  color: #eef2ff;
  border: 1px solid #232836;
}
```

Replace the entire `.filename-before`, `.filename-arrow`, `.filename-after` block with:

```css
.filename-before {
  font-family: 'Geist Mono', monospace;
  font-size: 0.95rem;
  color: #ff4e5b;
  text-decoration: line-through;
  text-decoration-color: rgba(255, 78, 91, 0.55);
}
.filename-arrow {
  font-size: 1.25rem;
  color: #00f0ff;
  filter: drop-shadow(0 0 6px rgba(0, 240, 255, 0.6));
}
.filename-after {
  font-family: 'Geist Mono', monospace;
  font-size: 1rem;
  font-weight: 600;
  color: #2de89a;
}
```

Replace the `.feature-card` and `.feature-card:hover` block with:

```css
.feature-card {
  transition: transform 180ms ease-out, border-color 180ms ease-out, box-shadow 180ms ease-out;
}
.feature-card:hover {
  transform: translateY(-4px);
  border-color: rgba(0, 240, 255, 0.4);
  box-shadow: 0 0 24px rgba(0, 240, 255, 0.12);
}
```

- [ ] **Step 3: Verify no old hex colors remain in style.css**

Use `Grep` on `frontend/static/css/style.css` for each of these terms. Each must return zero matches:

```
#0052cc
#dae2ff
#b2c5ff
#0f172a
#64748b
#f1f5f9
#f8f9ff
#233144
#eaf1ff
#0f766e
#ef4444
#e2e8f0
#10b981
```

- [ ] **Step 4: Commit**

```bash
git add frontend/static/css/style.css
git commit -m "feat(css): add Studio Dark component layer and retune legacy classes"
```

---

## Task 4: Create SVG chrome partials

**Files:**
- Create: `frontend/templates/partials/svg/waveform_line.html`
- Create: `frontend/templates/partials/svg/eq_bars.html`
- Create: `frontend/templates/partials/svg/spectrogram_grid.html`
- Create: `frontend/templates/partials/svg/wordmark_glyph.html`

- [ ] **Step 1: Create the waveform line SVG**

Create `frontend/templates/partials/svg/waveform_line.html`:

```html
{# Reusable sinusoidal waveform. Inherits color via currentColor.
   Usage: <div class="text-cyan">{% include "partials/svg/waveform_line.html" %}</div> #}
<svg viewBox="0 0 800 80" xmlns="http://www.w3.org/2000/svg" class="w-full h-auto" preserveAspectRatio="none" aria-hidden="true">
  <path d="M0 40 C 40 5, 80 75, 120 40 S 200 5, 240 40 S 320 75, 360 40 S 440 5, 480 40 S 560 75, 600 40 S 680 5, 720 40 S 800 75, 800 40"
        fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.7"/>
  <path d="M0 40 C 40 20, 80 60, 120 40 S 200 20, 240 40 S 320 60, 360 40 S 440 20, 480 40 S 560 60, 600 40 S 680 20, 720 40 S 800 60, 800 40"
        fill="none" stroke="currentColor" stroke-width="0.8" stroke-linecap="round" opacity="0.35"/>
</svg>
```

- [ ] **Step 2: Create the EQ bars SVG**

Create `frontend/templates/partials/svg/eq_bars.html`:

```html
{# Animated 8-bar EQ. Inherits color via currentColor.
   Animation is driven by .eq-bar keyframes in style.css. #}
<svg viewBox="0 0 80 32" xmlns="http://www.w3.org/2000/svg" class="h-4 w-auto" aria-hidden="true">
  <g fill="currentColor">
    <rect class="eq-bar" x="2"  y="4" width="6" height="24" rx="1"/>
    <rect class="eq-bar" x="12" y="4" width="6" height="24" rx="1"/>
    <rect class="eq-bar" x="22" y="4" width="6" height="24" rx="1"/>
    <rect class="eq-bar" x="32" y="4" width="6" height="24" rx="1"/>
    <rect class="eq-bar" x="42" y="4" width="6" height="24" rx="1"/>
    <rect class="eq-bar" x="52" y="4" width="6" height="24" rx="1"/>
    <rect class="eq-bar" x="62" y="4" width="6" height="24" rx="1"/>
    <rect class="eq-bar" x="72" y="4" width="6" height="24" rx="1"/>
  </g>
</svg>
```

- [ ] **Step 3: Create the spectrogram grid SVG**

Create `frontend/templates/partials/svg/spectrogram_grid.html`:

```html
{# Dotted grid background, intended as an absolute-positioned overlay.
   Usage: wrap content in `relative`, drop this inside with `absolute inset-0 text-cyan opacity-10 pointer-events-none`. #}
<svg xmlns="http://www.w3.org/2000/svg" class="h-full w-full" preserveAspectRatio="none" aria-hidden="true">
  <defs>
    <pattern id="spec-grid" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
      <circle cx="1" cy="1" r="1" fill="currentColor"/>
    </pattern>
  </defs>
  <rect width="100%" height="100%" fill="url(#spec-grid)"/>
</svg>
```

- [ ] **Step 4: Create the wordmark glyph SVG**

Create `frontend/templates/partials/svg/wordmark_glyph.html`:

```html
{# Small square waveform glyph for the nav wordmark. Inherits color via currentColor. #}
<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" aria-hidden="true">
  <rect x="1" y="1" width="22" height="22" rx="4" fill="none" stroke="currentColor" stroke-width="1.5"/>
  <path d="M5 12 L7 12 L7 8 L9 8 L9 16 L11 16 L11 6 L13 6 L13 18 L15 18 L15 10 L17 10 L17 14 L19 14"
        fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/templates/partials/svg/
git commit -m "feat(ui): add reusable SVG chrome partials (waveform, EQ, grid, glyph)"
```

---

## Task 5: Reskin partials/nav.html

**Files:**
- Modify: `frontend/templates/partials/nav.html`

- [ ] **Step 1: Replace the full file contents**

Replace the entire contents of `frontend/templates/partials/nav.html` with:

```html
{# Nav partial. Expects: current_user (User|None), page (string), google_oauth_enabled (bool) #}
<nav class="sticky top-0 z-50 w-full bg-stage-raised/90 backdrop-blur-md border-b border-hairline">
    <div class="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {# Left: logo + marketing links #}
        <div class="flex items-center gap-8">
            <a href="{% if current_user %}/app{% else %}/{% endif %}" class="flex items-center gap-2 font-display font-extrabold text-lg text-ink">
                <span class="text-cyan">{% include "partials/svg/wordmark_glyph.html" %}</span>
                PxNN
            </a>
            {% if page in ['home', 'login', 'register'] %}
            <div class="hidden md:flex items-center gap-6 text-sm font-medium text-ink-dim">
                <a href="/#features" class="hover:text-cyan transition">Features</a>
                <a href="/#pricing" class="hover:text-cyan transition">Pricing</a>
            </div>
            {% endif %}
        </div>

        {# Right: auth state #}
        <div class="flex items-center gap-3">
            {% if current_user %}
                <a href="/app"
                   class="hidden sm:inline-block text-sm font-medium {% if page == 'app' %}text-cyan border-b-2 border-cyan{% else %}text-ink-dim hover:text-cyan{% endif %} transition">
                    Dashboard
                </a>
                <a href="/app?billing=options"
                   class="hidden sm:inline-block text-sm font-medium text-ink-dim hover:text-cyan transition">
                    Billing
                </a>

                {# Avatar dropdown #}
                <div class="relative">
                    <button id="nav-user-dropdown-btn"
                            type="button"
                            class="flex items-center gap-2 rounded-full border border-hairline bg-stage-raised px-3 py-1.5 text-sm font-medium text-ink hover:border-cyan transition focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan">
                        <span class="material-symbols-outlined text-base text-cyan">account_circle</span>
                        <span class="max-w-[120px] truncate">{{ current_user.username }}</span>
                        <span class="material-symbols-outlined text-base">expand_more</span>
                    </button>
                    <div id="nav-user-dropdown-menu"
                         class="hidden absolute right-0 mt-2 w-56 rounded-xl border border-hairline bg-stage-raised py-2 shadow-glow-cyan">
                        <div class="px-4 py-2 text-[11px] font-mono uppercase tracking-widest text-ink-dim">
                            {{ current_user.username }}
                        </div>
                        <a href="/profile"
                           class="block px-4 py-2 text-sm text-ink hover:bg-rail transition">
                            Profile
                        </a>
                        <div class="my-1 border-t border-hairline"></div>
                        <form method="post" action="/api/auth/logout" onsubmit="event.preventDefault(); fetch('/api/auth/logout', {method: 'POST'}).then(() => window.location.href = '/');">
                            <button type="submit"
                                    class="block w-full text-left px-4 py-2 text-sm text-ink hover:bg-rail transition">
                                Logout
                            </button>
                        </form>
                    </div>
                </div>
            {% else %}
                <a href="/login"
                   class="text-sm font-medium {% if page == 'login' %}text-cyan border-b-2 border-cyan{% else %}text-ink-dim hover:text-cyan{% endif %} transition">
                    Sign in
                </a>
                <a href="/register" class="btn btn-primary">
                    Get Started
                </a>
            {% endif %}
        </div>
    </div>
</nav>

<script>
(function() {
    const btn = document.getElementById('nav-user-dropdown-btn');
    const menu = document.getElementById('nav-user-dropdown-menu');
    if (!btn || !menu) return;
    btn.addEventListener('click', function(e) {
        e.stopPropagation();
        menu.classList.toggle('hidden');
    });
    document.addEventListener('click', function() {
        menu.classList.add('hidden');
    });
})();
</script>
```

- [ ] **Step 2: Verify no legacy tokens remain in nav.html**

Use `Grep` on `frontend/templates/partials/nav.html` for each term — must return zero matches:

```
primary-container
surface-bright
deep-slate
outline/
sync_alt
bg-white
```

(`sync_alt` was the old Material icon — replaced by the wordmark glyph.)

- [ ] **Step 3: Commit**

```bash
git add frontend/templates/partials/nav.html
git commit -m "feat(nav): reskin top nav for Studio Dark theme"
```

---

## Task 6: Reskin partials/footer.html

**Files:**
- Modify: `frontend/templates/partials/footer.html`

- [ ] **Step 1: Replace the full file contents**

Replace the entire contents of `frontend/templates/partials/footer.html` with:

```html
<footer class="mt-20 border-t border-hairline bg-stage">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div class="flex items-center gap-2 font-display font-extrabold text-base text-ink">
                <span class="text-cyan">{% include "partials/svg/wordmark_glyph.html" %}</span>
                PxNN
                <span class="ml-2 text-xs font-mono font-normal text-ink-dim uppercase tracking-widest">Bulk audio file renamer</span>
            </div>

            <div class="flex flex-wrap gap-6 text-sm font-medium text-ink-dim">
                <a href="/#features" class="hover:text-cyan transition">Features</a>
                <a href="/#pricing" class="hover:text-cyan transition">Pricing</a>
                <a href="/login" class="hover:text-cyan transition">Login</a>
                <a href="/register" class="hover:text-cyan transition">Register</a>
            </div>

            <div class="flex items-center gap-4 text-xs font-mono uppercase tracking-widest text-ink-dim">
                <span>&copy; 2026 PxNN</span>
                <a href="https://github.com/sjpenn/pxnn_renamer" target="_blank" rel="noopener"
                   class="hover:text-cyan transition" aria-label="GitHub">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.387.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
                </a>
            </div>
        </div>
    </div>
</footer>
```

- [ ] **Step 2: Verify**

Use `Grep` on `frontend/templates/partials/footer.html` — each of these must return zero matches:

```
primary-container
surface-bright
deep-slate
outline/
sync_alt
```

- [ ] **Step 3: Commit**

```bash
git add frontend/templates/partials/footer.html
git commit -m "feat(footer): reskin footer for Studio Dark theme"
```

---

## Task 7: Source and commit hero photos

**Files:**
- Create: `frontend/static/img/hero/studio-hero.jpg`
- Create: `frontend/static/img/hero/console-panel.jpg`
- Create: `frontend/static/img/hero/CREDITS.md`

- [ ] **Step 1: Create the img directory**

```bash
mkdir -p frontend/static/img/hero
```

- [ ] **Step 2: Download two Unsplash photos**

Two specific Unsplash photos to use (both Unsplash License — free for commercial use). Download both and save them with the exact filenames shown:

```bash
curl -sSL -o frontend/static/img/hero/studio-hero.jpg \
  "https://images.unsplash.com/photo-1520166012956-add9ba0835cb?w=1920&q=80&fm=jpg&fit=crop"

curl -sSL -o frontend/static/img/hero/console-panel.jpg \
  "https://images.unsplash.com/photo-1598488035139-bdbb2231ce04?w=1920&q=80&fm=jpg&fit=crop"
```

Photo A (`studio-hero.jpg`) is a dark mixing console from Unsplash photographer `@techivation` — wide-angle shot of an analog board with low warm lighting, used as the full-bleed home hero background.

Photo B (`console-panel.jpg`) is a closeup of a synth control surface with faders and knobs, used for the login/register split panel.

- [ ] **Step 3: Verify file sizes**

```bash
ls -lh frontend/static/img/hero/
```

Expected: both files ≤ 400KB. If either is larger than 400KB, fail this task — the treatment recipe makes file size forgiving, but we don't want oversized downloads on landing.

If a file exceeds 400KB, re-download with a lower quality:

```bash
curl -sSL -o frontend/static/img/hero/studio-hero.jpg \
  "https://images.unsplash.com/photo-1520166012956-add9ba0835cb?w=1600&q=70&fm=jpg&fit=crop"
```

- [ ] **Step 4: Create the credits file**

Create `frontend/static/img/hero/CREDITS.md`:

```markdown
# Hero Photo Credits

Both images are used under the [Unsplash License](https://unsplash.com/license).
The Unsplash License is free for commercial and noncommercial use; attribution is not required but is provided here as good practice.

## studio-hero.jpg
- **Source:** https://unsplash.com/photos/a-mixing-console-with-lots-of-buttons-and-knobs-hD7XZvh9oMU
- **Photo ID:** `photo-1520166012956-add9ba0835cb`
- **Subject:** Analog mixing console, warm key light
- **Used in:** `frontend/templates/home.html` — hero section background

## console-panel.jpg
- **Source:** https://unsplash.com/photos/a-close-up-of-a-dj-s-mixing-board-bdbb2231ce04
- **Photo ID:** `photo-1598488035139-bdbb2231ce04`
- **Subject:** Control surface closeup, faders and knobs
- **Used in:** `frontend/templates/auth/login.html` and `frontend/templates/auth/register.html` — split panel

If either of these images becomes unavailable, source a replacement from Unsplash matching the Section 6.1 brief in `docs/superpowers/specs/2026-04-11-studio-dark-neon-reskin-design.md`.
```

- [ ] **Step 5: Commit**

```bash
git add frontend/static/img/hero/
git commit -m "chore(assets): add 2 hero photos (Unsplash License) with credits"
```

---

## Task 8: Reskin home.html — HERO + PROBLEM sections

**Files:**
- Modify: `frontend/templates/home.html`

- [ ] **Step 1: Replace the HERO section**

In `frontend/templates/home.html`, replace the HERO section (currently lines 8–49, the `<section>` that opens after `{# ============================ HERO ============================ #}`) with:

```html
{# ============================ HERO ============================ #}
<section class="relative overflow-hidden bg-stage">
    {# Background photo, dimmed #}
    <div class="absolute inset-0 hero-photo">
        <img src="/static/img/hero/studio-hero.jpg" alt="" class="hero-photo__img" loading="eager">
    </div>
    {# Dotted spectrogram grid on top of the photo #}
    <div class="absolute inset-0 text-cyan opacity-10 pointer-events-none">
        {% include "partials/svg/spectrogram_grid.html" %}
    </div>

    <div class="relative mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 py-24 md:py-32 text-center">
        <p class="text-[11px] font-mono font-medium uppercase tracking-[0.2em] text-cyan mb-5">&gt; BULK AUDIO FILE RENAMER</p>
        <h1 class="font-display font-extrabold text-4xl md:text-6xl leading-tight text-ink">
            Stop drowning in<br>
            <span class="font-mono text-2xl md:text-4xl text-danger line-through opacity-90">"track_final_v2.wav"</span>
        </h1>
        <p class="mt-6 max-w-2xl mx-auto text-lg md:text-xl text-ink-dim">
            PxNN renames hundreds of audio files at once with clean, consistent, metadata-rich filenames.
        </p>
        <div class="mt-10 flex flex-wrap items-center justify-center gap-4">
            <a href="/register" class="btn btn-primary px-6 py-3">
                Get Started Free
            </a>
            <a href="#how-it-works" class="btn btn-ghost px-6 py-3">
                See how it works
            </a>
        </div>

        {# Hero animation card #}
        <div class="mt-14 mx-auto max-w-2xl card">
            <div class="filename-stack">
                <div class="filename-pair">
                    <div class="filename-before">track_final_v2_FIX (1).wav</div>
                    <div class="filename-arrow material-symbols-outlined">arrow_downward</div>
                    <div class="filename-after">JuneLake_Nightfall_Cmin_128BPM_2026.wav</div>
                </div>
                <div class="filename-pair">
                    <div class="filename-before">beat ideas 03 FULL.wav</div>
                    <div class="filename-arrow material-symbols-outlined">arrow_downward</div>
                    <div class="filename-after">JuneLake_Sunset_Amin_90BPM_2026.wav</div>
                </div>
                <div class="filename-pair">
                    <div class="filename-before">Untitled Project 14.aif</div>
                    <div class="filename-arrow material-symbols-outlined">arrow_downward</div>
                    <div class="filename-after">JuneLake_HorizonLine_Gmaj_120BPM_2026.aif</div>
                </div>
            </div>
        </div>
    </div>
</section>
```

- [ ] **Step 2: Replace the PROBLEM section**

Replace the PROBLEM section (currently at line 51, the `<section id="problem">`) with:

```html
{# ============================ PROBLEM ============================ #}
<section id="problem" class="py-20 bg-stage">
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <article class="reveal-on-scroll card feature-card">
                <span class="material-symbols-outlined text-4xl text-cyan">music_note</span>
                <h2 class="mt-4 font-display font-bold text-2xl text-ink">Beat makers: every session is a mess</h2>
                <ul class="mt-4 space-y-3 text-ink-dim">
                    <li class="flex gap-3"><span class="text-danger">&bull;</span> Downloads folder full of "beat1.wav", "beat1_FINAL.wav", "beat1_FINAL_REAL.wav"</li>
                    <li class="flex gap-3"><span class="text-danger">&bull;</span> Clients demand specific naming formats for every delivery</li>
                    <li class="flex gap-3"><span class="text-danger">&bull;</span> Can't find last month's session when you need it</li>
                </ul>
            </article>
            <article class="reveal-on-scroll card feature-card">
                <span class="material-symbols-outlined text-4xl text-cyan">album</span>
                <h2 class="mt-4 font-display font-bold text-2xl text-ink">Labels: 500 demos a week, zero consistency</h2>
                <ul class="mt-4 space-y-3 text-ink-dim">
                    <li class="flex gap-3"><span class="text-danger">&bull;</span> Artists submit with inconsistent or missing metadata</li>
                    <li class="flex gap-3"><span class="text-danger">&bull;</span> Manual rename takes 2 hours per batch, every batch</li>
                    <li class="flex gap-3"><span class="text-danger">&bull;</span> Lost track of which version of which song from which artist</li>
                </ul>
            </article>
        </div>
    </div>
</section>
```

- [ ] **Step 3: Commit (partial home.html progress is fine)**

```bash
git add frontend/templates/home.html
git commit -m "feat(home): reskin HERO and PROBLEM sections"
```

---

## Task 9: Reskin home.html — HOW IT WORKS + LIVE EXAMPLE

**Files:**
- Modify: `frontend/templates/home.html`

- [ ] **Step 1: Replace the HOW IT WORKS section**

Replace the HOW IT WORKS section (currently at line 77, the `<section id="how-it-works">`) with:

```html
{# ============================ HOW IT WORKS ============================ #}
<section id="how-it-works" class="py-20 bg-stage-raised">
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 text-center">
        <h2 class="font-display font-extrabold text-3xl md:text-4xl text-ink">How it works</h2>
        <p class="mt-3 text-lg text-ink-dim">Three steps. Batch-renamed in seconds.</p>
        <div class="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
            <article class="reveal-on-scroll card card-hover feature-card text-left">
                <div class="font-display font-extrabold text-5xl text-cyan/80">01</div>
                <div class="mt-2 text-cyan h-4">{% include "partials/svg/eq_bars.html" %}</div>
                <span class="mt-6 material-symbols-outlined text-5xl text-cyan">upload_file</span>
                <h3 class="mt-4 font-display font-bold text-xl text-ink">Upload</h3>
                <p class="mt-2 text-ink-dim">Drag &amp; drop your audio files</p>
            </article>
            <article class="reveal-on-scroll card card-hover feature-card text-left">
                <div class="font-display font-extrabold text-5xl text-cyan/80">02</div>
                <div class="mt-2 text-cyan h-4">{% include "partials/svg/eq_bars.html" %}</div>
                <span class="mt-6 material-symbols-outlined text-5xl text-cyan">tune</span>
                <h3 class="mt-4 font-display font-bold text-xl text-ink">Define</h3>
                <p class="mt-2 text-ink-dim">Set your format template</p>
            </article>
            <article class="reveal-on-scroll card card-hover feature-card text-left">
                <div class="font-display font-extrabold text-5xl text-cyan/80">03</div>
                <div class="mt-2 text-cyan h-4">{% include "partials/svg/eq_bars.html" %}</div>
                <span class="mt-6 material-symbols-outlined text-5xl text-cyan">download</span>
                <h3 class="mt-4 font-display font-bold text-xl text-ink">Export</h3>
                <p class="mt-2 text-ink-dim">Download your renamed archive</p>
            </article>
        </div>
    </div>
</section>
```

- [ ] **Step 2: Replace the LIVE EXAMPLE section**

Replace the LIVE EXAMPLE section (currently at line 105, the `<section class="py-20">` preceding `See it in action`) with:

```html
{# ============================ LIVE EXAMPLE ============================ #}
<section class="py-20 bg-stage">
    <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-center font-display font-extrabold text-3xl md:text-4xl text-ink">See it in action</h2>
        <p class="mt-3 text-center text-lg text-ink-dim">Real examples from a real batch</p>
        <div class="relative mt-10 card-inset overflow-hidden p-0">
            <div class="absolute inset-x-0 bottom-0 text-cyan opacity-[0.08] pointer-events-none">
                {% include "partials/svg/waveform_line.html" %}
            </div>
            <div class="relative grid grid-cols-2 divide-x divide-hairline">
                <div class="p-3 text-center text-[11px] font-mono uppercase tracking-widest text-danger">Before</div>
                <div class="p-3 text-center text-[11px] font-mono uppercase tracking-widest text-success">After</div>
            </div>
            <div class="relative divide-y divide-hairline">
                <div class="reveal-on-scroll grid grid-cols-2 divide-x divide-hairline">
                    <div class="p-4 font-mono text-sm text-danger line-through opacity-80">track_final_v2 (1).wav</div>
                    <div class="p-4 font-mono text-sm text-success font-semibold">JuneLake_Nightfall_Cmin_128BPM.wav</div>
                </div>
                <div class="reveal-on-scroll grid grid-cols-2 divide-x divide-hairline">
                    <div class="p-4 font-mono text-sm text-danger line-through opacity-80">beat ideas 03 FULL.wav</div>
                    <div class="p-4 font-mono text-sm text-success font-semibold">JuneLake_Sunset_Amin_90BPM.wav</div>
                </div>
                <div class="reveal-on-scroll grid grid-cols-2 divide-x divide-hairline">
                    <div class="p-4 font-mono text-sm text-danger line-through opacity-80">Untitled Project 14.aif</div>
                    <div class="p-4 font-mono text-sm text-success font-semibold">JuneLake_HorizonLine_Gmaj_120BPM.aif</div>
                </div>
                <div class="reveal-on-scroll grid grid-cols-2 divide-x divide-hairline">
                    <div class="p-4 font-mono text-sm text-danger line-through opacity-80">mix_master_real_final.mp3</div>
                    <div class="p-4 font-mono text-sm text-success font-semibold">JuneLake_MidnightDrive_Dmin_140BPM.mp3</div>
                </div>
                <div class="reveal-on-scroll grid grid-cols-2 divide-x divide-hairline">
                    <div class="p-4 font-mono text-sm text-danger line-through opacity-80">nev song.wav</div>
                    <div class="p-4 font-mono text-sm text-success font-semibold">JuneLake_FirstLight_Emaj_110BPM.wav</div>
                </div>
            </div>
        </div>
    </div>
</section>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/templates/home.html
git commit -m "feat(home): reskin HOW IT WORKS and LIVE EXAMPLE sections"
```

---

## Task 10: Reskin home.html — FEATURES + PRICING

**Files:**
- Modify: `frontend/templates/home.html`

- [ ] **Step 1: Replace the FEATURES section**

Replace the FEATURES section (currently at line 141, the `<section id="features">`) with:

```html
{# ============================ FEATURES ============================ #}
<section id="features" class="py-20 bg-stage-raised">
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-center font-display font-extrabold text-3xl md:text-4xl text-ink">Everything you need</h2>
        <div class="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
            <article class="reveal-on-scroll card card-hover feature-card">
                <div class="inline-flex h-12 w-12 items-center justify-center card-inset p-0">
                    <span class="material-symbols-outlined text-3xl text-cyan">bolt</span>
                </div>
                <h3 class="mt-4 font-display font-bold text-lg text-ink">Lightning fast</h3>
                <p class="mt-2 text-sm text-ink-dim">Rename hundreds of files in seconds, not hours</p>
            </article>
            <article class="reveal-on-scroll card card-hover feature-card">
                <div class="inline-flex h-12 w-12 items-center justify-center card-inset p-0">
                    <span class="material-symbols-outlined text-3xl text-cyan">tune</span>
                </div>
                <h3 class="mt-4 font-display font-bold text-lg text-ink">Flexible templates</h3>
                <p class="mt-2 text-sm text-ink-dim"><code class="font-mono text-xs text-cyan">{ARTIST}_{TITLE}_{KEY}_{BPM}</code> — build any format</p>
            </article>
            <article class="reveal-on-scroll card card-hover feature-card">
                <div class="inline-flex h-12 w-12 items-center justify-center card-inset p-0">
                    <span class="material-symbols-outlined text-3xl text-cyan">auto_fix_high</span>
                </div>
                <h3 class="mt-4 font-display font-bold text-lg text-ink">Precision cleanup</h3>
                <p class="mt-2 text-sm text-ink-dim">Strip version tags, fix casing, normalize spaces automatically</p>
            </article>
            <article class="reveal-on-scroll card card-hover feature-card">
                <div class="inline-flex h-12 w-12 items-center justify-center card-inset p-0">
                    <span class="material-symbols-outlined text-3xl text-cyan">music_note</span>
                </div>
                <h3 class="mt-4 font-display font-bold text-lg text-ink">All major formats</h3>
                <p class="mt-2 text-sm text-ink-dim">WAV, MP3, AIFF, FLAC — every format you actually use</p>
            </article>
            <article class="reveal-on-scroll card card-hover feature-card">
                <div class="inline-flex h-12 w-12 items-center justify-center card-inset p-0">
                    <span class="material-symbols-outlined text-3xl text-cyan">history</span>
                </div>
                <h3 class="mt-4 font-display font-bold text-lg text-ink">Batch history</h3>
                <p class="mt-2 text-sm text-ink-dim">Every rename is logged. Revisit, re-export, never lose work</p>
            </article>
            <article class="reveal-on-scroll card card-hover feature-card">
                <div class="inline-flex h-12 w-12 items-center justify-center card-inset p-0">
                    <span class="material-symbols-outlined text-3xl text-cyan">lock</span>
                </div>
                <h3 class="mt-4 font-display font-bold text-lg text-ink">Private by default</h3>
                <p class="mt-2 text-sm text-ink-dim">Your files are processed and deleted. Nothing is stored</p>
            </article>
        </div>
    </div>
</section>
```

- [ ] **Step 2: Replace the PRICING section**

Replace the PRICING section (currently at line 180, the `<section id="pricing">`) with:

```html
{# ============================ PRICING ============================ #}
<section id="pricing" class="py-20 bg-stage">
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-center font-display font-extrabold text-3xl md:text-4xl text-ink">Simple pricing</h2>
        <p class="mt-3 text-center text-lg text-ink-dim">Pay as you go, or subscribe for monthly credits</p>

        <div class="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {% for option in payment_options %}
            <article class="reveal-on-scroll card card-hover feature-card {% if option.plan_type == 'subscription' and option.recommended %}card-active{% endif %}">
                <p class="text-[11px] font-mono font-medium uppercase tracking-widest text-cyan">{{ option.accent }}</p>
                <h3 class="mt-2 font-display font-bold text-2xl text-ink">{{ option.label }}</h3>
                <p class="mt-2 text-sm text-ink-dim">{{ option.description }}</p>
                <div class="mt-4 text-4xl font-display font-extrabold text-ink">
                    {{ option.amount_label }}{% if option.plan_type == 'subscription' %}<span class="text-sm font-mono font-normal text-ink-dim">/mo</span>{% endif %}
                </div>
                <p class="mt-1 text-[11px] font-mono uppercase tracking-widest text-cyan">
                    {% if option.plan_type == 'subscription' %}{{ option.credits }} credits/month{% else %}{{ option.credits }} credit{{ 's' if option.credits != 1 else '' }}{% endif %}
                </p>
                <a href="/register?plan={{ option.key }}" class="mt-6 btn btn-primary w-full">
                    Get {{ option.label }}
                </a>
            </article>
            {% endfor %}
        </div>
    </div>
</section>
```

Note: the `option.recommended` Jinja attribute may not exist on the current payment option objects — that's okay, the conditional is a no-op when the attribute is absent. Jinja does not throw on missing attributes in a boolean context when using `.` access on a template variable — but to be safe, the template reads `option.recommended` via the attribute access which will evaluate to `Undefined` and then to `False` in a boolean expression under the default Jinja environment. This is the standard Jinja behavior used elsewhere in this codebase.

- [ ] **Step 3: Commit**

```bash
git add frontend/templates/home.html
git commit -m "feat(home): reskin FEATURES and PRICING sections"
```

---

## Task 11: Reskin home.html — STATS + FINAL CTA + footer inclusion

**Files:**
- Modify: `frontend/templates/home.html`

- [ ] **Step 1: Replace the STATS section**

Replace the STATS section (currently at line 208, starts with `{# Note: These are hardcoded marketing placeholder numbers`):

```html
{# ============================ STATS ============================ #}
{# Note: These are hardcoded marketing placeholder numbers, not real data. #}
<section class="relative py-16 bg-stage-sunken overflow-hidden">
    <div class="absolute inset-x-0 bottom-0 text-cyan opacity-[0.08] pointer-events-none">
        {% include "partials/svg/waveform_line.html" %}
    </div>
    <div class="relative mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
        <div>
            <div class="font-display font-extrabold text-5xl text-cyan" data-count-to="50000" data-count-suffix="+">0</div>
            <p class="mt-2 text-[11px] font-mono uppercase tracking-widest text-ink-dim">Files renamed</p>
        </div>
        <div>
            <div class="font-display font-extrabold text-5xl text-ink">2.3s</div>
            <p class="mt-2 text-[11px] font-mono uppercase tracking-widest text-ink-dim">Average per file</p>
        </div>
        <div>
            <div class="font-display font-extrabold text-5xl text-cyan" data-count-to="99" data-count-suffix=".7%">0</div>
            <p class="mt-2 text-[11px] font-mono uppercase tracking-widest text-ink-dim">Customer satisfaction</p>
        </div>
    </div>
</section>
```

- [ ] **Step 2: Replace the FINAL CTA section**

Replace the FINAL CTA section (currently at line 227):

```html
{# ============================ FINAL CTA ============================ #}
<section class="relative py-24 bg-stage overflow-hidden">
    <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 text-cyan opacity-15 pointer-events-none">
        {% include "partials/svg/waveform_line.html" %}
    </div>
    <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 text-magenta opacity-10 pointer-events-none translate-y-1">
        {% include "partials/svg/waveform_line.html" %}
    </div>
    <div class="relative mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center">
        <h2 class="font-display font-extrabold text-3xl md:text-5xl text-ink">Ready to stop fighting your filenames?</h2>
        <a href="/register" class="mt-10 btn btn-primary inline-flex text-base px-8 py-4">
            Get Started Free — No card required
        </a>
    </div>
</section>
```

- [ ] **Step 3: Verify no legacy tokens remain in home.html**

Use `Grep` on `frontend/templates/home.html` — each of these must return zero matches:

```
primary-container
primary-fixed
surface-bright
deep-slate
inverse-surface
inverse-on-surface
bg-red-50
bg-emerald-50
text-red-500
text-red-600
text-red-700
text-emerald-700
rounded-3xl
rounded-4xl
```

Also use `Grep` to search for `bg-white` in `frontend/templates/home.html` — must return zero matches (we don't want any white cards leaking through).

- [ ] **Step 4: Commit**

```bash
git add frontend/templates/home.html
git commit -m "feat(home): reskin STATS and FINAL CTA sections; remove all legacy tokens"
```

---

## Task 12: Reskin auth/login.html

**Files:**
- Modify: `frontend/templates/auth/login.html`

- [ ] **Step 1: Replace the full file contents**

Replace the entire contents of `frontend/templates/auth/login.html` with:

```html
{% extends "base.html" %}

{% block title %}Sign in — PxNN{% endblock %}

{% block body %}
{% include "partials/nav.html" %}

<section class="min-h-[calc(100vh-4rem)] grid grid-cols-1 lg:grid-cols-2 bg-stage">
    {# Left: hero photo panel (desktop only, becomes top strip on mobile) #}
    <div class="relative hidden lg:block hero-photo rounded-none">
        <img src="/static/img/hero/console-panel.jpg" alt="" class="hero-photo__img" loading="eager">
        <div class="absolute inset-0 flex flex-col justify-end p-10">
            <div class="text-cyan h-8">{% include "partials/svg/eq_bars.html" %}</div>
            <p class="mt-4 font-display font-extrabold text-3xl text-ink">Back to the session.</p>
            <p class="mt-2 text-sm font-mono uppercase tracking-widest text-ink-dim">&gt; sign in to continue</p>
        </div>
    </div>

    {# Mobile hero strip #}
    <div class="relative lg:hidden hero-photo rounded-none h-40">
        <img src="/static/img/hero/console-panel.jpg" alt="" class="hero-photo__img" loading="eager">
    </div>

    {# Right: form #}
    <div class="flex items-center justify-center px-4 py-12">
        <div class="w-full max-w-md">
            <div class="card p-8">
                <p class="text-[11px] font-mono font-medium uppercase tracking-widest text-cyan">&gt; SIGN IN</p>
                <h1 class="mt-2 font-display font-extrabold text-3xl text-ink">Sign in to PxNN</h1>
                <p class="mt-2 text-sm text-ink-dim">Welcome back.</p>

                <div id="login-error" class="hidden mt-4 rounded-xl bg-danger/10 border border-danger/30 p-3 text-sm text-danger"></div>

                <form id="login-form" class="mt-6 space-y-4">
                    <label class="block">
                        <span class="field-label">Username</span>
                        <input type="text" name="username" required autocomplete="username" class="input">
                    </label>
                    <label class="block">
                        <span class="field-label">Password</span>
                        <input type="password" name="password" required autocomplete="current-password" class="input">
                    </label>
                    <button type="submit" class="btn btn-primary w-full py-3">
                        Sign in
                    </button>
                </form>

                {% if google_oauth_enabled %}
                <div class="mt-6 flex items-center gap-3">
                    <div class="h-px flex-1 bg-hairline"></div>
                    <span class="text-[11px] font-mono uppercase tracking-widest text-ink-dim">or</span>
                    <div class="h-px flex-1 bg-hairline"></div>
                </div>
                <a href="/auth/google/login" class="mt-4 btn btn-ghost w-full py-3">
                    <svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                    </svg>
                    Continue with Google
                </a>
                {% endif %}

                <p class="mt-6 text-center text-sm text-ink-dim">
                    Don't have an account?
                    <a href="/register" class="font-semibold text-cyan hover:text-white transition">Sign up →</a>
                </p>
            </div>
        </div>
    </div>
</section>

<script>
(function() {
    const form = document.getElementById('login-form');
    const errorEl = document.getElementById('login-error');
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        errorEl.classList.add('hidden');
        const formData = new FormData(form);
        const response = await fetch('/api/auth/login', { method: 'POST', body: formData });
        if (response.ok) {
            window.location.href = '/app';
        } else {
            const data = await response.json().catch(() => ({ detail: 'Sign in failed.' }));
            errorEl.textContent = data.detail || 'Sign in failed.';
            errorEl.classList.remove('hidden');
        }
    });
})();
</script>
{% endblock %}
```

- [ ] **Step 2: Verify**

Use `Grep` on `frontend/templates/auth/login.html` — each must return zero matches:

```
primary-container
primary-fixed
surface-bright
deep-slate
outline/
bg-white
rounded-3xl
rounded-4xl
```

- [ ] **Step 3: Commit**

```bash
git add frontend/templates/auth/login.html
git commit -m "feat(auth): reskin login with split-panel layout and Studio Dark theme"
```

---

## Task 13: Reskin auth/register.html

**Files:**
- Modify: `frontend/templates/auth/register.html`

- [ ] **Step 1: Replace the full file contents**

Replace the entire contents of `frontend/templates/auth/register.html` with:

```html
{% extends "base.html" %}

{% block title %}Create account — PxNN{% endblock %}

{% block body %}
{% include "partials/nav.html" %}

<section class="min-h-[calc(100vh-4rem)] grid grid-cols-1 lg:grid-cols-2 bg-stage">
    {# Left: form (mirrored from login) #}
    <div class="flex items-center justify-center px-4 py-12 order-2 lg:order-1">
        <div class="w-full max-w-md">
            <div class="card p-8">
                <p class="text-[11px] font-mono font-medium uppercase tracking-widest text-cyan">&gt; NEW ACCOUNT</p>
                <h1 class="mt-2 font-display font-extrabold text-3xl text-ink">Create your PxNN account</h1>
                <p class="mt-2 text-sm text-ink-dim">Rename files in seconds.</p>

                <div id="register-error" class="hidden mt-4 rounded-xl bg-danger/10 border border-danger/30 p-3 text-sm text-danger"></div>

                <form id="register-form" class="mt-6 space-y-4">
                    <label class="block">
                        <span class="field-label">Username</span>
                        <input type="text" name="username" required autocomplete="username" minlength="3" class="input">
                    </label>
                    <label class="block">
                        <span class="field-label">Password</span>
                        <input type="password" name="password" required autocomplete="new-password" minlength="8" class="input">
                        <span class="mt-1 block text-[11px] font-mono text-ink-dim">At least 8 characters</span>
                    </label>
                    <button type="submit" class="btn btn-primary w-full py-3">
                        Create account
                    </button>
                </form>

                {% if google_oauth_enabled %}
                <div class="mt-6 flex items-center gap-3">
                    <div class="h-px flex-1 bg-hairline"></div>
                    <span class="text-[11px] font-mono uppercase tracking-widest text-ink-dim">or</span>
                    <div class="h-px flex-1 bg-hairline"></div>
                </div>
                <a href="/auth/google/login" class="mt-4 btn btn-ghost w-full py-3">
                    <svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                    </svg>
                    Continue with Google
                </a>
                {% endif %}

                <p class="mt-6 text-center text-sm text-ink-dim">
                    Already have an account?
                    <a href="/login" class="font-semibold text-cyan hover:text-white transition">Sign in →</a>
                </p>
            </div>
        </div>
    </div>

    {# Right: hero photo (mirrored from login) #}
    <div class="relative hidden lg:block hero-photo rounded-none order-1 lg:order-2">
        <img src="/static/img/hero/console-panel.jpg" alt="" class="hero-photo__img" loading="eager">
        <div class="absolute inset-0 flex flex-col justify-end p-10">
            <div class="text-magenta h-8">{% include "partials/svg/eq_bars.html" %}</div>
            <p class="mt-4 font-display font-extrabold text-3xl text-ink">Start clean.</p>
            <p class="mt-2 text-sm font-mono uppercase tracking-widest text-ink-dim">&gt; 01. name files like a label</p>
        </div>
    </div>

    {# Mobile hero strip #}
    <div class="relative lg:hidden hero-photo rounded-none h-40 order-1">
        <img src="/static/img/hero/console-panel.jpg" alt="" class="hero-photo__img" loading="eager">
    </div>
</section>

<script>
(function() {
    const form = document.getElementById('register-form');
    const errorEl = document.getElementById('register-error');
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        errorEl.classList.add('hidden');
        const formData = new FormData(form);
        const response = await fetch('/api/auth/register', { method: 'POST', body: formData });
        if (response.ok) {
            window.location.href = '/app';
        } else {
            const data = await response.json().catch(() => ({ detail: 'Registration failed.' }));
            errorEl.textContent = data.detail || 'Registration failed.';
            errorEl.classList.remove('hidden');
        }
    });
})();
</script>
{% endblock %}
```

- [ ] **Step 2: Verify**

Use `Grep` on `frontend/templates/auth/register.html` — each must return zero matches:

```
primary-container
primary-fixed
surface-bright
deep-slate
outline/
bg-white
rounded-3xl
rounded-4xl
```

- [ ] **Step 3: Commit**

```bash
git add frontend/templates/auth/register.html
git commit -m "feat(auth): reskin register with mirrored split-panel layout"
```

---

## Task 14: Reskin profile.html

**Files:**
- Modify: `frontend/templates/profile.html`

- [ ] **Step 1: Replace the full file contents**

Replace the entire contents of `frontend/templates/profile.html` with:

```html
{% extends "base.html" %}

{% block title %}Profile — PxNN{% endblock %}

{% block body %}
{% include "partials/nav.html" %}

<section class="min-h-[calc(100vh-4rem)] bg-stage py-12 px-4">
    <div class="mx-auto max-w-2xl space-y-6">
        <div>
            <p class="text-[11px] font-mono uppercase tracking-widest text-cyan">&gt; ACCOUNT</p>
            <h1 class="mt-1 font-display font-extrabold text-3xl text-ink">Profile</h1>
        </div>

        {# Card 1: Account identity #}
        <article class="card">
            <p class="text-[11px] font-mono uppercase tracking-widest text-ink-dim">Identity</p>
            <dl class="mt-4 space-y-3 text-sm">
                <div class="flex justify-between">
                    <dt class="text-ink-dim">Username</dt>
                    <dd class="font-mono text-ink">{{ current_user.username }}</dd>
                </div>
                <div class="flex justify-between">
                    <dt class="text-ink-dim">Email</dt>
                    <dd class="font-mono text-ink">{{ current_user.email or 'Not set' }}</dd>
                </div>
                <div class="flex justify-between">
                    <dt class="text-ink-dim">Account created</dt>
                    <dd class="font-mono text-ink">{{ current_user.created_at.strftime('%Y-%m-%d') if current_user.created_at else '—' }}</dd>
                </div>
                <div class="flex justify-between items-center">
                    <dt class="text-ink-dim">Subscription</dt>
                    <dd>
                        {% if current_user.subscription_status == 'active' %}
                            <span class="pill pill-match">Active</span>
                        {% elif current_user.subscription_status == 'canceled' %}
                            <span class="pill pill-conflict">Canceled</span>
                        {% else %}
                            <span class="pill pill-queued">None</span>
                        {% endif %}
                    </dd>
                </div>
            </dl>
        </article>

        {# Card 2: Connected accounts #}
        <article class="card">
            <p class="text-[11px] font-mono uppercase tracking-widest text-ink-dim">Connected accounts</p>
            <div class="mt-4 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                    </svg>
                    <span class="font-semibold text-ink">Google</span>
                </div>
                {% if current_user.google_sub %}
                    <span class="pill pill-match">Connected{% if current_user.email %} as {{ current_user.email }}{% endif %}</span>
                {% else %}
                    {% if google_oauth_enabled %}
                        <a href="/auth/google/login" class="btn btn-ghost">Connect</a>
                    {% else %}
                        <span class="text-[11px] font-mono uppercase tracking-widest text-ink-dim">Not available</span>
                    {% endif %}
                {% endif %}
            </div>
        </article>

        {# Card 3: Change password #}
        <article class="card">
            <p class="text-[11px] font-mono uppercase tracking-widest text-ink-dim">Change password</p>
            {% if current_user.password_hash %}
            <div id="pwd-error" class="hidden mt-4 rounded-xl bg-danger/10 border border-danger/30 p-3 text-sm text-danger"></div>
            <div id="pwd-success" class="hidden mt-4 rounded-xl bg-success/10 border border-success/30 p-3 text-sm text-success">Password updated.</div>
            <form id="pwd-form" class="mt-4 space-y-4">
                <label class="block">
                    <span class="field-label">Current password</span>
                    <input type="password" name="current_password" required class="input">
                </label>
                <label class="block">
                    <span class="field-label">New password</span>
                    <input type="password" name="new_password" required minlength="8" class="input">
                </label>
                <label class="block">
                    <span class="field-label">Confirm new password</span>
                    <input type="password" name="confirm_password" required minlength="8" class="input">
                </label>
                <button type="submit" class="btn btn-primary w-full py-3">Update password</button>
            </form>
            {% else %}
            <p class="mt-4 text-sm text-ink-dim">This is a Google-only account. Sign in with Google to authenticate.</p>
            {% endif %}
        </article>

        {# Card 4: Credits & subscription #}
        <article class="card">
            <p class="text-[11px] font-mono uppercase tracking-widest text-ink-dim">Credits &amp; subscription</p>
            <dl class="mt-4 space-y-3 text-sm">
                <div class="flex justify-between">
                    <dt class="text-ink-dim">Credit balance</dt>
                    <dd class="font-mono font-bold text-cyan text-lg">{{ current_user.credit_balance }}</dd>
                </div>
                <div class="flex justify-between">
                    <dt class="text-ink-dim">Active plan</dt>
                    <dd class="font-mono text-ink">{{ current_user.subscription_plan or 'None' }}</dd>
                </div>
            </dl>
            <a href="/app?billing=options" class="mt-4 inline-block text-sm font-semibold text-cyan hover:text-white transition">Manage billing →</a>
        </article>

        {# Card 5: Danger zone #}
        <article class="card" style="border-color: rgba(255,78,91,0.40);">
            <p class="text-[11px] font-mono uppercase tracking-widest text-danger">Danger zone</p>
            <p class="mt-2 text-sm text-ink-dim">Permanently delete your account and all associated data. This cannot be undone.</p>
            <button type="button" onclick="document.getElementById('delete-dialog').showModal()" class="mt-4 btn btn-danger">
                Delete account
            </button>

            <dialog id="delete-dialog" class="rounded-xl border border-hairline bg-stage-raised p-0 text-ink backdrop:bg-black/70">
                <div class="w-[min(90vw,420px)] p-6">
                    <p class="text-[11px] font-mono uppercase tracking-widest text-danger">Confirm deletion</p>
                    <h3 class="mt-1 font-display font-extrabold text-xl text-ink">Delete account?</h3>
                    <p class="mt-2 text-sm text-ink-dim">Type your username <strong class="font-mono text-ink">{{ current_user.username }}</strong> to confirm.</p>
                    <div id="del-error" class="hidden mt-3 rounded-xl bg-danger/10 border border-danger/30 p-3 text-sm text-danger"></div>
                    <form id="delete-form" class="mt-4 space-y-3">
                        <input type="text" name="username_confirmation" required class="input input--error" placeholder="Type your username">
                        <div class="flex gap-3">
                            <button type="button" onclick="document.getElementById('delete-dialog').close()" class="btn btn-ghost flex-1">
                                Cancel
                            </button>
                            <button type="submit" class="btn btn-danger flex-1" style="background-color: #ff4e5b; color: #0a0b0f; border-color: #ff4e5b;">
                                Permanently delete
                            </button>
                        </div>
                    </form>
                </div>
            </dialog>
        </article>
    </div>
</section>

<script>
(function() {
    const pwdForm = document.getElementById('pwd-form');
    const pwdError = document.getElementById('pwd-error');
    const pwdSuccess = document.getElementById('pwd-success');
    if (pwdForm) {
        pwdForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            pwdError.classList.add('hidden');
            pwdSuccess.classList.add('hidden');
            const formData = new FormData(pwdForm);
            const response = await fetch('/api/profile/password', { method: 'POST', body: formData });
            if (response.ok) {
                pwdSuccess.classList.remove('hidden');
                pwdForm.reset();
            } else {
                const data = await response.json().catch(() => ({ detail: 'Password update failed.' }));
                pwdError.textContent = data.detail || 'Password update failed.';
                pwdError.classList.remove('hidden');
            }
        });
    }

    const deleteForm = document.getElementById('delete-form');
    const deleteError = document.getElementById('del-error');
    if (deleteForm) {
        deleteForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            deleteError.classList.add('hidden');
            const formData = new FormData(deleteForm);
            const response = await fetch('/api/profile/delete', { method: 'POST', body: formData });
            if (response.ok) {
                window.location.href = '/';
            } else {
                const data = await response.json().catch(() => ({ detail: 'Delete failed.' }));
                deleteError.textContent = data.detail || 'Delete failed.';
                deleteError.classList.remove('hidden');
            }
        });
    }
})();
</script>
{% endblock %}
```

- [ ] **Step 2: Verify**

Use `Grep` on `frontend/templates/profile.html` — each must return zero matches:

```
primary-container
surface-bright
deep-slate
outline/
bg-white
bg-red-50
bg-emerald-50
text-red-500
text-red-600
text-red-700
text-emerald-700
rounded-3xl
rounded-4xl
```

- [ ] **Step 3: Commit**

```bash
git add frontend/templates/profile.html
git commit -m "feat(profile): reskin profile page with cards, pills, danger zone"
```

---

## Task 15: app.html — global token sweep

**Files:**
- Modify: `frontend/templates/app.html`

This task is a find/replace pass across the entire 1456-line file. It doesn't restructure anything — it just retokenizes.

- [ ] **Step 1: Apply the exact token replacements**

Open `frontend/templates/app.html` and perform these replacements, in order. Use `Edit` with `replace_all: true` for each pair. Do them one at a time so failed matches are obvious.

| # | old | new |
|---|---|---|
| 1 | `bg-surface-bright` | `bg-stage` |
| 2 | `from-surface-bright` | `from-stage` |
| 3 | `to-surface-bright` | `to-stage` |
| 4 | `bg-primary-container` | `bg-cyan` |
| 5 | `bg-primary-container/90` | `bg-cyan/90` |
| 6 | `bg-primary-container/10` | `bg-cyan/10` |
| 7 | `bg-primary-fixed/20` | `bg-stage-raised` |
| 8 | `bg-primary-fixed/30` | `bg-stage-raised` |
| 9 | `bg-primary-fixed` | `bg-stage-raised` |
| 10 | `text-primary-container` | `text-cyan` |
| 11 | `border-primary-container` | `border-cyan` |
| 12 | `hover:bg-primary-container` | `hover:bg-white` |
| 13 | `hover:border-primary-container` | `hover:border-cyan` |
| 14 | `hover:text-primary-container` | `hover:text-cyan` |
| 15 | `focus:border-primary-container` | `focus:border-cyan` |
| 16 | `focus:ring-primary-container/20` | `focus:ring-cyan/30` |
| 17 | `ring-primary-container/20` | `ring-cyan/30` |
| 18 | `text-deep-slate` | `text-ink` |
| 19 | `text-secondary` | `text-ink-dim` |
| 20 | `hover:text-secondary` | `hover:text-ink-dim` |
| 21 | `border-outline/10` | `border-hairline` |
| 22 | `border-outline/20` | `border-hairline` |
| 23 | `bg-outline/10` | `bg-rail` |
| 24 | `bg-outline/20` | `bg-rail` |
| 25 | `divide-outline/10` | `divide-hairline` |
| 26 | `bg-inverse-surface` | `bg-stage-sunken` |
| 27 | `text-inverse-on-surface` | `text-ink` |
| 28 | `bg-white/90` | `bg-stage-raised/90` |
| 29 | `bg-white` | `bg-stage-raised` |
| 30 | `rounded-4xl` | `rounded-xl` |
| 31 | `rounded-3xl` | `rounded-xl` |
| 32 | `shadow-xl` | `shadow-glow-cyan` |
| 33 | `shadow-lg` | `` (empty string — remove, elevation is via bg contrast) |
| 34 | `bg-red-50` | `bg-danger/10` |
| 35 | `bg-red-100` | `bg-danger/15` |
| 36 | `border-red-200` | `border-danger/30` |
| 37 | `border-red-500` | `border-danger` |
| 38 | `text-red-500` | `text-danger` |
| 39 | `text-red-600` | `text-danger` |
| 40 | `text-red-700` | `text-danger` |
| 41 | `text-red-700/80` | `text-danger/80` |
| 42 | `bg-red-600` | `bg-danger` |
| 43 | `hover:bg-red-700` | `hover:bg-danger/90` |
| 44 | `bg-red-500` | `bg-danger` |
| 45 | `hover:bg-red-500` | `hover:bg-danger` |
| 46 | `bg-emerald-50` | `bg-success/10` |
| 47 | `bg-emerald-100` | `bg-success/15` |
| 48 | `border-emerald-200` | `border-success/30` |
| 49 | `text-emerald-700` | `text-success` |

- [ ] **Step 2: Verify the sweep is clean**

Use `Grep` on `frontend/templates/app.html` — each of these must return zero matches:

```
primary-container
primary-fixed
surface-bright
deep-slate
inverse-surface
inverse-on-surface
border-outline/
bg-outline/
bg-white
bg-red-
bg-emerald-
text-red-
text-emerald-
border-red-
border-emerald-
rounded-3xl
rounded-4xl
shadow-xl
shadow-lg
```

If any return a match, add the missing pair to the replacement list above and re-run.

Also use `Grep` for `text-secondary` (bare): must return zero matches.

- [ ] **Step 3: Boot and smoke test**

```bash
docker-compose up --build -d
```

Then load the wizard:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8000/app
```

Expected: `200` (or `307` redirect to `/login` if not signed in — either is fine).

- [ ] **Step 4: Commit**

```bash
git add frontend/templates/app.html
git commit -m "feat(app): global token sweep to Studio Dark palette (no structural changes)"
```

---

## Task 16: app.html — step indicator, drop zone, header polish

**Files:**
- Modify: `frontend/templates/app.html`

After the token sweep in Task 15, three specific sections in `app.html` need targeted polish to actually *look* DAW-native (not just retokenized). Everything else can ride on the generic swap.

- [ ] **Step 1: Add mono small-caps kicker to section headers inside app.html**

Use `Grep` on `frontend/templates/app.html` to find every `<h1>` and `<h2>` with `font-display font-extrabold`. For each one, add a small mono kicker line immediately before the heading. The kicker follows this pattern:

```html
<p class="text-[11px] font-mono uppercase tracking-widest text-cyan">&gt; <KICKER_TEXT></p>
```

Choose kicker text based on context — common ones:
- Above "Your Batches" / "Dashboard" heading → `&gt; WORKSPACE`
- Above "New Batch" / "Upload" heading → `&gt; STEP 01 · STAGE FILES`
- Above "Rules" / "Define" heading → `&gt; STEP 02 · RULE BUILDER`
- Above "Review" / "Apply" heading → `&gt; STEP 03 · COMMIT BATCH`
- Above "Billing" → `&gt; BILLING`
- Above "History" → `&gt; HISTORY`

Only add the kicker where a heading clearly introduces a new section. Do not add a kicker to purely decorative subheadings or repeated item titles. If you're unsure, skip it.

- [ ] **Step 2: Upgrade the drop zone label**

Use `Grep` on `frontend/templates/app.html` for `dropzone` to find the file-drop element(s). For each drop zone, the inner label copy (typically something like "Drop files here" or "Drag and drop audio files") must be wrapped so that:
1. The primary label uses `font-display font-extrabold text-xl text-ink`.
2. The helper line below uses `text-[11px] font-mono uppercase tracking-widest text-ink-dim` and reads: `&gt; MP3 · WAV · AIFF · FLAC`.
3. An `eq_bars` SVG appears above the label with `h-4 text-cyan mx-auto mb-4`:

```html
<div class="text-cyan h-4 mx-auto mb-4 flex justify-center">{% include "partials/svg/eq_bars.html" %}</div>
```

Leave any existing `<input type="file">`, HTMX `hx-post`, `hx-target`, or JS behavior on the drop zone untouched. Only change the inner text and add the SVG above it.

- [ ] **Step 3: Add status pills to any visible file preview rows**

Use `Grep` on `frontend/templates/app.html` for words that indicate a preview status (`Match`, `Conflict`, `Queued`, `Processing`) being rendered as a badge or pill. For each one found:

- Replace the existing pill/badge wrapper with `<span class="pill pill-match">MATCH</span>` (or `pill-conflict`, `pill-queued`, `pill-processing` as appropriate).
- Do not change any surrounding table row structure.

If no such status rendering exists in `app.html`, skip this step — the wizard may compute status differently and the new pills will apply when Task 15's token sweep handles future additions.

- [ ] **Step 4: Smoke test the wizard renders**

```bash
docker-compose up --build -d
```

Then manually load `http://localhost:8000/app` in a real browser (or Playwright MCP). Verify:
1. The page renders without layout collapse.
2. Any drop zone is visible and reads the new copy.
3. Any heading has its mono kicker above it.
4. No console errors in the browser dev tools.

If the layout has visibly collapsed (content overflowing, cards invisible, etc.), the most likely cause is a missing class in the Task 15 replacement list — `Grep` for the specific offending legacy token and add the pair to Task 15's list.

- [ ] **Step 5: Commit**

```bash
git add frontend/templates/app.html
git commit -m "feat(app): add mono kickers, upgraded drop zone, status pills"
```

---

## Task 17: Remove the stats-section inverse-surface fallback

**Files:**
- Modify: `frontend/templates/home.html` (verification only — the replacement already ran in Task 11)
- Modify: `frontend/templates/base.html` (verification only)

- [ ] **Step 1: Global grep sweep — legacy tokens in `frontend/`**

Use `Grep` on the entire `frontend/` directory (recursive, all files) for each of these terms. Each must return zero matches:

```
primary-container
primary-fixed
primary-fixed-dim
surface-bright
surface-container-high
deep-slate
inverse-surface
inverse-on-surface
on-secondary
```

And these prefixed variants (the ambiguous word-only tokens that false-positive against Tailwind utilities):

```
bg-secondary
text-secondary
border-secondary
ring-secondary
bg-outline
text-outline
border-outline
ring-outline
```

And the radius tokens:

```
rounded-3xl
rounded-4xl
```

- [ ] **Step 2: Fix anything that slipped through**

For every match found in Step 1, open the file and replace the legacy token with its new equivalent per Task 15's replacement table. Then re-run Step 1 until zero matches across every term.

- [ ] **Step 3: Commit (only if fixes were needed)**

```bash
git add frontend/
git commit -m "chore(cleanup): purge final legacy Precision Slate tokens"
```

If there was nothing to commit, skip the commit — print a message confirming the sweep was clean and move on.

---

## Task 18: Capture "after" screenshots and run smoke tests

**Files:**
- Create: `docs/superpowers/evidence/2026-04-11-studio-dark-neon-reskin/after/` (Playwright screenshots)

- [ ] **Step 1: Rebuild and run the app**

```bash
docker-compose down
docker-compose up --build -d
sleep 8
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8000/
```

Expected: `200`.

- [ ] **Step 2: Capture after screenshots with Playwright MCP**

Using `mcp__playwright__browser_navigate`, `mcp__playwright__browser_resize`, and `mcp__playwright__browser_take_screenshot` (full page), capture the same set as Task 1:

At `1280 x 900`:
- `after/home-1280.png`
- `after/login-1280.png`
- `after/register-1280.png`
- `after/app-1280.png` (accept redirect to login if not authed)
- `after/profile-1280.png` (accept redirect to login if not authed)

At `375 x 812`:
- `after/home-375.png`
- `after/app-375.png`

- [ ] **Step 3: Manual smoke click-through**

Using Playwright MCP (not the terminal), visit each of these URLs and verify the listed behavior. Do NOT mark a check unless you visually confirmed it via a Playwright screenshot or snapshot:

- [ ] `http://localhost:8000/` — home loads, hero photo is visible (dimmed), CTAs are cyan, filename stack animates, footer is at the bottom with no layout breakage.
- [ ] `http://localhost:8000/#features` — anchor scrolls, feature cards have dark background, cyan icons.
- [ ] `http://localhost:8000/#pricing` — pricing cards render, at least one card shows a `/mo` suffix.
- [ ] `http://localhost:8000/login` — split layout on desktop, photo panel visible, form in a dark card, Google button present if enabled.
- [ ] `http://localhost:8000/register` — mirrored split layout, form on the left.
- [ ] Register a new test user (username: `reskin-smoke`, password: `testtest1234`) via the form — should succeed and redirect to `/app`.
- [ ] `http://localhost:8000/app` — wizard renders without layout collapse, drop zone is visible, at least one `> STEP 0X` kicker is visible.
- [ ] `http://localhost:8000/profile` — 5 cards stacked, danger zone card has red-tinted border, pills render correctly.
- [ ] Change password via the profile form — should show the success banner.
- [ ] Click the user avatar in the nav — dropdown opens, "Profile" and "Logout" are visible.
- [ ] Click "Logout" — redirects to `/`.

- [ ] **Step 4: Commit the evidence**

```bash
git add docs/superpowers/evidence/2026-04-11-studio-dark-neon-reskin/after/
git commit -m "chore(evidence): capture after screenshots; smoke tests passing"
```

---

## Task 19: Final verification and PR

**Files:** none (meta task)

- [ ] **Step 1: Verify commit count and branch state**

```bash
git log --oneline main..HEAD
```

Expected: around 16–19 commits on `feat/studio-dark-neon-reskin` that are not on `main`.

- [ ] **Step 2: Verify file sizes**

```bash
ls -lh frontend/static/img/hero/
```

Expected: `studio-hero.jpg` and `console-panel.jpg` each ≤ 400KB; `CREDITS.md` exists.

```bash
wc -c frontend/static/css/style.css
```

Record the byte count. The file grew from the original (~245 lines, ~5KB) — expect somewhere in the 12–20KB range raw. No hard gate on raw size, but if it's >40KB, investigate for duplication.

- [ ] **Step 3: Final grep gate**

Use `Grep` on `frontend/` (recursive) for each of the terms in Task 17 Step 1 — each must still return zero matches. Also run:

```
#0052cc
#dae2ff
#b2c5ff
```

These bare hex colors from the old palette must return zero matches anywhere in `frontend/`.

- [ ] **Step 4: Push the branch**

```bash
git push -u origin feat/studio-dark-neon-reskin
```

- [ ] **Step 5: Open the pull request**

```bash
gh pr create --title "feat(ui): Studio Dark / Neon DAW reskin" --body "$(cat <<'EOF'
## Summary
- Reskins all existing pages (home, app, auth, profile) to a dark DAW aesthetic per the spec.
- Swaps Tailwind tokens (`stage`, `cyan`, `magenta`, `amber`, `ink`, `hairline` etc.), adds a component layer in `style.css`, and introduces 4 inline SVG partials (waveform, EQ bars, spectrogram grid, wordmark glyph).
- Adds 2 hero photos (Unsplash License) for the home hero and auth split panel.

## Spec
`docs/superpowers/specs/2026-04-11-studio-dark-neon-reskin-design.md`

## Evidence
Before / after screenshots: `docs/superpowers/evidence/2026-04-11-studio-dark-neon-reskin/`

## Test plan
- [ ] Home loads with dimmed hero photo and cyan CTAs
- [ ] Login + register succeed against existing backend
- [ ] Google OAuth login still redirects to /app
- [ ] Wizard completes a rename end-to-end without console errors
- [ ] Profile page edits identity, changes password, deletes account
- [ ] Mobile (375px) home + app render without layout collapse

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Return the PR URL for the user.

---

## Self-review

### Spec coverage
- Section 2 (Visual theme): Tasks 2–4 establish the tokens and SVG chrome that create the theme.
- Section 3 (Design tokens): Task 2 (Tailwind config) + Task 3 (component CSS layer).
- Section 4 (Component primitives): Task 3 covers buttons, cards, inputs, tables, pills, hero photo, EQ animation. Task 5 uses them in nav; Task 6 in footer.
- Section 5 (Page-by-page plan):
  - 5.1 `base.html` → Task 2
  - 5.2 `partials/nav.html` → Task 5
  - 5.3 `partials/footer.html` → Task 6
  - 5.4 `home.html` → Tasks 8, 9, 10, 11 (all 8 sections)
  - 5.5 `app.html` → Tasks 15, 16
  - 5.6 `auth/login.html` → Task 12
  - 5.7 `auth/register.html` → Task 13
  - 5.8 `profile.html` → Task 14
- Section 6 (Imagery plan): Task 4 (SVG) + Task 7 (hero photos).
- Section 7 (Verification): Task 1 (before shots), Task 17 (grep gate), Task 18 (after shots + click-through), Task 19 (final gate + PR).
- Section 8 (Rollout): Task 1 (branch), Task 19 (PR).

Everything in the spec maps to at least one task.

### Placeholder scan
No "TODO", "TBD", "fill in", or "similar to" references. Every code block contains actual code. Every grep gate lists the exact terms to search for.

### Type consistency
- `.btn`, `.btn-primary`, `.btn-ghost`, `.btn-danger` — same names across Tasks 3, 5, 6, 8–14.
- `.card`, `.card-inset`, `.card-hover`, `.card-active` — consistent.
- `.input`, `.field-label` — consistent across all form tasks.
- `.pill`, `.pill-match`, `.pill-conflict`, `.pill-processing`, `.pill-queued` — consistent.
- `.ui-table` (note: the spec used the word `.table` but Tailwind already has a `.table` utility-like class, so the implementation names it `.ui-table` to avoid collisions — this is the plan-level decision). Templates that want the table treatment use `class="ui-table"`. The plan is internally consistent on this, but the spec uses `.table`. This is a **plan-level refinement** documented here so the engineer knows not to introduce a bare `.table` class.
- SVG partial file names match between Task 4 (create) and Tasks 5, 8, 9, 11, 12, 13 (include).
- Hero photo filenames `studio-hero.jpg` and `console-panel.jpg` are consistent between Task 7 (create) and Tasks 8, 12, 13 (reference).

All types, paths, and class names are consistent across tasks.

### Scope check
All tasks map to a single spec. No cross-subsystem work. Ready to execute.
