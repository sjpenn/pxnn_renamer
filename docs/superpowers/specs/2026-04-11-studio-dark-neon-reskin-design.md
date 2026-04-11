# Studio Dark / Neon DAW Reskin — Design Spec

**Date:** 2026-04-11
**Branch target:** `feat/studio-dark-neon-reskin`
**Approach:** A — Token swap + component polish (no template componentization in this pass)
**Stitch reference:** `https://stitch.withgoogle.com/projects/7726411999300532473` — screenshots captured to `docs/stitch-reference/`

## 1. Goal

Replace the current "Precision Slate" (blue enterprise SaaS) look with a **Studio Dark / Neon DAW** aesthetic that feels like a music industry tool. Reskin only — no new routes, no new surfaces, no refactor of the wizard monolith. Every existing page gets the new skin; no functional behavior changes.

The Stitch mockups provide the UX structure reference for future dashboards, but this spec deliberately scopes only the **currently-shipping pages**: `home.html`, `app.html`, `auth/login.html`, `auth/register.html`, `profile.html`, plus the global `base.html`, `partials/nav.html`, `partials/footer.html`.

## 2. Visual Theme & Atmosphere

Dark, focused, cinematic — evokes a late-night DAW session (Ableton, Logic, Serato). Neon is **surgical**: reserved for CTAs, active states, key metrics, focus rings, and a single glow accent per screen. The darks carry a 2% SVG noise grain so they don't feel flat-digital. Typography leans into Geist Mono for any filename, BPM, or readout — the single strongest signal that this is a pro-audio tool, not a generic SaaS.

Mood adjectives: focused, technical, cinematic, confident, quiet-confident.
Anti-patterns to avoid: synthwave gradients, glowing text everywhere, VHS scanlines, heavy drop shadows, bubble-rounded corners.

## 3. Design Tokens

Replace the current `tailwind.config.theme.extend` block in `base.html` with these tokens.

### 3.1 Color tokens

| Token | Hex | Role |
|---|---|---|
| `stage` | `#0a0b0f` | Page background — darkest layer, "stage black" |
| `stage-raised` | `#13151c` | Cards, panels, nav rail |
| `stage-sunken` | `#07080b` | Inset wells (file drop zone, code blocks, waveform bed) |
| `rail` | `#1c1f2a` | Sidebar rail, elevated sections under cards |
| `hairline` | `#232836` | 1px borders, table dividers, card outlines |
| `ink` | `#eef2ff` | Primary text on dark |
| `ink-dim` | `#8b92a8` | Secondary/muted text (minimum 18px to meet WCAG AA) |
| `ink-mute` | `#545a6e` | Tertiary (placeholders, disabled) |
| `cyan` | `#00f0ff` | Primary accent — CTAs, active nav, focus rings, playhead, key metrics |
| `cyan-soft` | `#0088a3` | Hover states, pressed CTAs, non-glowing cyan |
| `magenta` | `#ff2d95` | Alt accent — "live" states, secondary CTAs, conflict highlights |
| `amber` | `#ffb300` | Warning/meter — VU meters, warnings, "processing" state |
| `success` | `#2de89a` | Match/success pills, saved states |
| `danger` | `#ff4e5b` | Conflict pills, destructive confirmations |

### 3.2 Typography

| Role | Font | Weight | Usage |
|---|---|---|---|
| Display | Manrope | 700 / 800 | Hero titles, section headers, metric numerals |
| Body | Inter | 400 / 500 | Paragraphs, UI labels, button text |
| Mono | Geist Mono | 400 / 500 | Filenames, BPM/Key, tech readouts, metric labels, timestamps — prominent |

All three fonts are already loaded in `base.html` via Google Fonts. No new fonts added.

### 3.3 Shape & elevation

- **Radii:** `sm=8px`, `md=12px`, `lg=16px`, `xl=20px`, `pill=full`. The previous custom `rounded-3xl`/`4xl` (24px/32px) are dropped as too bubbly for a console aesthetic. **Remediation:** the 30 existing usages of `rounded-3xl` / `rounded-4xl` across `home.html` (14), `app.html` (8), `profile.html` (6), `auth/login.html` (1), and `auth/register.html` (1) must be rewritten — `rounded-3xl` → `rounded-xl`, `rounded-4xl` → `rounded-xl`. Verified by grep returning zero hits for `rounded-3xl` and `rounded-4xl` in `frontend/`.
- **Shadows:** flat by default. Elevation comes from `stage-raised` vs `stage` contrast and `hairline` borders. One glow utility reserved: `shadow-glow-cyan = 0 0 24px rgba(0,240,255,0.18)`, used only on primary CTAs (hover/focus) and the current-step indicator.
- **Grain:** a 2% SVG noise overlay applied via `body::before` as a data URI. No extra HTTP request.

### 3.4 Focus & motion

- `:focus-visible` = 2px cyan outline + 2px stage offset, replacing Tailwind's default blue.
- Default transition: `transition-[background,border-color,box-shadow] duration-150`. No bouncy easings.

## 4. Component Primitives

Defined once in `frontend/static/css/style.css` under `@layer components`. Templates use these class names, not raw Tailwind utilities, wherever a component repeats.

### 4.1 Buttons

```
.btn           base: rounded-lg, px-5 py-2.5, font-semibold, transition
.btn-primary   bg-cyan text-stage; hover:bg-white; focus-visible: shadow-glow-cyan
.btn-ghost     border-hairline text-ink; hover:border-cyan hover:text-cyan
.btn-danger    border-hairline text-danger; hover:bg-danger/10
.btn-icon      square, toolbar use, cyan hover tint
```

- Primary CTAs carry **no colored shadow at rest**; the glow is a focus/hover-only affordance.
- Disabled: `bg-rail text-ink-mute cursor-not-allowed`, no border.

### 4.2 Cards / surfaces

```
.card          bg-stage-raised border border-hairline rounded-xl
.card-inset    bg-stage-sunken border border-hairline rounded-lg (wells)
.card-hover    hover:border-cyan/40 transition
.card-active   border-cyan shadow-glow-cyan (selected row/preset/step)
```

No drop shadows by default — elevation is carried by surface contrast.

### 4.3 Navigation

- **Top nav (`partials/nav.html`):** full-bleed `bg-stage-raised` with `hairline` bottom border. Wordmark left (cyan waveform glyph + "PxNN" in Manrope 800). Links centered in `ink-dim` with `hover:text-cyan` and active-underline in cyan. Right side: Sign In `btn-ghost` + Get Started `btn-primary` when logged out; user chip when logged in.
- **User chip:** small pill showing avatar initial + name on `stage-raised`, cyan focus ring when open.
- **Mobile:** hamburger opens a `stage-raised` sheet with vertically-stacked links.
- **Footer (`partials/footer.html`):** single-row, `ink-dim` text, `hairline` top border, small wordmark + © line + 2–3 links (Privacy, Terms, Contact). Intentionally quiet.

### 4.4 Inputs & forms

```
.input         bg-stage-sunken border border-hairline text-ink rounded-lg
               focus:border-cyan focus:ring-2 focus:ring-cyan/30
.label         text-xs uppercase tracking-wide text-ink-dim font-medium
.field-group   label + input with a consistent 6px gap
```

- Placeholders render in `ink-mute`.
- Error: `border-danger` + small danger helper text beneath.
- Register password-match indicator uses `success` / `danger` live feedback.

### 4.5 Tables (file lists, preview rows)

```
.table          w-full text-sm border-separate border-spacing-0
.table th       text-ink-dim uppercase text-xs tracking-wide px-4 py-3
                border-b border-hairline
.table td       px-4 py-3 border-b border-hairline font-mono text-ink
.table tr:hover bg-rail/50
```

All `.table td` cells default to Geist Mono via the class definition above — this is deliberate. Filename lists, size readouts, format tags, and preview "new name" columns all render mono, which is the single biggest visual cue that the app is a DAW-adjacent tool. Header cells (`th`) stay in Inter (sans) because they're short uppercase labels and already have their own styling.

### 4.6 Status pills

| Pill | Use | Style |
|---|---|---|
| `.pill-match` | successful rename | `bg-success/15 text-success border border-success/30 rounded-full px-2 py-0.5 text-[11px] font-mono uppercase` |
| `.pill-conflict` | naming collision | same shape, `danger` colors |
| `.pill-processing` | in-flight file | `amber` colors, optional pulse |
| `.pill-queued` | waiting | `ink-dim` colors, no pulse |

All pills render in mono small caps — looks like a DAW meter label.

### 4.7 Waveform / EQ SVG chrome

Inline SVG partials under `frontend/templates/partials/svg/`. All use `stroke="currentColor"` or `fill="currentColor"` so they theme via parent Tailwind class.

| SVG | File | Usage |
|---|---|---|
| `waveform_line.html` | sinusoidal line in cyan with soft magenta shadow | home final-CTA background, hero filename-stack divider, section dividers |
| `eq_bars.html` | 8–16 animated EQ bars (pure CSS keyframes) | "live" indicator next to active labels, drop-zone hover, step-number accent |
| `spectrogram_grid.html` | dotted grid | hero upper-half backdrop, empty-state backgrounds |
| `wordmark_glyph.html` | small cyan square-waveform icon | nav wordmark |

Each SVG ≤1KB. No external files, no build step.

### 4.8 Drop zones

- `bg-stage-sunken`, dashed `hairline` border, Material Symbols `cloud_upload` icon 48px in cyan.
- On `drag-over`: border becomes solid cyan + faint inner cyan glow + the `eq_bars` SVG starts animating.

### 4.9 Hero photo treatment

Any hero photo is wrapped in `bg-stage overflow-hidden rounded-xl` and rendered with this CSS recipe:

- `filter: brightness(0.55) contrast(1.15) saturate(0.9)`
- Cyan multiply overlay (`#00313a`, 40%)
- Bottom-to-top `stage` gradient so copy reads
- Optional magenta corner vignette

This recipe carries any stock photo regardless of original lighting — the visual system doesn't depend on finding "the perfect shot."

### 4.10 Icons

No change — continue using Material Symbols Outlined (Google Fonts) already loaded. Color rule: action icons (upload, play, save, settings) render in `cyan`; state/info icons (check, info, lock) render in `ink-dim` unless a status color applies.

## 5. Page-by-page plan

### 5.1 `base.html`
- Replace `tailwind.config.theme.extend` with the Section 3 tokens.
- `<body>` default becomes `bg-stage text-ink`.
- Add the 2% noise overlay via `body::before`.
- Register the `@layer components` block (Section 4) in `static/css/style.css` so templates can use `.btn-*`, `.card*`, `.input`, `.table`, `.pill-*`, `.glow-cyan`, `.hairline`, `.shadow-glow-cyan`.
- Font preloads unchanged.

### 5.2 `partials/nav.html`
- Full-bleed `stage-raised` bar with `hairline` bottom border.
- Left: cyan waveform-glyph SVG + "PxNN" wordmark in Manrope 800.
- Center: nav links in `ink-dim` with `hover:text-cyan`, active-underline in cyan.
- Right: `btn-ghost` "Sign In" + `btn-primary` "Get Started" (logged-out) or user chip (logged-in).
- Mobile: hamburger opens a `stage-raised` sheet with vertically stacked links.

### 5.3 `partials/footer.html`
- Single-row, `ink-dim`, `hairline` top border, small wordmark + © line + Privacy / Terms / Contact links.

### 5.4 `home.html` (landing)
The current file has 8 sections (verified from the source). Each maps 1:1 to a reskin treatment:

1. **HERO** (line 8) — `stage` bg with `spectrogram_grid` SVG tiled in the upper half. Hero photo A (dark studio) sits full-bleed at ~25% opacity behind copy. Kicker `BULK AUDIO FILE RENAMER` in mono small caps, cyan. H1 Manrope 800 (existing copy). Red strikethrough `"track_final_v2.wav"` becomes `danger` color on dark. Subcopy `ink-dim`. CTAs: `btn-primary` "Get Started Free" + `btn-ghost` "See how it works". The existing filename-stack card becomes a `.card` with Geist-Mono filenames, `success`-colored arrow icons, `ink-dim` struck-through before-names; the downward arrow gets a cyan glow.
2. **PROBLEM** (line 51) — two side-by-side `.card`s, each with a cyan Material Symbols icon at top. Bullet markers render in `danger`.
3. **HOW IT WORKS** (line 77) — three-up step cards with giant `01 / 02 / 03` in Manrope 800 and a small cyan `eq_bars` SVG under each number. Hover applies `.card-hover`.
4. **LIVE EXAMPLE** (line 105) — a `.card-inset` container wrapping the existing example. Before filenames in Geist Mono `ink-dim` with strikethrough; after filenames in Geist Mono `ink`; match pills to the right. A faint `waveform_line` SVG sits behind the example at low opacity as visual interest.
5. **FEATURES** (line 141) — six feature cards, each with a Material Symbols icon in cyan on a `.card-inset` square. Body text `ink-dim`.
6. **PRICING** (line 180) — three plan cards. Recommended plan uses `.card-active`. Price in Manrope 800 with `/mo` in small Geist Mono.
7. **STATS** (line 208) — full-bleed `stage-sunken` band with 3–4 giant metric numerals in Manrope 800 and mono small-caps labels beneath. A single cyan `waveform_line` runs across the bottom edge as a divider.
8. **FINAL CTA** (line 227) — full-bleed `stage` band with a `waveform_line` SVG across the background in cyan + magenta split-tone. One centered `btn-primary`.

### 5.5 `app.html` (wizard)
**No file split.** Reskin in place.

- Wrap the whole app in a two-column shell: `rail` sidebar left (nav + step indicator), main area right. Mobile collapses the sidebar to a top strip.
- **Step indicator:** three bars on the rail. Current step = `bg-cyan shadow-glow-cyan`. Completed = `bg-cyan-soft`. Pending = `hairline`.
- **Step 1 (file stage):** the drop zone becomes the Section 4.8 pattern. The file list becomes a `.table` with Geist Mono filenames and `ink-dim` mono size column.
- **Step 2 (metadata rules):** each rule block becomes a `.card` with a mono small-caps header (`SEARCH & REPLACE`, `SEQUENTIAL NUMBERING`, `TAG-BASED`). Inputs use `.input`. "Add rule" = `btn-ghost`.
- **Step 3 (review & run):** left column = Live Preview `.table` with `.pill-match` / `.pill-conflict` / `.pill-processing`. Right column = metrics strip (`TOTAL / RENAMING / SKIPPING / CONFLICTS`) where numbers render in Manrope 800 with mono labels beneath. Bottom action bar: `Apply Changes` as `btn-primary`.
- Every existing `hx-*` attribute, target ID, and swap selector is preserved. Only class lists and a minimal set of wrapper divs change.

### 5.6 `auth/login.html`
- 50/50 split on desktop. Left: hero photo B (control surface closeup with cyan key light) treated per Section 4.9. Right: form centered on `stage`.
- Form inside a `.card` with a `SIGN IN` mono small-caps header. Email/password use `.input`. Primary submit = `btn-primary`. Google OAuth = `btn-ghost` with the Google "G".
- Footer line: "New here? Create an account →" in `ink-dim` with cyan link.
- Mobile: photo collapses to a top hero strip, form stacks beneath.

### 5.7 `auth/register.html`
- Same split layout as login, mirrored (photo on the right).
- Password-match live indicator uses `success`/`danger` helper text.
- Mobile: same collapse behavior as login.

### 5.8 `profile.html`
- Single column on `stage`, `max-w-2xl` centered.
- Three stacked `.card`s: **Identity** (avatar + name + email), **Password** (change form), **Danger Zone** (`border-danger/40` accent, `btn-danger` delete).
- Section headers in mono small caps.

## 6. Imagery plan

### 6.1 Hero photos (2 total)

| Slot | Template | Subject | Treatment |
|---|---|---|---|
| A | `home.html` hero background | Dark studio: mixing console closeup with underlit faders, or modular synth wall with glowing patch cables | Section 4.9 recipe, rendered at ~25% opacity behind H1 |
| B | `auth/login.html` + `auth/register.html` split panel | Control surface closeup (faders, knobs, jog wheel) with subtle cyan key light | Section 4.9 recipe at full opacity; panel is the visual |

**Sourcing:** Unsplash (Unsplash License — free for commercial use, no attribution required but will be credited). Two candidates per slot, committed to `frontend/static/img/hero/` with a `CREDITS.md` listing photographer + URL + license. Final pick gated on user approval during implementation.

**Format:** 1920×1080 JPG, quality 80, target ~200–250KB each after optimization. Served statically.

### 6.2 SVG chrome

All four SVGs (Section 4.7) live as Jinja includes under `frontend/templates/partials/svg/`. Each is ≤1KB and themes via `currentColor`.

### 6.3 Icons

Material Symbols Outlined — already loaded, no change.

### 6.4 Explicitly excluded

- No stock photos beyond the 2 hero slots.
- No illustrations, 3D renders, Lottie animations, or video backgrounds.
- No album-art placeholders (Dashboard-specific, out of scope).
- No favicon / PWA icon updates (out of scope).

## 7. Verification

All checks must pass before the work is claimed complete.

### 7.1 Visual

- [ ] Every reskinned template renders cleanly at 375px, 768px, 1280px, and 1920px: `base.html`, `home.html`, `app.html`, `auth/login.html`, `auth/register.html`, `profile.html`, `partials/nav.html`, `partials/footer.html`.
- [ ] Grep for residual Precision Slate tokens across `frontend/` returns zero hits. Use these exact search terms so unrelated Tailwind utilities don't false-positive:
  - `primary-container`, `primary-fixed`, `primary-fixed-dim`
  - `surface-bright`, `surface-container-high`
  - `deep-slate`
  - `inverse-surface`, `inverse-on-surface`
  - `on-secondary`
  - Prefixed forms for the ambiguous tokens: `bg-secondary`, `text-secondary`, `border-secondary`, `ring-secondary`
  - Prefixed forms for the custom `outline` color token: `bg-outline`, `text-outline`, `border-outline`, `ring-outline` (do **not** grep bare `outline`, which matches Tailwind's outline utility)
  - The entire old `theme.extend.colors` block in `base.html` must be gone.
- [ ] Grep returns zero hits for `rounded-3xl` and `rounded-4xl` across `frontend/`.
- [ ] Every interactive element has a visible `:focus-visible` cyan ring.
- [ ] Contrast: `ink` on `stage` and `ink` on `stage-raised` both meet WCAG AA for body text (4.5:1). `ink-dim` is never used for body copy smaller than 18px.

### 7.2 Functional (zero regressions)

- [ ] Wizard in `app.html` completes a full rename end-to-end: drop files → define rules → preview → apply.
- [ ] Register and login both succeed against existing backend routes.
- [ ] Google OAuth login still redirects to `/app` (preserves commit `4da5e55`).
- [ ] Profile page still edits identity, changes password, and deletes the account.
- [ ] No broken `hx-target` / `hx-swap` references in `app.html` — diff carefully.

### 7.3 Performance

- [ ] No more than 2 image files added under `frontend/static/img/hero/`, each ≤250KB.
- [ ] Total added CSS in `style.css` stays under 8KB gzipped.
- [ ] Tailwind CDN stays; no build step introduced.

### 7.4 Evidence

- [ ] Playwright MCP screenshots of every reskinned page at 1280px saved to `docs/superpowers/evidence/2026-04-11-studio-dark-neon-reskin/`.
- [ ] Mobile (375px) screenshots of `home.html` and `app.html` in the same evidence folder.

## 8. Rollout

- **Branch:** `feat/studio-dark-neon-reskin` off `main`.
- **Single PR, no feature flag.** The reskin is reversible at the token layer, so the whole thing ships as one commit.
- **Pre-merge manual pass:** `docker-compose up --build`, click through `/`, `/app`, `/login`, `/register`, `/profile`, then run the Playwright screenshot sweep.
- **Rollback:** revert the single merge commit. All changes live inside `frontend/` plus `docs/`.

## 9. Out of scope

Deferred to follow-up specs if desired:

- Dashboard route (Stitch screen 2)
- File Library route (Stitch screen 3)
- Renaming Workflow as a separate route (Stitch screen 4)
- Settings & Presets route (Stitch screen 5)
- Batch Processing Progress route (Stitch screen 6)
- Componentizing `app.html` into Jinja partials
- Light-mode toggle
- Favicon / PWA icon set
- Dashboard empty-state illustrations
- Any backend changes
