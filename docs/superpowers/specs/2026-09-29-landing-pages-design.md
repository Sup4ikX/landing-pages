# Design: Landing page generator (portfolio sub-project 1)

Date: 2026-09-29
Status: awaiting author review

## Context

Portfolio for a first freelance offer to local businesses in Moscow. Six artifacts
total across three sub-projects (2 landing pages, 2 Telegram bots, 2 videos), one
per niche: an auto service and a cafe. This spec covers sub-project 1 only: two
landing pages produced by one generator, shown to clients as GitHub Pages links.

The generator IS the product story: "a template plus a config produces a site in
~40 minutes", not "I hand-craft pages".

## Goal

One command, `python3 generate.py`, produces two static, mobile-ready landing
pages into `dist/` from two JSON configs and HTML templates, deployable to
GitHub Pages as permanent links.

## Requirements

### Functional

- F1. Two sites generated from configs: `sites/auto.json` (auto service),
  `sites/cafe.json` (cafe). Same block set, different content and skin.
- F2. Seven blocks, config defines order: `hero`, `services`, `prices`,
  `reviews`, `gallery`, `map`, `contact`.
- F3. Two theme skins over one shared `base.css`: `auto` (graphite + signal
  orange, dense type), `cafe` (cream + warm coffee/terracotta, airy).
- F4. Form (fields: name, phone, comment) submit opens a WhatsApp deep link
  `https://wa.me/<phone>?text=<urlencoded message built from the three fields>`
  — no backend, no fake "sent" confirmation. Config key `submit.type` =
  `messenger` for this sub-project; value `bot` is reserved for sub-project 2
  (form opens a Telegram bot chat with `?start=landing_auto`).
- F5. Buttons: `tel:` link and WhatsApp link — both click-tested.
- F6. Every page: `lang="ru"`, per-site `seo.title` and `seo.description`.
- F7. All images downloaded into the repo (Pexels, free license), no hotlinks.
- F8. Maps: Yandex Maps embed in `map` block plus plain-text address.

### Non-functional

- N1. Generator uses Python standard library only (`json`, `string.Template`,
  `pathlib`, `shutil`). No `pip install`, no `package.json`.
- N2. Responsive down to 375px viewport, no horizontal scroll.
- N3. Generator fails loudly: missing required field for a rendered block exits
  non-zero with `sites/<id>.json: отсутствует поле <name>`. No output page with
  unsubstituted placeholders may be shipped.
- N4. `dist/` is build output: never hand-edited, not committed to git.

## Content (fixed, fictional, Moscow)

**Auto — `auto.json`**

- name: `АвтоПрофи`
- tagline: `ТО и ремонт в Москве без лишнего ожидания`
- address: `Москва, ул. Электрозаводская, 21к2`
- hours: `пн–сб 9:00–20:00, вс — выходной`
- map: lat `55.7746`, lon `37.7074`
- seo.title: `АвтоПрофи — ТО и ремонт автомобилей в Москве`
- services: замена масла и фильтров; диагностика подвески; ремонт тормозов;
  шиномонтаж; компьютерная диагностика
- prices: Замена масла — от 1 200 ₽; ТО-1 — от 4 500 ₽; Диагностика
  подвески — 800 ₽; Ремонт тормозов — от 2 500 ₽; Шиномонтаж (4 колеса) —
  от 1 600 ₽
- reviews: 3 fictional reviews, rating out of 5
- gallery: 4 local photos of service/workshop from Pexels

**Cafe — `cafe.json`**

- name: `Тёплый хлеб`
- tagline: `Пекарня-кофейня на Пятницкой`
- address: `Москва, ул. Пятницкая, 14`
- hours: `ежедневно 8:00–22:00`
- map: lat `55.7410`, lon `37.6290`
- seo.title: `Тёплый хлеб — пекарня-кофейня в Москве`
- prices: Круассан — 190 ₽; Хлеб на закваске — 320 ₽; Капучино — 260 ₽;
  Раф — 320 ₽; Сырники со сметаной — 390 ₽
- reviews: 3 fictional reviews, rating out of 5
- gallery: 4 local photos of pastries/interior from Pexels

**Phone (both configs):** the real phone number of the portfolio author, entered
at implementation time — personal data deliberately not written into this spec.
The demo displays and submits to the same number: the author plays "the
business" during a client demo; on sale the client swaps one config field.

## Config schema (`sites/<id>.json`)

```json
{
  "id": "auto",                       // output dir name, must match filename
  "theme": "auto",                    // skin: "auto" | "cafe"
  "blocks": ["hero", "services", "prices", "reviews", "gallery", "map", "contact"],
  "name": "...", "tagline": "...",
  "phone": "+7...",                   // author's real number (see above)
  "address": "...", "hours": "...",
  "map": { "lat": 55.7746, "lon": 37.7074 },
  "seo": { "title": "...", "description": "..." },
  "services": [ { "title": "...", "text": "..." } ],
  "prices":   [ { "name": "...", "price": "от 1 200 ₽" } ],
  "reviews":  [ { "author": "...", "text": "...", "rating": 5 } ],
  "gallery":  [ "assets/auto/1.jpg", "..." ],
  "submit":   { "type": "messenger" }
}
```

Required per rendered block: `hero` → name, tagline, phone; `services` →
services (≥1); `prices` → prices (≥1); `reviews` → reviews (≥3); `gallery` →
gallery (≥4, each path must exist); `map` → map, address; `contact` → phone,
submit. Top-level always required: id, theme, blocks, seo. A block listed in
`blocks` but not rendered from a partial that exists is a hard error; a partial
present but absent from `blocks` is simply skipped.

## Architecture

```
~/Work/landing-pages/
├── generate.py            # generator, stdlib only
├── sites/
│   ├── auto.json
│   └── cafe.json
├── template/
│   ├── layout.html        # html shell: head, header, footer
│   └── blocks/            # one partial per block, ${field} placeholders
├── theme/
│   ├── base.css           # grid, responsive, shared components
│   ├── auto.css           # skin
│   └── cafe.css           # skin
├── assets/
│   ├── auto/*.jpg         # Pexels photos, committed
│   └── cafe/*.jpg
├── dist/                  # build output (gitignored)
│   ├── auto/  {index.html, style.css, assets/}
│   └── cafe/
├── docs/superpowers/specs/  # this document
└── .github/workflows/deploy.yml
```

Generator flow per site: read JSON → validate required fields for the blocks in
`blocks` order → substitute each partial via `string.Template.substitute`
(strict: KeyError on missing field → friendly error, exit 1) → assemble into
`layout.html` → copy `base.css` + skin and referenced assets → write `dist/<id>/`.
Run for both configs in one invocation.

## Deploy

GitHub Actions workflow on push to `main`: checkout, `python3 generate.py`,
upload `dist/` as Pages artifact, deploy. Pages URLs:
`https://<owner>.github.io/landing-pages/auto/` and `.../cafe/`.

## Acceptance criteria

1. `python3 generate.py` exits 0; `dist/auto/index.html` and
   `dist/cafe/index.html` exist.
2. `grep -r '\$' dist/` finds no unsubstituted placeholder.
3. Negative path: delete `phone` from `auto.json` → exit code != 0 and stderr
   contains `auto.json` and `phone`; no partial output written.
4. Playwright at 375px and 1280px: no horizontal scroll on either page, every
   `<img>` returns 200, zero console errors.
5. Click test: form submit navigates to a messenger URL containing the typed
   name/phone; `tel:` button contains the config phone.
6. Both GitHub Pages URLs open after deploy.
7. Grep of each generated `<title>` matches the config `seo.title`.

## Out of scope

- Telegram bot integration (only the `submit.type: "bot"` value reserved),
  CMS, backend, real email delivery, analytics, SEO promotion, i18n,
  deployment to any host other than GitHub Pages.
