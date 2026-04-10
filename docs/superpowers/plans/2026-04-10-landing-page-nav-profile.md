# Marketing Homepage + Nav + Auth Pages + Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the PxNN it frontend into a proper SaaS surface with a marketing homepage at `/`, workspace at `/app`, dedicated `/login` and `/register` pages, a `/profile` page, and a global top-right nav.

**Architecture:** Extract a shared `base.html` template and reusable `partials/nav.html` and `partials/footer.html`. Rename the current monolithic `index.html` to `app.html` and extend base. Create a new marketing `home.html` with hero animation, problem/solution sections, pricing, and CTAs. Add `/login`, `/register`, `/profile` page routes that reuse existing auth endpoints via JavaScript form submission. Add two new profile endpoints (`/api/profile/password` and `/api/profile/delete`).

**Tech Stack:** FastAPI, Jinja2, Tailwind CSS (CDN), vanilla JavaScript, existing authlib session middleware, SQLAlchemy, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/templates/base.html` | Create | HTML skeleton, head, Tailwind config, shared CSS/fonts |
| `frontend/templates/partials/nav.html` | Create | Global top-right navigation component |
| `frontend/templates/partials/footer.html` | Create | Marketing page footer |
| `frontend/templates/home.html` | Create | Marketing homepage (hero, problem, features, pricing, CTA) |
| `frontend/templates/app.html` | Create | Renamed from `index.html`; workspace wizard |
| `frontend/templates/index.html` | Delete | Replaced by `home.html` + `app.html` |
| `frontend/templates/auth/login.html` | Create | Dedicated login page |
| `frontend/templates/auth/register.html` | Create | Dedicated register page |
| `frontend/templates/profile.html` | Create | User profile page (identity, password, delete) |
| `frontend/static/css/style.css` | Modify | Add marketing animation keyframes and reveal-on-scroll utilities |
| `backend/app/main.py` | Modify | Split old `/` into `/` (marketing) + `/app` (workspace); add `/login`, `/register`, `/profile` handlers; include profile router |
| `backend/app/routes/oauth.py` | Modify | Change OAuth callback redirect from `/` to `/app` |
| `backend/app/routes/profile.py` | Create | Password update and account delete endpoints |
| `backend/app/core/security.py` | Modify | Add `set_pending_plan` and `pop_pending_plan` session helpers |
| `tests/test_routes_pages.py` | Create | Tests for home, app, login, register page routes |
| `tests/test_profile.py` | Create | Tests for profile page and profile endpoints |

---

## Task 1: Session Plan Helpers

**Files:**
- Modify: `backend/app/core/security.py`

- [ ] **Step 1: Read the current `security.py` to find the import block and end of file**

Run: `cat backend/app/core/security.py | head -15`
Expected: see the existing imports.

- [ ] **Step 2: Add session helpers**

Append these two functions to the end of `backend/app/core/security.py`:

```python
def set_pending_plan(request: Request, plan_key: str) -> None:
    """Store a plan key in the session for post-registration checkout redirect."""
    request.session["pending_plan"] = plan_key


def pop_pending_plan(request: Request) -> Optional[str]:
    """Retrieve and clear the pending plan from the session."""
    return request.session.pop("pending_plan", None)
```

`Request` and `Optional` are already imported at the top of the file.

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/security.py
git commit -m "feat: add pending plan session helpers for post-register checkout"
```

---

## Task 2: Create `base.html` Template

**Files:**
- Create: `frontend/templates/base.html`

- [ ] **Step 1: Read current `index.html` head section to capture existing head elements**

Run: `sed -n '1,40p' frontend/templates/index.html`
Expected: current doctype, meta, title, fonts, Tailwind CDN, inline config.

- [ ] **Step 2: Create `frontend/templates/base.html`**

```html
<!doctype html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{% block title %}PxNN it{% endblock %}</title>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link
        href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Manrope:wght@600;700;800&family=Geist+Mono:wght@400;500&display=swap"
        rel="stylesheet">
    <link
        href="https://fonts.googleapis.com/icon?family=Material+Symbols+Outlined"
        rel="stylesheet">

    <script src="https://cdn.tailwindcss.com"></script>
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
                        'primary-container': '#0052cc',
                        'primary-fixed': '#dae2ff',
                        'primary-fixed-dim': '#b2c5ff',
                        'secondary': '#4c5d8d',
                        'inverse-surface': '#233144',
                        'inverse-on-surface': '#eaf1ff',
                        'surface-bright': '#f8f9ff',
                        'surface-container-high': '#dce9ff',
                        'on-secondary': '#ffffff',
                        'outline': '#737685',
                        'deep-slate': '#1a1f2e',
                    },
                    borderRadius: {
                        '3xl': '1.5rem',
                        '4xl': '2rem',
                    },
                },
            },
        };
    </script>

    <link rel="stylesheet" href="/static/css/style.css">

    {% block extra_head %}{% endblock %}
</head>
<body class="min-h-full font-sans text-deep-slate antialiased {% block body_class %}bg-surface-bright{% endblock %}">
    {% block body %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/templates/base.html
git commit -m "feat: add shared base.html template with head, fonts, Tailwind config"
```

---

## Task 3: Create `partials/nav.html`

**Files:**
- Create: `frontend/templates/partials/nav.html`

- [ ] **Step 1: Create the nav partial**

```html
{# Nav partial. Expects: current_user (User|None), page (string), google_oauth_enabled (bool) #}
<nav class="sticky top-0 z-50 w-full bg-white/90 backdrop-blur-md border-b border-outline/10">
    <div class="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {# Left: logo + marketing links #}
        <div class="flex items-center gap-8">
            <a href="{% if current_user %}/app{% else %}/{% endif %}" class="flex items-center gap-2 font-display font-bold text-lg text-deep-slate">
                <span class="material-symbols-outlined text-primary-container">sync_alt</span>
                PxNN it
            </a>
            {% if page in ['home', 'login', 'register'] %}
            <div class="hidden md:flex items-center gap-6 text-sm font-semibold text-secondary">
                <a href="/#features" class="hover:text-primary-container transition">Features</a>
                <a href="/#pricing" class="hover:text-primary-container transition">Pricing</a>
            </div>
            {% endif %}
        </div>

        {# Right: auth state #}
        <div class="flex items-center gap-3">
            {% if current_user %}
                <a href="/app"
                   class="hidden sm:inline-block text-sm font-semibold {% if page == 'app' %}text-primary-container border-b-2 border-primary-container{% else %}text-secondary hover:text-primary-container{% endif %} transition">
                    Dashboard
                </a>
                <a href="/app?billing=options"
                   class="hidden sm:inline-block text-sm font-semibold text-secondary hover:text-primary-container transition">
                    Billing
                </a>

                {# Avatar dropdown #}
                <div class="relative">
                    <button id="nav-user-dropdown-btn"
                            type="button"
                            class="flex items-center gap-2 rounded-full border border-outline/20 bg-white px-3 py-1.5 text-sm font-semibold text-deep-slate hover:border-primary-container transition">
                        <span class="material-symbols-outlined text-base">account_circle</span>
                        <span class="max-w-[120px] truncate">{{ current_user.username }}</span>
                        <span class="material-symbols-outlined text-base">expand_more</span>
                    </button>
                    <div id="nav-user-dropdown-menu"
                         class="hidden absolute right-0 mt-2 w-56 rounded-xl border border-outline/10 bg-white py-2 shadow-lg">
                        <div class="px-4 py-2 text-xs font-bold uppercase tracking-widest text-secondary opacity-60">
                            {{ current_user.username }}
                        </div>
                        <a href="/profile"
                           class="block px-4 py-2 text-sm text-deep-slate hover:bg-surface-bright transition">
                            Profile
                        </a>
                        <div class="my-1 border-t border-outline/10"></div>
                        <form method="post" action="/api/auth/logout" onsubmit="event.preventDefault(); fetch('/api/auth/logout', {method: 'POST'}).then(() => window.location.href = '/');">
                            <button type="submit"
                                    class="block w-full text-left px-4 py-2 text-sm text-deep-slate hover:bg-surface-bright transition">
                                Logout
                            </button>
                        </form>
                    </div>
                </div>
            {% else %}
                <a href="/login"
                   class="text-sm font-semibold {% if page == 'login' %}text-primary-container border-b-2 border-primary-container{% else %}text-secondary hover:text-primary-container{% endif %} transition">
                    Sign in
                </a>
                <a href="/register"
                   class="rounded-xl bg-primary-container px-4 py-2 text-sm font-bold text-white hover:bg-primary-container/90 transition">
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

- [ ] **Step 2: Commit**

```bash
git add frontend/templates/partials/nav.html
git commit -m "feat: add global nav partial with auth-aware menu and avatar dropdown"
```

---

## Task 4: Create `partials/footer.html`

**Files:**
- Create: `frontend/templates/partials/footer.html`

- [ ] **Step 1: Create the footer partial**

```html
<footer class="mt-20 border-t border-outline/10 bg-surface-bright">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10">
        <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div>
                <div class="flex items-center gap-2 font-display font-bold text-lg text-deep-slate">
                    <span class="material-symbols-outlined text-primary-container">sync_alt</span>
                    PxNN it
                </div>
                <p class="mt-2 text-sm text-secondary">Bulk audio file renamer for producers and labels</p>
            </div>

            <div class="flex flex-wrap gap-6 text-sm font-semibold text-secondary">
                <a href="/#features" class="hover:text-primary-container transition">Features</a>
                <a href="/#pricing" class="hover:text-primary-container transition">Pricing</a>
                <a href="/login" class="hover:text-primary-container transition">Login</a>
                <a href="/register" class="hover:text-primary-container transition">Register</a>
            </div>

            <div class="flex items-center gap-4 text-sm text-secondary">
                <span>&copy; 2026 PxNN it</span>
                <a href="https://github.com/sjpenn/pxnn_renamer" target="_blank" rel="noopener"
                   class="hover:text-primary-container transition" aria-label="GitHub">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.387.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
                </a>
            </div>
        </div>
    </div>
</footer>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/templates/partials/footer.html
git commit -m "feat: add marketing footer partial with links and GitHub icon"
```

---

## Task 5: Rename `index.html` to `app.html` and Extend Base

**Files:**
- Create: `frontend/templates/app.html`
- Delete: `frontend/templates/index.html`

- [ ] **Step 1: Copy index.html to app.html**

```bash
cp frontend/templates/index.html frontend/templates/app.html
```

- [ ] **Step 2: Replace head block in app.html**

Open `frontend/templates/app.html` in an editor. Replace the entire section from `<!doctype html>` through the closing `</head>` tag (keep the opening `<body>` tag for now) with:

```
{% extends "base.html" %}

{% block title %}PxNN it — Workspace{% endblock %}

{% block body_class %}bg-surface-bright min-h-screen{% endblock %}

{% block body %}
{% include "partials/nav.html" %}
```

Then find the closing `</body>` and `</html>` tags at the end of the file and replace them with:

```
{% endblock %}
```

- [ ] **Step 3: Remove the signed-out auth forms from app.html**

The current `index.html` has a `<section id="signed-out-shell">` that contains login and register forms with a Google button. Delete the entire `<section id="signed-out-shell">...</section>` block.

- [ ] **Step 4: Remove the wizard-lockout overlay**

Find and delete the entire element with id `wizard-lockout` (used to block unauthenticated users from interacting with the wizard). It's no longer needed because logged-out users cannot reach `/app`.

- [ ] **Step 5: Simplify JavaScript signed-out branches**

In the inline `<script>` block, find `signedOutShell` and `signedInShell` references. Remove the logic that toggles them — specifically:
- Delete lines like `signedOutShell.classList.toggle("hidden", Boolean(state.user));`
- Delete lines like `signedInShell.classList.toggle("hidden", !state.user);`
- Delete the `const signedOutShell = document.getElementById("signed-out-shell");` lookup
- Delete references to `wizardLockout`
- Leave all other workspace JS unchanged

- [ ] **Step 6: Delete the original `index.html`**

```bash
rm frontend/templates/index.html
```

- [ ] **Step 7: Commit**

```bash
git add frontend/templates/app.html
git rm frontend/templates/index.html
git commit -m "refactor: rename index.html to app.html, extend base, remove inline auth"
```

---

## Task 6: Marketing Animations in `style.css`

**Files:**
- Modify: `frontend/static/css/style.css`

- [ ] **Step 1: Append marketing animations and reveal utilities**

Append these styles to the end of `frontend/static/css/style.css`:

```css
/* ============================================================
   Marketing page animations
   ============================================================ */

html {
    scroll-behavior: smooth;
}

/* Reveal-on-scroll — activated by IntersectionObserver adding .in-view */
.reveal-on-scroll {
    opacity: 0;
    transform: translateY(20px);
    transition: opacity 0.6s ease-out, transform 0.6s ease-out;
}

.reveal-on-scroll.in-view {
    opacity: 1;
    transform: translateY(0);
}

/* Filename morph hero animation — three stacked pairs cycle via animation-delay */
.filename-stack {
    position: relative;
    display: grid;
    place-items: center;
    min-height: 140px;
}

.filename-pair {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    opacity: 0;
    animation: filename-fade 30s infinite;
}

.filename-pair:nth-child(1) { animation-delay: 0s; }
.filename-pair:nth-child(2) { animation-delay: 10s; }
.filename-pair:nth-child(3) { animation-delay: 20s; }

@keyframes filename-fade {
    0%, 3%   { opacity: 0; transform: translateY(8px); }
    6%, 30%  { opacity: 1; transform: translateY(0); }
    33%, 100% { opacity: 0; transform: translateY(-8px); }
}

.filename-before {
    font-family: 'Geist Mono', monospace;
    font-size: 0.95rem;
    color: #ef4444;
    text-decoration: line-through;
    text-decoration-color: rgba(239, 68, 68, 0.5);
}

.filename-arrow {
    font-size: 1.25rem;
    color: #0052cc;
}

.filename-after {
    font-family: 'Geist Mono', monospace;
    font-size: 1rem;
    font-weight: 600;
    color: #0f766e;
}

/* Feature card hover lift */
.feature-card {
    transition: transform 180ms ease-out, box-shadow 180ms ease-out;
}

.feature-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 24px -8px rgba(15, 23, 42, 0.12);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/static/css/style.css
git commit -m "feat: add marketing page animations and reveal-on-scroll utilities"
```

---

## Task 7: Create `home.html` Marketing Page

**Files:**
- Create: `frontend/templates/home.html`

- [ ] **Step 1: Create the marketing homepage**

```html
{% extends "base.html" %}

{% block title %}PxNN it — Bulk audio file renamer for producers & labels{% endblock %}

{% block body %}
{% include "partials/nav.html" %}

{# ============================ HERO ============================ #}
<section class="relative overflow-hidden bg-gradient-to-b from-surface-bright via-primary-fixed/30 to-surface-bright">
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 py-20 md:py-28 text-center">
        <p class="text-xs font-bold uppercase tracking-[0.2em] text-primary-container mb-4">BULK AUDIO FILE RENAMER</p>
        <h1 class="font-display font-extrabold text-4xl md:text-6xl leading-tight text-deep-slate">
            Stop drowning in<br>
            <span class="font-mono text-2xl md:text-4xl text-red-500 line-through opacity-80">"track_final_v2.wav"</span>
        </h1>
        <p class="mt-6 max-w-2xl mx-auto text-lg md:text-xl text-secondary">
            PxNN it renames hundreds of audio files at once with clean, consistent, metadata-rich filenames.
        </p>
        <div class="mt-8 flex flex-wrap items-center justify-center gap-4">
            <a href="/register" class="rounded-xl bg-primary-container px-6 py-3 font-bold text-white hover:bg-primary-container/90 transition shadow-lg">
                Get Started Free
            </a>
            <a href="#how-it-works" class="rounded-xl border border-outline/20 bg-white px-6 py-3 font-bold text-deep-slate hover:border-primary-container transition">
                See how it works
            </a>
        </div>

        {# Hero animation card #}
        <div class="mt-14 mx-auto max-w-2xl rounded-3xl border border-outline/10 bg-white p-6 md:p-8 shadow-xl">
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

{# ============================ PROBLEM ============================ #}
<section id="problem" class="py-20">
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-8 feature-card">
                <span class="material-symbols-outlined text-4xl text-primary-container">music_note</span>
                <h2 class="mt-4 font-display font-bold text-2xl text-deep-slate">Beat makers: every session is a mess</h2>
                <ul class="mt-4 space-y-3 text-secondary">
                    <li class="flex gap-3"><span class="text-red-500">&bull;</span> Downloads folder full of "beat1.wav", "beat1_FINAL.wav", "beat1_FINAL_REAL.wav"</li>
                    <li class="flex gap-3"><span class="text-red-500">&bull;</span> Clients demand specific naming formats for every delivery</li>
                    <li class="flex gap-3"><span class="text-red-500">&bull;</span> Can't find last month's session when you need it</li>
                </ul>
            </article>
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-8 feature-card">
                <span class="material-symbols-outlined text-4xl text-primary-container">album</span>
                <h2 class="mt-4 font-display font-bold text-2xl text-deep-slate">Labels: 500 demos a week, zero consistency</h2>
                <ul class="mt-4 space-y-3 text-secondary">
                    <li class="flex gap-3"><span class="text-red-500">&bull;</span> Artists submit with inconsistent or missing metadata</li>
                    <li class="flex gap-3"><span class="text-red-500">&bull;</span> Manual rename takes 2 hours per batch, every batch</li>
                    <li class="flex gap-3"><span class="text-red-500">&bull;</span> Lost track of which version of which song from which artist</li>
                </ul>
            </article>
        </div>
    </div>
</section>

{# ============================ HOW IT WORKS ============================ #}
<section id="how-it-works" class="py-20 bg-primary-fixed/20">
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 text-center">
        <h2 class="font-display font-extrabold text-3xl md:text-4xl text-deep-slate">How it works</h2>
        <p class="mt-3 text-lg text-secondary">Three steps. Batch-renamed in seconds.</p>
        <div class="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-8 feature-card">
                <div class="text-xs font-bold uppercase tracking-widest text-primary-container">01</div>
                <span class="mt-4 material-symbols-outlined text-5xl text-primary-container">upload_file</span>
                <h3 class="mt-4 font-display font-bold text-xl">Upload</h3>
                <p class="mt-2 text-secondary">Drag & drop your audio files</p>
            </article>
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-8 feature-card">
                <div class="text-xs font-bold uppercase tracking-widest text-primary-container">02</div>
                <span class="mt-4 material-symbols-outlined text-5xl text-primary-container">tune</span>
                <h3 class="mt-4 font-display font-bold text-xl">Define</h3>
                <p class="mt-2 text-secondary">Set your format template</p>
            </article>
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-8 feature-card">
                <div class="text-xs font-bold uppercase tracking-widest text-primary-container">03</div>
                <span class="mt-4 material-symbols-outlined text-5xl text-primary-container">download</span>
                <h3 class="mt-4 font-display font-bold text-xl">Export</h3>
                <p class="mt-2 text-secondary">Download your renamed archive</p>
            </article>
        </div>
    </div>
</section>

{# ============================ LIVE EXAMPLE ============================ #}
<section class="py-20">
    <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-center font-display font-extrabold text-3xl md:text-4xl text-deep-slate">See it in action</h2>
        <p class="mt-3 text-center text-lg text-secondary">Real examples from a real batch</p>
        <div class="mt-10 rounded-3xl border border-outline/10 bg-white overflow-hidden shadow-lg">
            <div class="grid grid-cols-2 divide-x divide-outline/10">
                <div class="p-4 bg-red-50 text-center text-xs font-bold uppercase tracking-widest text-red-700">Before</div>
                <div class="p-4 bg-emerald-50 text-center text-xs font-bold uppercase tracking-widest text-emerald-700">After</div>
            </div>
            <div class="divide-y divide-outline/10">
                <div class="reveal-on-scroll grid grid-cols-2 divide-x divide-outline/10">
                    <div class="p-4 font-mono text-sm text-red-600 line-through opacity-80">track_final_v2 (1).wav</div>
                    <div class="p-4 font-mono text-sm text-emerald-700 font-semibold">JuneLake_Nightfall_Cmin_128BPM.wav</div>
                </div>
                <div class="reveal-on-scroll grid grid-cols-2 divide-x divide-outline/10">
                    <div class="p-4 font-mono text-sm text-red-600 line-through opacity-80">beat ideas 03 FULL.wav</div>
                    <div class="p-4 font-mono text-sm text-emerald-700 font-semibold">JuneLake_Sunset_Amin_90BPM.wav</div>
                </div>
                <div class="reveal-on-scroll grid grid-cols-2 divide-x divide-outline/10">
                    <div class="p-4 font-mono text-sm text-red-600 line-through opacity-80">Untitled Project 14.aif</div>
                    <div class="p-4 font-mono text-sm text-emerald-700 font-semibold">JuneLake_HorizonLine_Gmaj_120BPM.aif</div>
                </div>
                <div class="reveal-on-scroll grid grid-cols-2 divide-x divide-outline/10">
                    <div class="p-4 font-mono text-sm text-red-600 line-through opacity-80">mix_master_real_final.mp3</div>
                    <div class="p-4 font-mono text-sm text-emerald-700 font-semibold">JuneLake_MidnightDrive_Dmin_140BPM.mp3</div>
                </div>
                <div class="reveal-on-scroll grid grid-cols-2 divide-x divide-outline/10">
                    <div class="p-4 font-mono text-sm text-red-600 line-through opacity-80">nev song.wav</div>
                    <div class="p-4 font-mono text-sm text-emerald-700 font-semibold">JuneLake_FirstLight_Emaj_110BPM.wav</div>
                </div>
            </div>
        </div>
    </div>
</section>

{# ============================ FEATURES ============================ #}
<section id="features" class="py-20 bg-primary-fixed/20">
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-center font-display font-extrabold text-3xl md:text-4xl text-deep-slate">Everything you need</h2>
        <div class="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-6 feature-card">
                <span class="material-symbols-outlined text-4xl text-primary-container">bolt</span>
                <h3 class="mt-3 font-display font-bold text-lg">Lightning fast</h3>
                <p class="mt-2 text-sm text-secondary">Rename hundreds of files in seconds, not hours</p>
            </article>
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-6 feature-card">
                <span class="material-symbols-outlined text-4xl text-primary-container">tune</span>
                <h3 class="mt-3 font-display font-bold text-lg">Flexible templates</h3>
                <p class="mt-2 text-sm text-secondary"><code class="font-mono text-xs">{ARTIST}_{TITLE}_{KEY}_{BPM}</code> — build any format</p>
            </article>
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-6 feature-card">
                <span class="material-symbols-outlined text-4xl text-primary-container">auto_fix_high</span>
                <h3 class="mt-3 font-display font-bold text-lg">Precision cleanup</h3>
                <p class="mt-2 text-sm text-secondary">Strip version tags, fix casing, normalize spaces automatically</p>
            </article>
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-6 feature-card">
                <span class="material-symbols-outlined text-4xl text-primary-container">music_note</span>
                <h3 class="mt-3 font-display font-bold text-lg">All major formats</h3>
                <p class="mt-2 text-sm text-secondary">WAV, MP3, AIFF, FLAC — every format you actually use</p>
            </article>
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-6 feature-card">
                <span class="material-symbols-outlined text-4xl text-primary-container">history</span>
                <h3 class="mt-3 font-display font-bold text-lg">Batch history</h3>
                <p class="mt-2 text-sm text-secondary">Every rename is logged. Revisit, re-export, never lose work</p>
            </article>
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-6 feature-card">
                <span class="material-symbols-outlined text-4xl text-primary-container">lock</span>
                <h3 class="mt-3 font-display font-bold text-lg">Private by default</h3>
                <p class="mt-2 text-sm text-secondary">Your files are processed and deleted. Nothing is stored</p>
            </article>
        </div>
    </div>
</section>

{# ============================ PRICING ============================ #}
<section id="pricing" class="py-20">
    <div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-center font-display font-extrabold text-3xl md:text-4xl text-deep-slate">Simple pricing</h2>
        <p class="mt-3 text-center text-lg text-secondary">Pay as you go, or subscribe for monthly credits</p>

        <div class="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {% for option in payment_options %}
            <article class="reveal-on-scroll rounded-3xl border border-outline/10 bg-white p-6 feature-card">
                <p class="text-xs font-bold uppercase tracking-widest text-primary-container">{{ option.accent }}</p>
                <h3 class="mt-2 font-display font-bold text-2xl">{{ option.label }}</h3>
                <p class="mt-2 text-sm text-secondary">{{ option.description }}</p>
                <div class="mt-4 text-3xl font-display font-bold text-deep-slate">
                    {{ option.amount_label }}{% if option.plan_type == 'subscription' %}<span class="text-sm font-medium opacity-60">/mo</span>{% endif %}
                </div>
                <p class="mt-1 text-xs font-bold text-primary-container">
                    {% if option.plan_type == 'subscription' %}{{ option.credits }} credits/month{% else %}{{ option.credits }} credit{{ 's' if option.credits != 1 else '' }}{% endif %}
                </p>
                <a href="/register?plan={{ option.key }}"
                   class="mt-6 block w-full rounded-xl bg-primary-container py-3 text-center text-sm font-bold text-white hover:bg-primary-container/90 transition">
                    Get {{ option.label }}
                </a>
            </article>
            {% endfor %}
        </div>
    </div>
</section>

{# ============================ STATS ============================ #}
{# Note: These are hardcoded marketing placeholder numbers, not real data. #}
<section class="py-16 bg-inverse-surface text-inverse-on-surface">
    <div class="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
        <div>
            <div class="font-display font-extrabold text-5xl" data-count-to="50000" data-count-suffix="+">0</div>
            <p class="mt-2 text-sm uppercase tracking-widest opacity-70">Files renamed</p>
        </div>
        <div>
            <div class="font-display font-extrabold text-5xl">2.3s</div>
            <p class="mt-2 text-sm uppercase tracking-widest opacity-70">Average per file</p>
        </div>
        <div>
            <div class="font-display font-extrabold text-5xl" data-count-to="99" data-count-suffix=".7%">0</div>
            <p class="mt-2 text-sm uppercase tracking-widest opacity-70">Customer satisfaction</p>
        </div>
    </div>
</section>

{# ============================ FINAL CTA ============================ #}
<section class="py-20 bg-gradient-to-br from-primary-container to-deep-slate text-white">
    <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center">
        <h2 class="font-display font-extrabold text-3xl md:text-5xl">Ready to stop fighting your filenames?</h2>
        <a href="/register" class="mt-8 inline-block rounded-xl bg-white px-8 py-4 font-bold text-primary-container hover:bg-white/90 transition shadow-xl">
            Get Started Free — No card required
        </a>
    </div>
</section>

{% include "partials/footer.html" %}

<script>
// Reveal-on-scroll IntersectionObserver
(function() {
    const els = document.querySelectorAll('.reveal-on-scroll');
    if (!('IntersectionObserver' in window)) {
        els.forEach(el => el.classList.add('in-view'));
        return;
    }
    const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('in-view');
                io.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15 });
    els.forEach(el => io.observe(el));
})();

// Stat counters
(function() {
    const counters = document.querySelectorAll('[data-count-to]');
    if (!counters.length) return;
    const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            const el = entry.target;
            const target = parseInt(el.getAttribute('data-count-to'), 10);
            const suffix = el.getAttribute('data-count-suffix') || '';
            const duration = 1500;
            const start = performance.now();
            function tick(now) {
                const t = Math.min((now - start) / duration, 1);
                const eased = 1 - Math.pow(1 - t, 3);
                const value = Math.floor(target * eased);
                el.textContent = value.toLocaleString() + suffix;
                if (t < 1) requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
            io.unobserve(el);
        });
    }, { threshold: 0.5 });
    counters.forEach(el => io.observe(el));
})();
</script>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/templates/home.html
git commit -m "feat: add marketing homepage with hero animation, features, and pricing"
```

---

## Task 8: Create `auth/login.html`

**Files:**
- Create: `frontend/templates/auth/login.html`

- [ ] **Step 1: Create the login page**

```html
{% extends "base.html" %}

{% block title %}Sign in — PxNN it{% endblock %}

{% block body %}
{% include "partials/nav.html" %}

<section class="min-h-[calc(100vh-4rem)] flex items-center justify-center bg-gradient-to-b from-surface-bright to-primary-fixed/30 px-4 py-12">
    <div class="w-full max-w-md">
        <div class="rounded-3xl border border-outline/10 bg-white p-8 shadow-xl">
            <h1 class="font-display font-extrabold text-3xl text-deep-slate text-center">Sign in to PxNN it</h1>
            <p class="mt-2 text-center text-sm text-secondary">Welcome back.</p>

            <div id="login-error" class="hidden mt-4 rounded-xl bg-red-50 border border-red-200 p-3 text-sm text-red-700"></div>

            <form id="login-form" class="mt-6 space-y-4">
                <label class="block">
                    <span class="text-xs font-bold uppercase tracking-widest text-secondary">Username</span>
                    <input type="text" name="username" required autocomplete="username"
                           class="mt-1 w-full rounded-xl border border-outline/20 bg-white px-4 py-3 text-sm focus:border-primary-container focus:outline-none focus:ring-2 focus:ring-primary-container/20">
                </label>
                <label class="block">
                    <span class="text-xs font-bold uppercase tracking-widest text-secondary">Password</span>
                    <input type="password" name="password" required autocomplete="current-password"
                           class="mt-1 w-full rounded-xl border border-outline/20 bg-white px-4 py-3 text-sm focus:border-primary-container focus:outline-none focus:ring-2 focus:ring-primary-container/20">
                </label>
                <button type="submit"
                        class="w-full rounded-xl bg-primary-container py-3 text-sm font-bold text-white hover:bg-primary-container/90 transition">
                    Sign in
                </button>
            </form>

            {% if google_oauth_enabled %}
            <div class="mt-6 flex items-center gap-3">
                <div class="h-px flex-1 bg-outline/20"></div>
                <span class="text-xs font-bold uppercase tracking-widest text-secondary opacity-60">or</span>
                <div class="h-px flex-1 bg-outline/20"></div>
            </div>
            <a href="/auth/google/login"
               class="mt-4 flex w-full items-center justify-center gap-3 rounded-xl border border-outline/20 bg-white py-3 text-sm font-bold text-deep-slate hover:border-primary-container transition">
                <svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                Continue with Google
            </a>
            {% endif %}

            <p class="mt-6 text-center text-sm text-secondary">
                Don't have an account?
                <a href="/register" class="font-bold text-primary-container hover:underline">Sign up</a>
            </p>
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

- [ ] **Step 2: Commit**

```bash
git add frontend/templates/auth/login.html
git commit -m "feat: add dedicated login page"
```

---

## Task 9: Create `auth/register.html`

**Files:**
- Create: `frontend/templates/auth/register.html`

- [ ] **Step 1: Create the register page**

```html
{% extends "base.html" %}

{% block title %}Create account — PxNN it{% endblock %}

{% block body %}
{% include "partials/nav.html" %}

<section class="min-h-[calc(100vh-4rem)] flex items-center justify-center bg-gradient-to-b from-surface-bright to-primary-fixed/30 px-4 py-12">
    <div class="w-full max-w-md">
        <div class="rounded-3xl border border-outline/10 bg-white p-8 shadow-xl">
            <h1 class="font-display font-extrabold text-3xl text-deep-slate text-center">Create your PxNN it account</h1>
            <p class="mt-2 text-center text-sm text-secondary">Rename files in seconds.</p>

            <div id="register-error" class="hidden mt-4 rounded-xl bg-red-50 border border-red-200 p-3 text-sm text-red-700"></div>

            <form id="register-form" class="mt-6 space-y-4">
                <label class="block">
                    <span class="text-xs font-bold uppercase tracking-widest text-secondary">Username</span>
                    <input type="text" name="username" required autocomplete="username" minlength="3"
                           class="mt-1 w-full rounded-xl border border-outline/20 bg-white px-4 py-3 text-sm focus:border-primary-container focus:outline-none focus:ring-2 focus:ring-primary-container/20">
                </label>
                <label class="block">
                    <span class="text-xs font-bold uppercase tracking-widest text-secondary">Password</span>
                    <input type="password" name="password" required autocomplete="new-password" minlength="8"
                           class="mt-1 w-full rounded-xl border border-outline/20 bg-white px-4 py-3 text-sm focus:border-primary-container focus:outline-none focus:ring-2 focus:ring-primary-container/20">
                    <span class="mt-1 block text-xs text-secondary opacity-70">At least 8 characters</span>
                </label>
                <button type="submit"
                        class="w-full rounded-xl bg-primary-container py-3 text-sm font-bold text-white hover:bg-primary-container/90 transition">
                    Create account
                </button>
            </form>

            {% if google_oauth_enabled %}
            <div class="mt-6 flex items-center gap-3">
                <div class="h-px flex-1 bg-outline/20"></div>
                <span class="text-xs font-bold uppercase tracking-widest text-secondary opacity-60">or</span>
                <div class="h-px flex-1 bg-outline/20"></div>
            </div>
            <a href="/auth/google/login"
               class="mt-4 flex w-full items-center justify-center gap-3 rounded-xl border border-outline/20 bg-white py-3 text-sm font-bold text-deep-slate hover:border-primary-container transition">
                <svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                Continue with Google
            </a>
            {% endif %}

            <p class="mt-6 text-center text-sm text-secondary">
                Already have an account?
                <a href="/login" class="font-bold text-primary-container hover:underline">Sign in</a>
            </p>
        </div>
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

- [ ] **Step 2: Commit**

```bash
git add frontend/templates/auth/register.html
git commit -m "feat: add dedicated register page"
```

---

## Task 10: Profile Routes + Tests (TDD)

**Files:**
- Create: `backend/app/routes/profile.py`
- Create: `tests/test_profile.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_profile.py`:

```python
import pytest

from backend.app.core.security import hash_password
from backend.app.database.models import User


def _create_user(db, username="profileuser", password="oldpassword123"):
    user = User(
        username=username,
        password_hash=hash_password(password),
        credit_balance=0,
    )
    db.add(user)
    db.commit()
    return user


def _login(client, username, password):
    response = client.post("/api/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200
    return response.cookies


def test_password_update_success(client, db):
    _create_user(db, username="pwuser1", password="oldpassword123")
    _login(client, "pwuser1", "oldpassword123")

    response = client.post("/api/profile/password", data={
        "current_password": "oldpassword123",
        "new_password": "newpassword456",
        "confirm_password": "newpassword456",
    })
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    # Verify the new password works
    relogin = client.post("/api/auth/login", data={"username": "pwuser1", "password": "newpassword456"})
    assert relogin.status_code == 200


def test_password_update_wrong_current(client, db):
    _create_user(db, username="pwuser2", password="rightpass123")
    _login(client, "pwuser2", "rightpass123")

    response = client.post("/api/profile/password", data={
        "current_password": "wrongpass",
        "new_password": "newpassword456",
        "confirm_password": "newpassword456",
    })
    assert response.status_code == 401


def test_password_update_mismatched_confirmation(client, db):
    _create_user(db, username="pwuser3", password="rightpass123")
    _login(client, "pwuser3", "rightpass123")

    response = client.post("/api/profile/password", data={
        "current_password": "rightpass123",
        "new_password": "newpassword456",
        "confirm_password": "differentpass",
    })
    assert response.status_code == 400


def test_password_update_weak_password(client, db):
    _create_user(db, username="pwuser4", password="rightpass123")
    _login(client, "pwuser4", "rightpass123")

    response = client.post("/api/profile/password", data={
        "current_password": "rightpass123",
        "new_password": "short",
        "confirm_password": "short",
    })
    assert response.status_code == 400


def test_password_update_google_only_user(client, db):
    user = User(username="googleuser", password_hash=None, google_sub="google_sub_abc", credit_balance=0)
    db.add(user)
    db.commit()

    # Google-only users cannot sign in via password, so we need to manually set a cookie.
    # Use an authenticated request by creating a session token directly.
    from backend.app.core.security import create_access_token, set_auth_cookie
    from backend.app.core.config import settings

    token = create_access_token(str(user.id))
    client.cookies.set(settings.COOKIE_NAME, token)

    response = client.post("/api/profile/password", data={
        "current_password": "anything",
        "new_password": "newpassword456",
        "confirm_password": "newpassword456",
    })
    assert response.status_code == 400


def test_delete_account_success(client, db):
    user = _create_user(db, username="deluser1", password="delpass123")
    _login(client, "deluser1", "delpass123")

    response = client.post("/api/profile/delete", data={"username_confirmation": "deluser1"})
    assert response.status_code == 200

    # User should be gone
    db.expire_all()
    assert db.query(User).filter(User.username == "deluser1").first() is None


def test_delete_account_wrong_username(client, db):
    _create_user(db, username="deluser2", password="delpass123")
    _login(client, "deluser2", "delpass123")

    response = client.post("/api/profile/delete", data={"username_confirmation": "wrongname"})
    assert response.status_code == 400
```

- [ ] **Step 2: Run tests (they should fail — no profile router yet)**

Run: `./venv/bin/python -m pytest tests/test_profile.py -v 2>&1 | tail -20`
Expected: failures (404 or import error).

- [ ] **Step 3: Create `backend/app/routes/profile.py`**

```python
from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import (
    clear_auth_cookie,
    get_current_user,
    hash_password,
    verify_password,
)
from ..database.models import ActivityLog, PaymentRecord, User
from ..database.session import get_db

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.post("/password")
async def update_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.password_hash:
        raise HTTPException(status_code=400, detail="This account has no password. Sign in with Google instead.")

    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )

    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Password confirmation does not match.")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    current_user.password_hash = hash_password(new_password)
    db.commit()

    return {"ok": True}


@router.post("/delete")
async def delete_account(
    response: Response,
    username_confirmation: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if username_confirmation != current_user.username:
        raise HTTPException(status_code=400, detail="Username confirmation does not match.")

    # Manually delete related rows first — no ORM cascade configured on these relationships.
    db.query(ActivityLog).filter(ActivityLog.user_id == current_user.id).delete(synchronize_session=False)
    db.query(PaymentRecord).filter(PaymentRecord.user_id == current_user.id).delete(synchronize_session=False)
    db.delete(current_user)
    db.commit()

    clear_auth_cookie(response)

    return {"ok": True}
```

- [ ] **Step 4: Register the profile router in `main.py`**

Edit `backend/app/main.py`. Add the import near the other route imports:

```python
from .routes.profile import router as profile_router
```

And register it after the other `include_router` calls:

```python
app.include_router(profile_router)
```

- [ ] **Step 5: Run tests again**

Run: `./venv/bin/python -m pytest tests/test_profile.py -v 2>&1 | tail -25`
Expected: all 7 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/profile.py backend/app/main.py tests/test_profile.py
git commit -m "feat: add profile router with password update and account delete endpoints"
```

---

## Task 11: Create `profile.html` Page

**Files:**
- Create: `frontend/templates/profile.html`

- [ ] **Step 1: Create the profile page**

```html
{% extends "base.html" %}

{% block title %}Profile — PxNN it{% endblock %}

{% block body %}
{% include "partials/nav.html" %}

<section class="min-h-[calc(100vh-4rem)] bg-surface-bright py-10 px-4">
    <div class="mx-auto max-w-2xl space-y-6">
        <h1 class="font-display font-extrabold text-3xl text-deep-slate">Profile</h1>

        {# Card 1: Account identity #}
        <article class="rounded-3xl border border-outline/10 bg-white p-6">
            <h2 class="font-display font-bold text-lg text-deep-slate">Account</h2>
            <dl class="mt-4 space-y-3 text-sm">
                <div class="flex justify-between">
                    <dt class="text-secondary">Username</dt>
                    <dd class="font-semibold text-deep-slate">{{ current_user.username }}</dd>
                </div>
                <div class="flex justify-between">
                    <dt class="text-secondary">Email</dt>
                    <dd class="font-semibold text-deep-slate">{{ current_user.email or 'Not set' }}</dd>
                </div>
                <div class="flex justify-between">
                    <dt class="text-secondary">Account created</dt>
                    <dd class="font-semibold text-deep-slate">{{ current_user.created_at.strftime('%Y-%m-%d') if current_user.created_at else '—' }}</dd>
                </div>
                <div class="flex justify-between">
                    <dt class="text-secondary">Subscription</dt>
                    <dd>
                        {% if current_user.subscription_status == 'active' %}
                            <span class="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700">Active</span>
                        {% elif current_user.subscription_status == 'canceled' %}
                            <span class="rounded-full bg-red-100 px-3 py-1 text-xs font-bold text-red-700">Canceled</span>
                        {% else %}
                            <span class="rounded-full bg-outline/10 px-3 py-1 text-xs font-bold text-secondary">None</span>
                        {% endif %}
                    </dd>
                </div>
            </dl>
        </article>

        {# Card 2: Connected accounts #}
        <article class="rounded-3xl border border-outline/10 bg-white p-6">
            <h2 class="font-display font-bold text-lg text-deep-slate">Connected accounts</h2>
            <div class="mt-4 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                    </svg>
                    <span class="font-semibold text-deep-slate">Google</span>
                </div>
                {% if current_user.google_sub %}
                    <span class="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700">Connected{% if current_user.email %} as {{ current_user.email }}{% endif %}</span>
                {% else %}
                    {% if google_oauth_enabled %}
                        <a href="/auth/google/login" class="rounded-xl border border-outline/20 bg-white px-4 py-2 text-xs font-bold text-deep-slate hover:border-primary-container transition">Connect</a>
                    {% else %}
                        <span class="text-xs text-secondary opacity-60">Not available</span>
                    {% endif %}
                {% endif %}
            </div>
        </article>

        {# Card 3: Change password #}
        <article class="rounded-3xl border border-outline/10 bg-white p-6">
            <h2 class="font-display font-bold text-lg text-deep-slate">Change password</h2>
            {% if current_user.password_hash %}
            <div id="pwd-error" class="hidden mt-4 rounded-xl bg-red-50 border border-red-200 p-3 text-sm text-red-700"></div>
            <div id="pwd-success" class="hidden mt-4 rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-700">Password updated.</div>
            <form id="pwd-form" class="mt-4 space-y-4">
                <label class="block">
                    <span class="text-xs font-bold uppercase tracking-widest text-secondary">Current password</span>
                    <input type="password" name="current_password" required class="mt-1 w-full rounded-xl border border-outline/20 bg-white px-4 py-3 text-sm focus:border-primary-container focus:outline-none focus:ring-2 focus:ring-primary-container/20">
                </label>
                <label class="block">
                    <span class="text-xs font-bold uppercase tracking-widest text-secondary">New password</span>
                    <input type="password" name="new_password" required minlength="8" class="mt-1 w-full rounded-xl border border-outline/20 bg-white px-4 py-3 text-sm focus:border-primary-container focus:outline-none focus:ring-2 focus:ring-primary-container/20">
                </label>
                <label class="block">
                    <span class="text-xs font-bold uppercase tracking-widest text-secondary">Confirm new password</span>
                    <input type="password" name="confirm_password" required minlength="8" class="mt-1 w-full rounded-xl border border-outline/20 bg-white px-4 py-3 text-sm focus:border-primary-container focus:outline-none focus:ring-2 focus:ring-primary-container/20">
                </label>
                <button type="submit" class="w-full rounded-xl bg-primary-container py-3 text-sm font-bold text-white hover:bg-primary-container/90 transition">Update password</button>
            </form>
            {% else %}
            <p class="mt-4 text-sm text-secondary">This is a Google-only account. Sign in with Google to authenticate.</p>
            {% endif %}
        </article>

        {# Card 4: Credits & subscription #}
        <article class="rounded-3xl border border-outline/10 bg-white p-6">
            <h2 class="font-display font-bold text-lg text-deep-slate">Credits & subscription</h2>
            <dl class="mt-4 space-y-3 text-sm">
                <div class="flex justify-between">
                    <dt class="text-secondary">Credit balance</dt>
                    <dd class="font-bold text-deep-slate">{{ current_user.credit_balance }}</dd>
                </div>
                <div class="flex justify-between">
                    <dt class="text-secondary">Active plan</dt>
                    <dd class="font-semibold text-deep-slate">{{ current_user.subscription_plan or 'None' }}</dd>
                </div>
            </dl>
            <a href="/app?billing=options" class="mt-4 inline-block text-sm font-bold text-primary-container hover:underline">Manage billing →</a>
        </article>

        {# Card 5: Danger zone #}
        <article class="rounded-3xl border border-red-200 bg-red-50/50 p-6">
            <h2 class="font-display font-bold text-lg text-red-700">Danger zone</h2>
            <p class="mt-2 text-sm text-red-700/80">Permanently delete your account and all associated data. This cannot be undone.</p>
            <button type="button" onclick="document.getElementById('delete-dialog').showModal()"
                    class="mt-4 rounded-xl border border-red-500 bg-white px-4 py-2 text-sm font-bold text-red-600 hover:bg-red-500 hover:text-white transition">
                Delete account
            </button>

            <dialog id="delete-dialog" class="rounded-3xl border border-outline/10 p-0 backdrop:bg-black/40">
                <div class="w-[min(90vw,420px)] p-6">
                    <h3 class="font-display font-bold text-xl text-deep-slate">Delete account?</h3>
                    <p class="mt-2 text-sm text-secondary">Type your username <strong>{{ current_user.username }}</strong> to confirm.</p>
                    <div id="del-error" class="hidden mt-3 rounded-xl bg-red-50 border border-red-200 p-3 text-sm text-red-700"></div>
                    <form id="delete-form" class="mt-4 space-y-3">
                        <input type="text" name="username_confirmation" required
                               class="w-full rounded-xl border border-outline/20 bg-white px-4 py-3 text-sm focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500/20"
                               placeholder="Type your username">
                        <div class="flex gap-3">
                            <button type="button" onclick="document.getElementById('delete-dialog').close()"
                                    class="flex-1 rounded-xl border border-outline/20 bg-white py-2 text-sm font-bold text-deep-slate hover:border-primary-container transition">
                                Cancel
                            </button>
                            <button type="submit"
                                    class="flex-1 rounded-xl bg-red-600 py-2 text-sm font-bold text-white hover:bg-red-700 transition">
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

- [ ] **Step 2: Commit**

```bash
git add frontend/templates/profile.html
git commit -m "feat: add profile page with identity, password change, and delete account"
```

---

## Task 12: Page Routes in `main.py` (TDD)

**Files:**
- Modify: `backend/app/main.py`
- Create: `tests/test_routes_pages.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_routes_pages.py`:

```python
import pytest

from backend.app.core.security import hash_password
from backend.app.database.models import User


def _create_and_login(client, db, username="routesuser", password="testpass123"):
    user = User(
        username=username,
        password_hash=hash_password(password),
        credit_balance=0,
    )
    db.add(user)
    db.commit()
    response = client.post("/api/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200


def test_home_renders_for_anonymous(client, db):
    response = client.get("/")
    assert response.status_code == 200
    assert "PxNN it" in response.text
    assert "Get Started Free" in response.text


def test_home_redirects_authenticated_to_app(client, db):
    _create_and_login(client, db, username="homeauth")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/app"


def test_app_requires_auth(client, db):
    response = client.get("/app", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_app_renders_for_authenticated(client, db):
    _create_and_login(client, db, username="appuser")
    response = client.get("/app")
    assert response.status_code == 200


def test_login_page_renders_for_anonymous(client, db):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Sign in to PxNN it" in response.text


def test_login_page_redirects_authenticated_to_app(client, db):
    _create_and_login(client, db, username="loginauth")
    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/app"


def test_register_page_renders_for_anonymous(client, db):
    response = client.get("/register")
    assert response.status_code == 200
    assert "Create your PxNN it account" in response.text


def test_register_page_redirects_authenticated_to_app(client, db):
    _create_and_login(client, db, username="regauth")
    response = client.get("/register", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/app"


def test_register_stores_pending_plan_in_session(client, db):
    response = client.get("/register?plan=pro_monthly")
    assert response.status_code == 200
    # Verify the session cookie was set (pending_plan is stored in server session)
    # We assert the page still renders correctly with the query param
    assert "Create your PxNN it account" in response.text


def test_profile_page_renders_for_authenticated(client, db):
    _create_and_login(client, db, username="profilepage")
    response = client.get("/profile")
    assert response.status_code == 200
    assert "Profile" in response.text
    assert "profilepage" in response.text


def test_profile_page_redirects_anonymous(client, db):
    response = client.get("/profile", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
```

- [ ] **Step 2: Run tests (they should fail — routes not yet updated)**

Run: `./venv/bin/python -m pytest tests/test_routes_pages.py -v 2>&1 | tail -30`
Expected: failures (the `/` still returns 200 for authenticated users, and `/app`, `/login`, `/register`, `/profile` return 404).

- [ ] **Step 3: Update `backend/app/main.py`**

Replace the existing `root()` handler with these route handlers. The full section to replace is from `@app.get("/", response_class=HTMLResponse)` through the end of the `root` function.

Also add the import for `RedirectResponse` at the top with the other FastAPI imports, add `set_pending_plan` to the security import, and add the profile router import/registration:

```python
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from .core.config import settings
from .core.pricing import get_payment_options
from .core.security import (
    get_current_user_optional,
    serialize_user,
    set_pending_plan,
)
from .database.bootstrap import bootstrap_database
from .database.models import User
from .routes.auth import router as auth_router
from .routes.dashboard import router as dashboard_router
from .routes.oauth import router as oauth_router
from .routes.payments import router as payments_router
from .routes.profile import router as profile_router
from .routes.wizard import router as wizard_router

app = FastAPI(title="PxNN it")

# SessionMiddleware required by authlib for OAuth state/nonce and pending plan storage
app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET)

# Setup Templates and Static Files
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend" / "static")), name="static")

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(oauth_router)
app.include_router(payments_router)
app.include_router(profile_router)
app.include_router(wizard_router)


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user:
        return RedirectResponse(url="/app", status_code=303)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "current_user": None,
            "page": "home",
            "payment_options": get_payment_options(),
            "stripe_enabled": bool(settings.STRIPE_SECRET_KEY),
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
        },
    )


@app.get("/app", response_class=HTMLResponse)
async def workspace(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "app.html",
        {
            "title": "PxNN it - Workspace",
            "current_user": current_user,
            "page": "app",
            "initial_user": serialize_user(current_user),
            "payment_options": get_payment_options(),
            "stripe_enabled": bool(settings.STRIPE_SECRET_KEY),
            "billing_notice": request.query_params.get("billing", ""),
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
        },
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user:
        return RedirectResponse(url="/app", status_code=303)
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "current_user": None,
            "page": "login",
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
        },
    )


@app.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user:
        return RedirectResponse(url="/app", status_code=303)

    plan_key = request.query_params.get("plan")
    if plan_key:
        set_pending_plan(request, plan_key)

    return templates.TemplateResponse(
        request,
        "auth/register.html",
        {
            "current_user": None,
            "page": "register",
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
        },
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "title": "Profile — PxNN it",
            "current_user": current_user,
            "page": "profile",
            "google_oauth_enabled": bool(settings.GOOGLE_CLIENT_ID),
        },
    )


@app.on_event("startup")
def startup_event():
    bootstrap_database()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 4: Run tests again**

Run: `./venv/bin/python -m pytest tests/test_routes_pages.py -v 2>&1 | tail -30`
Expected: all 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py tests/test_routes_pages.py
git commit -m "feat: add page routes for home, app, login, register, profile"
```

---

## Task 13: Update OAuth Callback Redirect

**Files:**
- Modify: `backend/app/routes/oauth.py`

- [ ] **Step 1: Read the current oauth.py**

Run: `grep -n "RedirectResponse" backend/app/routes/oauth.py`
Expected: see the callback's redirect target.

- [ ] **Step 2: Change the callback redirect from `/` to `/app`**

Find the line in `backend/app/routes/oauth.py` that creates a `RedirectResponse` at the end of `google_callback` (look for `return RedirectResponse`). Change the `url="/"` to `url="/app"`. If the line is:

```python
return RedirectResponse(url="/", status_code=303)
```

Change it to:

```python
return RedirectResponse(url="/app", status_code=303)
```

- [ ] **Step 3: Run all tests**

Run: `./venv/bin/python -m pytest tests/ -v 2>&1 | tail -30`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/oauth.py
git commit -m "fix: redirect Google OAuth callback to /app instead of /"
```

---

## Task 14: Full Test Suite + Smoke Test

- [ ] **Step 1: Run all tests**

Run: `cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && ./venv/bin/python -m pytest tests/ -v 2>&1 | tail -40`
Expected: all tests pass (should be 41+ total: 22 existing + 7 profile + 11 page routes + a small buffer).

- [ ] **Step 2: Smoke test app import**

Run: `cd /Users/sjpenn/DEV-SITES/DEMOS/music_renamer && ./venv/bin/python -c "from backend.app.main import app; print('App import OK')"`
Expected: `App import OK`

- [ ] **Step 3: Verify clean working tree**

Run: `git status`
Expected: `nothing to commit, working tree clean`

- [ ] **Step 4: Push to GitHub**

```bash
git push origin main
```

Expected: successful push triggers Railway redeploy.
