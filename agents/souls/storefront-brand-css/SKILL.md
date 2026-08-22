---
name: Storefront Brand CSS
description: >
  Use whenever a task touches the Fourthwall storefront appearance: theme setup,
  custom code injection, landing tweaks, or verifying brand rendering. Contains the
  canonical paste-ready <style> override block enforcing SWE Drip terminal aesthetic.
metadata:
  sourceKind: github
  owner: kcbdev
  repo: SWE-DRIP
---

# Storefront Brand CSS — Fourthwall Custom Code

Paste-ready Custom Code section for the Fourthwall storefront. Injected as an HTML `<style>` block; overrides the active theme (Brutal) via `:root` variable remap + high-specificity `!important` element coverage, because Brutal DOM classnames are not pinned.

Canonical file in repo: `storefront/custom-code.html` (commit-tagged). Apply via Fourthwall Dashboard → Online store → Custom code.

## Brand constants (founder-owned)

- Background `#0D0D0D` void black
- Primary/accent `#00FF41` terminal green
- Error orange `#FF6B35` (badges, sale strike)
- Text `#FFFFFF`
- Font JetBrains Mono Bold (fallback Fira Code → Courier New)

## Anti-patterns enforced by this block

No gradients · no shadows · no text-shadows · no rounded pill corners (`border-radius: 0`) · no pastels · no decorative imagery.

## The block

```html
<html>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,400;0,700;1,400&display=swap');

  :root {
    --color-background: #0D0D0D !important;
    --color-primary: #00FF41 !important;
    --color-text: #FFFFFF !important;
    --sd-black:#0D0D0D; --sd-green:#00FF41; --sd-orange:#FF6B35;
    --sd-surface:#111111; --sd-border:#222222;
    --font-display:'JetBrains Mono','Fira Code','Courier New',monospace !important;
  }
  html, body { background:#0D0D0D !important; color:#FFF !important; font-family:var(--font-display) !important; }
  h1,h2,h3,h4,h5,h6 { font-family:var(--font-display) !important; color:#FFF !important; font-weight:700 !important; }
  p,span,div,li,label,td,th,small { font-family:var(--font-display),monospace !important; }
  ::selection { background:#00FF41 !important; color:#0D0D0D !important; }

  a, a * { color:#00FF41 !important; text-decoration:none !important; }
  a:hover, a:hover * { color:#FFF !important; text-decoration:underline !important; }

  button,.button,[class*="button"],[class*="Button"],input[type="submit"] {
    background:transparent !important; color:#00FF41 !important;
    border:2px solid #00FF41 !important; border-radius:0 !important;
    font-family:var(--font-display) !important; font-weight:700 !important;
    text-transform:uppercase !important; letter-spacing:.06em !important;
    box-shadow:none !important; background-image:none !important;
  }
  button:hover,[class*="button"]:hover,input[type="submit"]:hover { background:#00FF41 !important; color:#0D0D0D !important; }
  [class*="add-to-cart"],[class*="AddToCart"],form button[type="submit"] { background:#00FF41 !important; color:#0D0D0D !important; }
  [class*="add-to-cart"]:hover,form button[type="submit"]:hover { background:#0D0D0D !important; color:#00FF41 !important; }

  input,textarea,select { background:#0A0A0A !important; color:#FFF !important; border:1px solid #222 !important; border-radius:0 !important; font-family:var(--font-display) !important; }
  input:focus,textarea:focus,select:focus { outline:none !important; border-color:#00FF41 !important; }

  header,nav,footer,[class*="header"],[class*="Header"],[class*="footer"],[class*="Footer"] {
    background:#0D0D0D !important; background-image:none !important; box-shadow:none !important; border-color:#222 !important;
  }
  [class*="product-card"],[class*="ProductCard"],[class*="card"],[class*="Card"] {
    background:#0A0A0A !important; border:1px solid #222 !important; border-radius:0 !important; box-shadow:none !important;
  }
  [class*="product-card"]:hover,[class*="ProductCard"]:hover { border-color:#00FF41 !important; }
  [class*="price"],[class*="Price"] { color:#00FF41 !important; font-family:var(--font-display) !important; }
  s,del { color:#FF6B35 !important; }
  [class*="badge"],[class*="Badge"] { background:#FF6B35 !important; color:#0D0D0D !important; border-radius:0 !important; font-family:var(--font-display) !important; }

  *,*::before,*::after { background-image:none !important; box-shadow:none !important; text-shadow:none !important; }
  h1::after { content:"▌" !important; color:#00FF41 !important; animation:sdblink 1.1s steps(1) infinite !important; }
  @keyframes sdblink { 50%{opacity:0} }
</style>
</html>
```

## Verification after applying

Open the public storefront and confirm:

1. Page background is void black `#0D0D0D`, not theme default.
2. Links/buttons render terminal green; primary CTA fills green with black text on hover-invert.
3. All type renders JetBrains Mono (DevTools computed font-family).
4. No gradients or drop shadows anywhere (computed styles check).
5. Blinking block cursor visible after the H1 headline.

If any element resists the override, capture its selector and append a targeted rule to `storefront/custom-code.html` in the repo — do not patch inline in the dashboard without committing the same change here first.
