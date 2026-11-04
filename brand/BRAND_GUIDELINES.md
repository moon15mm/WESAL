# وِصال | WESAL — Brand Guidelines

**Tagline:** كل السوق في اتصال واحد. — *One Market. Connected.*

## 1. Concept
The mark is a rounded square containing three connected nodes — **store**, **sales
representative** and **supplier** — joined by a "W"-shaped path (WESAL) and an arc. The
lower, larger node is the store: the party every connection ultimately serves. The mark is
original geometry (64-unit grid, `brand/tools/build_brand.py`); wordmarks are set in IBM Plex
Sans Arabic Bold and Inter Bold and converted to outlines, so the SVGs render identically
everywhere without fonts installed.

## 2. Files
| Use | File |
|---|---|
| Primary lockup (AR + EN) | `svg/wesal-logo-primary.svg`, `png/wesal-logo-primary@{1,2,4}x.png` |
| Primary + tagline | `svg/wesal-logo-primary-tagline.svg` |
| Arabic only / English only | `svg/wesal-logo-ar.svg`, `svg/wesal-logo-en.svg` |
| Monochrome (navy / white) | `svg/wesal-logo-mono.svg`, `svg/wesal-logo-mono-white.svg` |
| On dark / on light background | `svg/wesal-logo-on-dark.svg`, `svg/wesal-logo-on-light.svg` |
| Symbol only | `svg/wesal-mark.svg` |
| App icon | `svg/wesal-app-icon.svg`, `png/app-icon-{16…1024}.png` |
| Favicon | `svg/wesal-favicon.svg`, `favicon.ico` (16/32/48), `png/favicon-*.png` |
| Splash screen | `svg/wesal-splash.svg`, `png/splash-1242x2688.png` |
| Social preview | `svg/wesal-og-image.svg`, `png/og-image.png` (1200×630) |
| Print (vector PDF) | `print/wesal-logo-primary.pdf`, `print/wesal-logo-mono.pdf`, `print/wesal-logo-primary-tagline.pdf` |

Regenerate: `backend/.venv/bin/python brand/tools/build_brand.py` then `cd frontend && node ../brand/tools/render.mjs`.

## 3. Colour
| Token | Hex | Use |
|---|---|---|
| Navy (primary) | `#102B46` | Mark background, headings, dark surfaces |
| Teal (secondary) | `#20B99A` | Accent, primary buttons, "WESAL" wordmark |
| Mint (interaction) | `#55D6B0` | Hover/focus, nodes, highlights |
| Page | `#F5F8FA` | App background |
| Text | `#172B3A` | Body text |
| Secondary text | `#718096` | Captions, hints |
| Success | `#16A36A` | Confirmations |
| Warning | `#E5A13B` | Pending, attention |
| Error | `#D84B4B` | Errors, destructive actions |

Accessibility: navy on white = 14.6:1, text on page = 13.9:1 (AAA). Teal on white is 2.6:1 —
use it for large text, icons and fills, never for body text; teal buttons use white bold text
at ≥16px or navy text. Design tokens live in `frontend/src/app/globals.css` (`@theme`).

## 4. Typography
* Arabic & Urdu UI: **IBM Plex Sans Arabic** (400/500/600/700); Urdu documents: Noto Nastaliq Urdu.
* Latin UI: **Inter**; Hindi: Noto Sans Devanagari.
* Numbers in tables use tabular figures; prices always show `SAR`/`ر.س` per locale.

## 5. Clear space & minimum size
* Clear space on all sides = ½ the height of the mark.
* Minimum size: mark 16 px (favicon) / 24 px in UI; full lockup 120 px wide on screen, 30 mm in print.

## 6. Do / Don't
* ✅ Use the supplied files; place the colour logo on white/page backgrounds and the on-dark version on navy.
* ✅ In RTL layouts the lockup is not mirrored — the mark always sits at the start of the reading direction of the surrounding layout only when used as an app header (the header component handles this).
* ❌ Don't recolour the nodes individually, stretch, rotate, add shadows/outlines, re-type the wordmark in another font, or place the colour logo on busy photos.
* ❌ Don't use the mark to imply certification, licensing or government endorsement.

## 7. Voice
Clear, respectful, practical. Arabic first; avoid jargon; state facts (e.g. "the supplier delivers;
you pay the supplier directly") rather than promises.
