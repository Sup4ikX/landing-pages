# Landing Pages Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command generates two static landing pages (auto service, cafe) from JSON configs, deployable as GitHub Pages links.

**Architecture:** A stdlib-only Python generator reads `sites/*.json`, strictly validates them, substitutes fields into HTML partials via `string.Template`, and writes self-contained sites (`index.html` + merged `style.css` + `script.js` + local images) into `dist/`. GitHub Actions rebuilds `dist/` on push and publishes it to Pages; `dist/` itself is never committed.

**Tech Stack:** Python 3.14 stdlib (`json`, `re`, `html`, `pathlib`, `shutil`, `string`, `sys`, `unittest`), plain HTML/CSS (no framework, no external fonts), `playwright-cli` for browser verification, `gh` + GitHub Actions for deploy.

**Spec:** `docs/superpowers/specs/2026-09-29-landing-pages-design.md`

## Global Constraints

- Python standard library only — no `pip install`, no `package.json` (spec N1).
- Generator failure format: stderr `sites/<id>.json: отсутствует поле <name>`, exit code != 0; never write output when validation fails (spec N3).
- Zero `$` placeholders left in any file under `dist/` (spec acceptance 2).
- `dist/` is build output: never hand-edit, never commit; `.gitignore` covers it (spec N4).
- Pages must not scroll horizontally at 375px width (spec N2).
- All images committed locally under `assets/` — no hotlinks (spec F7). All 8 URLs below returned HTTP 200 `image/jpeg` on 2026-09-29; licenses are CC0/public-domain (StockSnap, WordPress Photo Directory, Flickr via Openverse).
- `lang="ru"`, per-site `<title>`/`description` from `seo` config (spec F6).
- Content (names, prices, addresses, reviews) is fixed by the spec Content section — do not invent new copy.
- Phone: real number of the portfolio author, obtained by asking the user (spec: PII deliberately absent from the spec — ask, never invent).
- Host: GitHub Pages only (spec). GitHub account: `Sup4ikX` (gh CLI already authenticated).

## Review Focus

Spec-implied failure modes no single task naturally covers; each has a pinning test in the owning task:

1. Phone formats `+7 ...`, `8 (900)...`, bare 10 digits must all normalize to 11 digits before `wa.me`/`tel:` links — `test_digits_*` in Task 1.
2. Config values containing `&`, `"`, `<` must be HTML-escaped, not break markup — `test_context_escapes_html` in Task 3.
3. Cyrillic must survive generation as UTF-8 (`АвтоПрофи`, `lang="ru"`) — `test_cyrillic_utf8` in Task 5.
4. Re-running the generator must remove stale files from previous builds — `test_stale_files_removed` in Task 5.
5. `blocks` order in config controls section order in output — `test_assemble_block_order` in Task 3.

## File Structure

| File | Responsibility |
|---|---|
| `generate.py` | Everything generation: validation, rendering, build, CLI |
| `sites/auto.json`, `sites/cafe.json` | Content configs (the only file a "third site" needs) |
| `template/layout.html` | HTML shell: head, header, `${blocks}` slot, footer |
| `template/blocks/*.html` (7) | One section wrapper per block, `${items}` slots where needed |
| `template/items/*.html` (4) | Repeated item markup: service, price, review, photo |
| `template/script.js` | Static form handler (not templated — full JS freedom) |
| `theme/base.css` | Grid, responsive layout, components (uses CSS vars) |
| `theme/auto.css`, `theme/cafe.css` | Skins: only CSS custom properties |
| `assets/{auto,cafe}/1..4.jpg` | Committed gallery photos |
| `tests/test_generate.py` | Validator + digits unit tests (also exports `make_cfg` fixture) |
| `tests/test_render.py` | Escaping, block order, stars, submit links |
| `tests/test_styles.py` | Skin variable contract |
| `tests/test_build.py` | End-to-end CLI: outputs, no-`$`, negative path, stale cleanup |
| `.github/workflows/deploy.yml` | Actions: generate + publish `dist/` |
| `dist/` | Build output (gitignored) |

Tasks build in dependency order: validator → configs/assets → render → styles → CLI → CI → browser verification.

---

### Task 1: Scaffold repo + config validator

**Files:**
- Create: `.gitignore`, `generate.py`, `tests/test_generate.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces (later tasks depend on these exact names):
  - `generate.ConfigError(Exception)` — message format `sites/<id>.json: <problem>`
  - `generate.digits(phone: str) -> str` — normalized 11-digit phone `7XXXXXXXXXX`
  - `generate.validate(cfg: dict, path: str, root: pathlib.Path) -> None` — raises `ConfigError`
  - `generate.load_site(path) -> dict` — reads JSON, validates, returns config; `root = Path(path).parent.parent`
  - `tests.test_generate.make_cfg(**overrides) -> dict` — valid fixture config

- [ ] **Step 1: Environment and repo init**

```bash
cd ~/Work/landing-pages
python3 --version    # expect 3.14.x
git init -b main
git config user.name; git config user.email   # if either empty: git config user.email "Sup4ikX@users.noreply.github.com" && git config user.name "Sup4ikX" (local repo only)
```

- [ ] **Step 2: Write `.gitignore`**

```
dist/
__pycache__/
*.pyc
.playwright-cli/
```

- [ ] **Step 3: Write the failing tests** — `tests/test_generate.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

import generate


def make_cfg(**over):
    cfg = {
        "id": "demo",
        "theme": "auto",
        "blocks": ["hero", "services", "prices", "reviews", "gallery", "map", "contact"],
        "name": "Демо Сервис",
        "tagline": "Тестовый шаблон",
        "phone": "+7 900 111-22-33",
        "address": "Москва, ул. Тестовая, 1",
        "hours": "пн–сб 9:00–20:00",
        "seo": {"title": "Демо — тест", "description": "Тестовое описание"},
        "map": {"lat": 55.7746, "lon": 37.7074},
        "services": [{"title": "Услуга", "text": "Описание услуги"}],
        "prices": [{"name": "Позиция", "price": "1 000 ₽"}],
        "reviews": [{"author": f"Читатель {i}", "text": "Отзыв", "rating": 5} for i in range(1, 4)],
        "gallery": [f"assets/demo/{i}.jpg" for i in range(1, 5)],
        "submit": {"type": "messenger"},
    }
    cfg.update(over)
    return cfg


def touch_gallery(root: Path):
    d = root / "assets" / "demo"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(1, 5):
        (d / f"{i}.jpg").write_bytes(b"\xff\xd8\xff")


class TestDigits(unittest.TestCase):
    """Phone normalization: every Russian format -> 11 digits starting with 7."""

    def test_plus7_format(self):
        self.assertEqual(generate.digits("+7 900 111-22-33"), "79001112233")

    def test_eight_prefix_format(self):
        self.assertEqual(generate.digits("8 (900) 111-22-33"), "79001112233")

    def test_ten_digit_format(self):
        self.assertEqual(generate.digits("900 111-22-33"), "79001112233")


class TestValidate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        touch_gallery(self.root)
        self.addCleanup(self.tmp.cleanup)

    def check(self, cfg, *expected):
        with self.assertRaises(generate.ConfigError) as ctx:
            generate.validate(cfg, "sites/demo.json", self.root)
        msg = str(ctx.exception)
        self.assertIn("sites/demo.json", msg)
        for fragment in expected:
            self.assertIn(fragment, msg)

    def test_valid_config_passes(self):
        generate.validate(make_cfg(), "sites/demo.json", self.root)

    def test_missing_phone(self):
        cfg = make_cfg()
        del cfg["phone"]
        self.check(cfg, "отсутствует поле", "phone")

    def test_missing_seo_title(self):
        cfg = make_cfg()
        del cfg["seo"]["title"]
        self.check(cfg, "отсутствует поле", "seo.title")

    def test_unknown_block(self):
        self.check(make_cfg(blocks=["hero", "carousel"]), "неизвестный блок", "carousel")

    def test_bad_theme(self):
        self.check(make_cfg(theme="neon"), "не поддерживается")

    def test_id_mismatch(self):
        self.check(make_cfg(id="other"), "не совпадает с именем файла")

    def test_reviews_minimum_three(self):
        cfg = make_cfg(reviews=cfg_reviews(2))
        self.check(cfg, "reviews", "минимум 3")

    def test_rating_out_of_range(self):
        bad = cfg_reviews(3)
        bad[1]["rating"] = 7
        self.check(make_cfg(reviews=bad), "rating")

    def test_gallery_missing_file(self):
        (self.root / "assets" / "demo" / "3.jpg").unlink()
        self.check(make_cfg(), "не найден", "3.jpg")

    def test_bot_without_username(self):
        self.check(make_cfg(submit={"type": "bot"}), "отсутствует поле", "bot_username")

    def test_phone_wrong_digit_count(self):
        self.check(make_cfg(phone="+7 900 111-22"), "11 цифр")

    def test_load_site_reads_and_validates(self):
        sites = self.root / "sites"
        sites.mkdir(exist_ok=True)
        cfg = make_cfg()
        (sites / "demo.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        loaded = generate.load_site(sites / "demo.json")
        self.assertEqual(loaded["name"], "Демо Сервис")


def cfg_reviews(n):
    return [{"author": f"Читатель {i}", "text": "Отзыв", "rating": 5} for i in range(1, n + 1)]


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd ~/Work/landing-pages && python3 -m unittest discover -s tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'generate'`

- [ ] **Step 5: Implement `generate.py`**

```python
"""Static landing page generator: validate configs -> render templates -> build dist/."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KNOWN_BLOCKS = {"hero", "services", "prices", "reviews", "gallery", "map", "contact"}
THEMES = ("auto", "cafe")
ALWAYS_REQUIRED = ("id", "theme", "blocks", "name", "tagline", "phone",
                   "address", "hours", "seo", "submit")


class ConfigError(Exception):
    """A config problem with a user-facing message: <path>: <problem>."""


def digits(phone):
    """Normalize any Russian phone format to 11 digits starting with 7."""
    d = re.sub(r"\D", "", phone)
    if len(d) == 11 and d.startswith("8"):
        d = "7" + d[1:]
    elif len(d) == 10:
        d = "7" + d
    return d


def _check_list(path, value, minimum, keys, field):
    if not isinstance(value, list) or len(value) < minimum:
        raise ConfigError(f"{path}: поле {field} должно содержать минимум {minimum} записей")
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise ConfigError(f"{path}: {field}[{i}] должен быть объектом")
        for k in keys:
            if k not in item or item[k] in ("", None):
                raise ConfigError(f"{path}: отсутствует поле {field}[{i}].{k}")


def validate(cfg, path, root):
    """Raise ConfigError if the config cannot produce a correct page."""
    for field in ALWAYS_REQUIRED:
        if field not in cfg:
            raise ConfigError(f"{path}: отсутствует поле {field}")
    if cfg["id"] != Path(path).stem:
        raise ConfigError(f'{path}: id "{cfg["id"]}" не совпадает с именем файла')
    if cfg["theme"] not in THEMES:
        raise ConfigError(f'{path}: тема "{cfg["theme"]}" не поддерживается (ожидаются {", ".join(THEMES)})')
    if not isinstance(cfg["blocks"], list) or not cfg["blocks"]:
        raise ConfigError(f"{path}: поле blocks должно быть непустым списком")
    for block in cfg["blocks"]:
        if block not in KNOWN_BLOCKS:
            raise ConfigError(f"{path}: неизвестный блок {block}")
    for field in ("title", "description"):
        if not cfg["seo"].get(field):
            raise ConfigError(f"{path}: отсутствует поле seo.{field}")
    if not all(cfg[f] for f in ("name", "tagline", "address", "hours")):
        raise ConfigError(f"{path}: поля name, tagline, address, hours должны быть непустыми")
    if len(digits(cfg["phone"])) != 11:
        raise ConfigError(f"{path}: поле phone должно содержать 11 цифр с кодом страны")
    if cfg["submit"].get("type") not in ("messenger", "bot"):
        raise ConfigError(f'{path}: submit.type должен быть messenger или bot')
    if cfg["submit"]["type"] == "bot" and not cfg["submit"].get("bot_username"):
        raise ConfigError(f"{path}: отсутствует поле submit.bot_username")
    blocks = set(cfg["blocks"])
    if "services" in blocks:
        _check_list(path, cfg.get("services"), 1, ("title", "text"), "services")
    if "prices" in blocks:
        _check_list(path, cfg.get("prices"), 1, ("name", "price"), "prices")
    if "reviews" in blocks:
        _check_list(path, cfg.get("reviews"), 3, ("author", "text", "rating"), "reviews")
        for i, r in enumerate(cfg["reviews"]):
            if not isinstance(r["rating"], int) or not 1 <= r["rating"] <= 5:
                raise ConfigError(f"{path}: reviews[{i}].rating должен быть от 1 до 5")
    if "gallery" in blocks:
        gallery = cfg.get("gallery")
        if not isinstance(gallery, list) or len(gallery) < 4:
            raise ConfigError(f"{path}: поле gallery должно содержать минимум 4 файла")
        for g in gallery:
            if not (root / g).is_file():
                raise ConfigError(f"{path}: файл галереи не найден: {g}")
    if "map" in blocks:
        m = cfg.get("map")
        if not isinstance(m, dict) or "lat" not in m or "lon" not in m:
            raise ConfigError(f"{path}: отсутствует поле map.lat/map.lon")


def load_site(path):
    """Read and validate one site config; root is two levels above sites/."""
    path = Path(path)
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: невалидный JSON — {e}") from e
    validate(cfg, str(path).replace("\\", "/"), path.parent.parent)
    return cfg
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS, 15 tests (3 digits + 12 validation)

- [ ] **Step 7: Commit**

```bash
cd ~/Work/landing-pages
git add .gitignore generate.py tests/test_generate.py
git commit -m "feat: config validator and phone normalization with tests"
```

---

### Task 2: Gallery assets + site configs

**Files:**
- Create: `assets/auto/1..4.jpg`, `assets/cafe/1..4.jpg`, `sites/auto.json`, `sites/cafe.json`

**Interfaces:**
- Consumes: `generate.load_site` from Task 1 (used here as the acceptance check).
- Produces: two validated configs — the input contract for Tasks 3–5 (exact field names as in Task 1's `make_cfg`, real content from the spec).

- [ ] **Step 1: Ask the user for the phone number**

Ask (one question): «Какой телефон вписать в оба конфига? Он будет опубликован на сайте и в git — формат +7 XXX XXX-XX-XX». Wait for the answer; never invent a number.

- [ ] **Step 2: Download the 8 gallery images**

```bash
cd ~/Work/landing-pages
mkdir -p assets/auto assets/cafe
# auto: car garage, engine block, old tire, workshop wrench (StockSnap CC0)
curl -fsSL -o assets/auto/1.jpg "https://cdn.stocksnap.io/img-thumbs/960w/FETE753B18.jpg"
curl -fsSL -o assets/auto/2.jpg "https://cdn.stocksnap.io/img-thumbs/960w/739D74EEB8.jpg"
curl -fsSL -o assets/auto/3.jpg "https://cdn.stocksnap.io/img-thumbs/960w/EF9KZ7YIJ5.jpg"
curl -fsSL -o assets/auto/4.jpg "https://cdn.stocksnap.io/img-thumbs/960w/O8DVPXYOIY.jpg"
# cafe: cozy interior (WordPress Photo Dir CC0), breakfast table, coffee+cake, cappuccino
curl -fsSL -o assets/cafe/1.jpg "https://pd.w.org/2025/02/78067a47285796801.29683074-2048x1365.jpg"
curl -fsSL -o assets/cafe/2.jpg "https://cdn.stocksnap.io/img-thumbs/960w/BT5N1WHKER.jpg"
curl -fsSL -o assets/cafe/3.jpg "https://live.staticflickr.com/912/42261360291_f75d129a4b_b.jpg"
curl -fsSL -o assets/cafe/4.jpg "https://cdn.stocksnap.io/img-thumbs/960w/9QUVG8OY1I.jpg"
file assets/auto/*.jpg assets/cafe/*.jpg   # expect: JPEG image data, 8 lines
```

If any download fails (non-200), re-run that line once; if it still fails, pick another CC0 image via the Openverse API (`license=cc0`) and note the substitution in the commit message.

- [ ] **Step 3: Write `sites/auto.json`**

All values from the spec Content section; `phone` is the number from Step 1:

```json
{
  "id": "auto",
  "theme": "auto",
  "blocks": ["hero", "services", "prices", "reviews", "gallery", "map", "contact"],
  "name": "АвтоПрофи",
  "tagline": "ТО и ремонт в Москве без лишнего ожидания",
  "phone": "ВСТАВИТЬ_НОМЕР_ОТ_ПОЛЬЗОВАТЕЛЯ",
  "address": "Москва, ул. Электрозаводская, 21к2",
  "hours": "пн–сб 9:00–20:00, вс — выходной",
  "seo": {
    "title": "АвтоПрофи — ТО и ремонт автомобилей в Москве",
    "description": "АвтоПрофи — ТО, замена масла и ремонт автомобилей в Москве на Электрозаводской. Запись по телефону и в WhatsApp."
  },
  "map": { "lat": 55.7746, "lon": 37.7074 },
  "services": [
    { "title": "ТО и замена масла", "text": "Масло, фильтры, жидкости — за час. Работаем на вашем или на нашем масле." },
    { "title": "Диагностика подвески", "text": "Поднимаем на подъёмнике, показываем, что стучит. Цена до ремонта не меняется." },
    { "title": "Ремонт тормозов", "text": "Диски, колодки, суппорты. Оригинал или аналог — на выбор." },
    { "title": "Шиномонтаж и балансировка", "text": "Сезонная замена четырёх колёс, балансировка и ремонт проколов." },
    { "title": "Компьютерная диагностика", "text": "Считываем ошибки блоков, объясняем простыми словами, убираем check-энджин." }
  ],
  "prices": [
    { "name": "Замена масла", "price": "от 1 200 ₽" },
    { "name": "ТО-1", "price": "от 4 500 ₽" },
    { "name": "Диагностика подвески", "price": "800 ₽" },
    { "name": "Ремонт тормозов", "price": "от 2 500 ₽" },
    { "name": "Шиномонтаж (4 колеса)", "price": "от 1 600 ₽" }
  ],
  "reviews": [
    { "author": "Сергей", "text": "Заменил масло и фильтры за час, цену назвали заранее. Повторюсь.", "rating": 5 },
    { "author": "Дмитрий", "text": "Диагностику подвески сделали бесплатно и честно сказали, что пока ездить можно.", "rating": 5 },
    { "author": "Анна", "text": "Приехала с ребёнком, после ремонта тормозов отвезли обратно домой. Внимательные.", "rating": 4 }
  ],
  "gallery": ["assets/auto/1.jpg", "assets/auto/2.jpg", "assets/auto/3.jpg", "assets/auto/4.jpg"],
  "submit": { "type": "messenger" }
}
```

- [ ] **Step 4: Write `sites/cafe.json`**

```json
{
  "id": "cafe",
  "theme": "cafe",
  "blocks": ["hero", "services", "prices", "reviews", "gallery", "map", "contact"],
  "name": "Тёплый хлеб",
  "tagline": "Пекарня-кофейня на Пятницкой",
  "phone": "ВСТАВИТЬ_НОМЕР_ОТ_ПОЛЬЗОВАТЕЛЯ",
  "address": "Москва, ул. Пятницкая, 14",
  "hours": "ежедневно 8:00–22:00",
  "seo": {
    "title": "Тёплый хлеб — пекарня-кофейня в Москве",
    "description": "Тёплый хлеб — пекарня-кофейня на Пятницкой: свежая выпечка, кофе и завтраки ежедневно с 8:00."
  },
  "map": { "lat": 55.7410, "lon": 37.6290 },
  "services": [
    { "title": "Свежая выпечка", "text": "Круассаны, сдоба и хлеб на закваске — из печи каждое утро." },
    { "title": "Кофе", "text": "Капучино, латте, раф и фильтр. Зерно от обжарщика в Москве." },
    { "title": "Завтраки до 12:00", "text": "Сырники, омлеты и гранола — подаются в любые будни." }
  ],
  "prices": [
    { "name": "Круассан", "price": "190 ₽" },
    { "name": "Хлеб на закваске", "price": "320 ₽" },
    { "name": "Капучино", "price": "260 ₽" },
    { "name": "Раф", "price": "320 ₽" },
    { "name": "Сырники со сметаной", "price": "390 ₽" }
  ],
  "reviews": [
    { "author": "Марина", "text": "Хлеб на закваске — как в Париже. Беру каждую субботу.", "rating": 5 },
    { "author": "Игорь", "text": "Капучино и круассан по утрам, wifi есть, розетки у каждого стола.", "rating": 5 },
    { "author": "Ольга", "text": "Сырники большие, сметана отдельно. Кофе правда чуть долго делают.", "rating": 4 }
  ],
  "gallery": ["assets/cafe/1.jpg", "assets/cafe/2.jpg", "assets/cafe/3.jpg", "assets/cafe/4.jpg"],
  "submit": { "type": "messenger" }
}
```

Note: `"phone": "ВСТАВИТЬ_НОМЕР_ОТ_ПОЛЬЗОВАТЕЛЯ"` in both files is replaced with the real number from Step 1 before Step 5 — validation will reject it otherwise.

- [ ] **Step 5: Validate both real configs**

Run:
```bash
cd ~/Work/landing-pages
python3 -c "import generate; generate.load_site('sites/auto.json'); generate.load_site('sites/cafe.json'); print('configs OK')"
```
Expected: `configs OK` (no exception). If `отсутствует поле`/`не найден` appears — fix the config or re-download the missing asset, rerun.

- [ ] **Step 6: Commit**

```bash
git add assets sites
git commit -m "feat: site configs for auto/cafe and local CC0 gallery assets"
```

---

### Task 3: Templates + rendering pipeline

**Files:**
- Create: `template/layout.html`, `template/blocks/{hero,services,prices,reviews,gallery,map,contact}.html`,
  `template/items/{service,price,review,photo}.html`, `template/script.js`, `tests/test_render.py`
- Modify: `generate.py` (add `context`, `render_items`, `render_block`, `assemble`)

**Interfaces:**
- Consumes: `load_site`, `digits`, `make_cfg` (Task 1), validated configs (Task 2).
- Produces (Task 5 uses these exact names):
  - `generate.context(site: dict) -> dict[str, str]` — flat, HTML-escaped; keys: `name`, `tagline`, `phone`, `phone_raw`, `address`, `hours`, `map_lat`, `map_lon`, `seo_title`, `seo_description`, `theme`, `submit_base`, `submit_label`
  - `generate.render_block(name: str, site: dict, ctx: dict) -> str`
  - `generate.assemble(site: dict) -> str` — full `index.html` source

- [ ] **Step 1: Write the failing tests** — `tests/test_render.py`:

```python
import unittest
from pathlib import Path

import generate
from test_generate import make_cfg

ROOT = Path(__file__).resolve().parent.parent


class TestContext(unittest.TestCase):
    def test_escapes_html(self):
        ctx = generate.context(make_cfg(name='Cafe "Nice" & <b>Bar</b>'))
        self.assertEqual(
            ctx["name"],
            "Cafe &quot;Nice&quot; &amp; &lt;b&gt;Bar&lt;/b&gt;",
        )

    def test_submit_base_messenger(self):
        ctx = generate.context(make_cfg())
        self.assertEqual(ctx["submit_base"], "https://wa.me/79001112233")
        self.assertEqual(ctx["submit_label"], "Отправить в WhatsApp")

    def test_submit_base_bot(self):
        ctx = generate.context(make_cfg(submit={"type": "bot", "bot_username": "demo_bot"}))
        self.assertEqual(ctx["submit_base"], "https://t.me/demo_bot?start=landing_demo")
        self.assertEqual(ctx["submit_label"], "Написать в Telegram")


class TestRender(unittest.TestCase):
    def ctx(self, **over):
        return generate.context(make_cfg(**over))

    def test_assemble_block_order(self):
        site = make_cfg(blocks=["contact", "hero"])
        html = generate.assemble(site)
        self.assertLess(html.index('id="contact"'), html.index('id="hero"'))

    def test_default_block_order(self):
        html = generate.assemble(make_cfg())
        self.assertLess(html.index('id="hero"'), html.index('id="services"'))
        self.assertLess(html.index('id="gallery"'), html.index('id="contact"'))

    def test_stars_rendered(self):
        reviews = [{"author": "А", "text": "Б", "rating": 4},
                   {"author": "В", "text": "Г", "rating": 5},
                   {"author": "Д", "text": "Е", "rating": 5}]
        html = generate.render_block("reviews", make_cfg(reviews=reviews), self.ctx(reviews=reviews))
        self.assertIn("★★★★☆", html)
        self.assertEqual(html.count("<blockquote"), 3)

    def test_gallery_src_relative_to_output(self):
        html = generate.render_block("gallery", make_cfg(), self.ctx())
        self.assertIn('src="assets/1.jpg"', html)
        self.assertNotIn("assets/auto/", html)

    def test_map_coords_lon_first(self):
        html = generate.render_block("map", make_cfg(), self.ctx())
        self.assertIn("ll=37.7074%2C55.7746", html)

    def test_all_templates_are_valid(self):
        files = list((ROOT / "template").rglob("*.html"))
        self.assertEqual(len(files), 12)  # layout + 7 blocks + 4 items
        for f in files:
            from string import Template
            self.assertTrue(Template(f.read_text(encoding="utf-8")).is_valid(), f)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `AttributeError: module 'generate' has no attribute 'context'` (templates missing too)

- [ ] **Step 3: Write the 12 template files**

`template/layout.html`:

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${seo_title}</title>
<meta name="description" content="${seo_description}">
<link rel="stylesheet" href="style.css">
</head>
<body data-submit-base="${submit_base}">
<header class="site-header"><div class="wrap">
<a class="brand" href="#hero">${name}</a>
<a class="btn btn-primary" href="#contact">Оставить заявку</a>
</div></header>
<main class="wrap">
${blocks}
</main>
<footer class="site-footer"><div class="wrap">
<p>${name} · ${address} · ${hours}</p>
<p><a href="tel:${phone_raw}">${phone}</a></p>
</div></footer>
<script src="script.js"></script>
</body>
</html>
```

`template/blocks/hero.html`:

```html
<section class="hero" id="hero">
<h1>${name}</h1>
<p class="tagline">${tagline}</p>
<a class="btn btn-primary" href="#contact">Оставить заявку</a>
<a class="btn btn-ghost" href="tel:${phone_raw}">${phone}</a>
</section>
```

`template/blocks/services.html`:

```html
<section class="section" id="services">
<h2>Услуги</h2>
<div class="grid">${items}</div>
</section>
```

`template/blocks/prices.html`:

```html
<section class="section" id="prices">
<h2>Цены</h2>
<ul class="prices">${items}</ul>
</section>
```

`template/blocks/reviews.html`:

```html
<section class="section" id="reviews">
<h2>Отзывы</h2>
<div class="reviews">${items}</div>
</section>
```

`template/blocks/gallery.html`:

```html
<section class="section" id="gallery">
<h2>Фото</h2>
<div class="gallery">${items}</div>
</section>
```

`template/blocks/map.html`:

```html
<section class="section" id="map">
<h2>Как нас найти</h2>
<p class="address">${address} · ${hours}</p>
<iframe class="map-frame" src="https://yandex.com/map-widget/v1/?ll=${map_lon}%2C${map_lat}&amp;z=16" width="100%" height="360" frameborder="0" allowfullscreen title="Карта проезда"></iframe>
</section>
```

`template/blocks/contact.html`:

```html
<section class="section" id="contact">
<h2>Оставить заявку</h2>
<form class="contact-form" id="contact-form">
<label>Имя<input id="f-name" name="name" type="text" required></label>
<label>Телефон<input id="f-phone" name="phone" type="tel" required></label>
<label>Что нужно<input id="f-comment" name="comment" type="text"></label>
<button class="btn btn-primary" id="f-submit" type="submit">${submit_label}</button>
</form>
<p class="contact-alt">Или позвоните: <a href="tel:${phone_raw}">${phone}</a></p>
</section>
```

`template/items/service.html`:

```html
<article class="card"><h3>${title}</h3><p>${text}</p></article>
```

`template/items/price.html`:

```html
<li class="price-row"><span>${name}</span><span class="price">${price}</span></li>
```

`template/items/review.html`:

```html
<blockquote class="review"><div class="stars">${stars}</div><p>${text}</p><cite>${author}</cite></blockquote>
```

`template/items/photo.html`:

```html
<figure class="gallery-item"><img src="${src}" alt="${alt}" loading="lazy"></figure>
```

`template/script.js` (static — not passed through `string.Template`, so `$` would be allowed here, but keep concatenation style):

```js
document.getElementById("contact-form").addEventListener("submit", function (e) {
  e.preventDefault();
  var base = document.body.getAttribute("data-submit-base");
  var msg = "Заявка с сайта. Имя: " + document.getElementById("f-name").value.trim() +
    ". Телефон: " + document.getElementById("f-phone").value.trim() +
    ". " + document.getElementById("f-comment").value.trim();
  window.location.href = base + (base.indexOf("?") > -1 ? "&" : "?") +
    "text=" + encodeURIComponent(msg);
});
```

- [ ] **Step 4: Implement rendering in `generate.py`**

Append (plus imports `from string import Template` and `import html as html_mod` at the top):

```python
ITEM_TEMPLATE_FOR_BLOCK = {"services": "service", "prices": "price",
                           "reviews": "review", "gallery": "photo"}
BLOCKS_DIR = ROOT / "template" / "blocks"
ITEMS_DIR = ROOT / "template" / "items"


def esc(value):
    """HTML-escape a config value for safe insertion into markup/attributes."""
    return html_mod.escape(str(value), quote=True)


def context(site):
    """Flat, escaped substitution context for one site config."""
    phone_digits = digits(site["phone"])
    if site["submit"]["type"] == "bot":
        submit_base = f"https://t.me/{site['submit']['bot_username']}?start=landing_{site['id']}"
        submit_label = "Написать в Telegram"
    else:
        submit_base = f"https://wa.me/{phone_digits}"
        submit_label = "Отправить в WhatsApp"
    return {
        "name": esc(site["name"]),
        "tagline": esc(site["tagline"]),
        "phone": esc(site["phone"]),
        "phone_raw": phone_digits,
        "address": esc(site["address"]),
        "hours": esc(site["hours"]),
        "map_lat": str(site["map"]["lat"]),
        "map_lon": str(site["map"]["lon"]),
        "seo_title": esc(site["seo"]["title"]),
        "seo_description": esc(site["seo"]["description"]),
        "theme": esc(site["theme"]),
        "submit_base": esc(submit_base),
        "submit_label": esc(submit_label),
    }


def render_items(item_template, items):
    """Render each item dict into the item partial and join the results."""
    out = []
    for item in items:
        escaped = {k: esc(v) for k, v in item.items()}
        out.append(Template(item_template).substitute(escaped))
    return "\n".join(out)


def render_block(name, site, ctx):
    """Render one section: wrapper partial plus its repeated items, if any."""
    wrapper = (BLOCKS_DIR / f"{name}.html").read_text(encoding="utf-8")
    if name in ITEM_TEMPLATE_FOR_BLOCK:
        item_tpl = (ITEMS_DIR / f"{ITEM_TEMPLATE_FOR_BLOCK[name]}.html").read_text(encoding="utf-8")
        items = site[name]
        if name == "reviews":
            items = [{**r, "stars": "★" * r["rating"] + "☆" * (5 - r["rating"])} for r in items]
        if name == "gallery":
            items = [{"src": f"assets/{Path(g).name}",
                      "alt": f"{site['name']} — фото {i + 1}"} for i, g in enumerate(items)]
        ctx = {**ctx, "items": render_items(item_tpl, items)}
    try:
        return Template(wrapper).substitute(ctx)
    except KeyError as e:
        raise ConfigError(f"шаблон blocks/{name}.html требует поле {e}, отсутствующее в конфиге") from e


def assemble(site):
    """Full index.html source for one site: layout + blocks in config order."""
    ctx = context(site)
    layout = (ROOT / "template" / "layout.html").read_text(encoding="utf-8")
    blocks_html = "\n".join(render_block(b, site, ctx) for b in site["blocks"])
    try:
        return Template(layout).substitute({**ctx, "blocks": blocks_html})
    except KeyError as e:
        raise ConfigError(f"шаблон layout.html требует поле {e}, отсутствующее в конфиге") from e
```

Note: `blocks_html` is inserted as a Template *value* — values are never rescanned for `$`, so rendered markup stays intact.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS — Tasks 1+3 suites green (24 tests total)

- [ ] **Step 6: Commit**

```bash
git add template tests/test_render.py generate.py
git commit -m "feat: html templates and escaped rendering pipeline with tests"
```

---

### Task 4: Styles — base + two skins

**Files:**
- Create: `theme/base.css`, `theme/auto.css`, `theme/cafe.css`, `tests/test_styles.py`

**Interfaces:**
- Consumes: nothing code-wise; CSS class names match Task 3 templates exactly (`.hero`, `.grid`, `.card`, `.prices`, `.price-row`, `.review`, `.stars`, `.gallery`, `.map-frame`, `.contact-form`, `.site-header`, `.site-footer`).
- Produces: `theme/` contract used by Task 5's `build_site` (merged into `dist/<id>/style.css` as `base.css + "\n" + <skin>.css`).

- [ ] **Step 1: Write the failing test** — `tests/test_styles.py`:

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_VARS = ["--bg", "--surface", "--text", "--accent", "--border", "--btn-text", "--heading-font"]


class TestStyles(unittest.TestCase):
    def test_every_skin_defines_all_vars(self):
        for skin in ("auto", "cafe"):
            css = (ROOT / "theme" / f"{skin}.css").read_text(encoding="utf-8")
            for var in REQUIRED_VARS:
                self.assertIn(f"{var}:", css, f"{skin}.css missing {var}")

    def test_base_uses_accent_and_mobile_breakpoint(self):
        css = (ROOT / "theme" / "base.css").read_text(encoding="utf-8")
        self.assertIn("var(--accent)", css)
        self.assertIn("@media (max-width: 600px)", css)
        self.assertIn("minmax(240px, 1fr)", css)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `FileNotFoundError: .../theme/auto.css`

- [ ] **Step 3: Write `theme/base.css`**

```css
/* Shared layout: colors and fonts come from skin custom properties. */
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
}
h1, h2 { font-family: var(--heading-font); }
.wrap { max-width: 1080px; margin: 0 auto; padding: 0 20px; }

.site-header {
  position: sticky; top: 0; z-index: 10;
  background: var(--surface);
  border-bottom: 2px solid var(--accent);
}
.site-header .wrap {
  display: flex; align-items: center; justify-content: space-between;
  padding-top: 12px; padding-bottom: 12px; gap: 12px;
}
.brand { font-weight: 700; font-size: 20px; color: var(--text); text-decoration: none; }

.btn {
  display: inline-block; padding: 12px 22px; border-radius: 8px;
  text-decoration: none; font-weight: 600; font-size: 16px;
  border: 2px solid transparent; cursor: pointer;
}
.btn-primary { background: var(--accent); color: var(--btn-text); }
.btn-ghost { background: transparent; color: var(--text); border-color: var(--text); }

.hero { padding: 72px 0 56px; }
.hero h1 { font-size: 44px; margin: 0 0 12px; line-height: 1.1; }
.tagline { font-size: 20px; margin: 0 0 28px; opacity: .85; }

.section { padding: 40px 0; }
.section h2 { font-size: 30px; margin: 0 0 24px; }

.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.card h3 { margin: 0 0 8px; font-size: 18px; }

.prices { list-style: none; margin: 0; padding: 0; }
.price-row {
  display: flex; justify-content: space-between; gap: 16px;
  padding: 14px 0; border-bottom: 1px dashed var(--border); font-size: 18px;
}
.price { font-weight: 700; color: var(--accent); white-space: nowrap; }

.reviews { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 18px; }
.review { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin: 0; }
.stars { color: var(--accent); letter-spacing: 2px; margin-bottom: 8px; }
.review cite { display: block; margin-top: 10px; font-style: normal; font-weight: 600; opacity: .75; }

.gallery { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.gallery-item { margin: 0; }
.gallery-item img { width: 100%; height: 220px; object-fit: cover; border-radius: 12px; display: block; }

.map-frame { width: 100%; height: 360px; border: 0; border-radius: 12px; }
.address { font-size: 18px; margin: 0 0 16px; }

.contact-form {
  display: grid; gap: 14px; max-width: 480px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 24px;
}
.contact-form label { display: grid; gap: 6px; font-weight: 600; font-size: 14px; }
.contact-form input {
  padding: 12px; border: 1px solid var(--border); border-radius: 8px;
  font-size: 16px; background: var(--bg); color: var(--text);
}
.contact-alt { margin-top: 16px; }
.contact-alt a { color: var(--accent); }

.site-footer {
  margin-top: 48px; background: var(--surface);
  border-top: 1px solid var(--border); padding: 28px 0; font-size: 15px;
}
.site-footer a { color: var(--accent); }

@media (max-width: 600px) {
  .hero { padding: 48px 0 36px; }
  .hero h1 { font-size: 32px; }
  .tagline { font-size: 17px; }
  .section h2 { font-size: 24px; }
  .site-header .wrap { flex-wrap: wrap; }
}
```

- [ ] **Step 4: Write `theme/auto.css`**

```css
/* Auto service skin: graphite + signal orange, dense headings. */
:root {
  --bg: #16181d;
  --surface: #1f232b;
  --text: #eef1f5;
  --accent: #ff7a1a;
  --border: #333a45;
  --btn-text: #14161a;
  --heading-font: "Arial Black", Impact, sans-serif;
}
```

- [ ] **Step 5: Write `theme/cafe.css`**

```css
/* Cafe skin: cream + terracotta, airy serif headings. */
:root {
  --bg: #faf5ec;
  --surface: #ffffff;
  --text: #3b2f26;
  --accent: #b96a35;
  --border: #e6d9c6;
  --btn-text: #ffffff;
  --heading-font: Georgia, "Times New Roman", serif;
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS — all suites green (26 tests)

- [ ] **Step 7: Commit**

```bash
git add theme tests/test_styles.py
git commit -m "feat: base stylesheet and auto/cafe skins with var contract tests"
```

---

### Task 5: Build CLI + end-to-end tests

**Files:**
- Modify: `generate.py` (add `build_site`, `main`)
- Create: `tests/test_build.py`

**Interfaces:**
- Consumes: `assemble` (Task 3), validated configs (Task 2), `theme/` (Task 4), `template/script.js` (Task 3).
- Produces: runnable CLI `python3 generate.py`; `generate.build_site(site: dict) -> None`; `generate.main() -> int`.

- [ ] **Step 1: Write the failing tests** — `tests/test_build.py`:

```python
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_cli(cwd=ROOT):
    return subprocess.run([sys.executable, "generate.py"], cwd=cwd,
                          capture_output=True, text=True)


class TestBuild(unittest.TestCase):
    """End-to-end: real configs -> dist/ on a clean slate."""

    @classmethod
    def setUpClass(cls):
        shutil.rmtree(ROOT / "dist", ignore_errors=True)
        cls.proc = run_cli()
        cls.html = {i: (ROOT / "dist" / i / "index.html").read_text(encoding="utf-8")
                    for i in ("auto", "cafe") if (ROOT / "dist" / i / "index.html").exists()}

    def test_exit_zero(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_outputs_exist(self):
        for site_id in ("auto", "cafe"):
            base = ROOT / "dist" / site_id
            for name in ("index.html", "style.css", "script.js", "assets/1.jpg", "assets/4.jpg"):
                self.assertTrue((base / name).is_file(), f"missing dist/{site_id}/{name}")

    def test_no_placeholders_anywhere(self):
        for f in (ROOT / "dist").rglob("*"):
            if f.is_file() and f.suffix in (".html", ".css", ".js"):
                self.assertNotIn("$", f.read_text(encoding="utf-8", errors="ignore"), f)

    def test_titles_match_config(self):
        for site_id, html in self.html.items():
            title = json.loads((ROOT / "sites" / f"{site_id}.json").read_text(encoding="utf-8"))["seo"]["title"]
            self.assertIn(f"<title>{title}</title>", html)

    def test_cyrillic_utf8(self):
        auto = self.html["auto"]
        self.assertIn("<html lang=\"ru\">", auto)
        self.assertIn("АвтоПрофи", auto)
        self.assertIn("Тёплый хлеб", self.html["cafe"])

    def test_skins_merged_correctly(self):
        auto_css = (ROOT / "dist" / "auto" / "style.css").read_text(encoding="utf-8")
        cafe_css = (ROOT / "dist" / "cafe" / "style.css").read_text(encoding="utf-8")
        self.assertIn("#16181d", auto_css)   # auto skin bg
        self.assertIn("#faf5ec", cafe_css)   # cafe skin bg
        self.assertIn(".hero", auto_css)     # base merged first
        self.assertIn(".hero", cafe_css)


class TestStaleCleanup(unittest.TestCase):
    def test_stale_files_removed(self):
        stale = ROOT / "dist" / "auto" / "STALE.html"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("junk", encoding="utf-8")
        proc = run_cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(stale.exists(), "rebuild must clear dist/<id> first")


class TestNegative(unittest.TestCase):
    """A broken config must fail loudly and write no output at all."""

    def setUp(self):
        self.tmp = Path(ROOT.parent / f".tmp_negative_{self._testMethodName}")
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.copytree(ROOT, self.tmp,
                        ignore=shutil.ignore_patterns("dist", ".git", "__pycache__",
                                                      "docs", ".playwright-cli", ".tmp*"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_missing_phone_fails_without_output(self):
        cfg_path = self.tmp / "sites" / "auto.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        del cfg["phone"]
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        proc = run_cli(cwd=self.tmp)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("auto.json", proc.stderr)
        self.assertIn("phone", proc.stderr)
        self.assertIn("отсутствует поле", proc.stderr)
        self.assertFalse((self.tmp / "dist").exists(),
                         "validation runs before any output is written")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL or ERROR — `generate.py` has no `main()`/`__main__` block yet, so the CLI writes no output and `dist/` stays empty (first alphabetical test trips on the missing files).

- [ ] **Step 3: Implement build + CLI in `generate.py`**

Append (plus imports `import shutil` at the top):

```python
def build_site(site):
    """Write one self-contained site into dist/<id>/ (replaces any previous build)."""
    out = ROOT / "dist" / site["id"]
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    (out / "index.html").write_text(assemble(site), encoding="utf-8")
    base_css = (ROOT / "theme" / "base.css").read_text(encoding="utf-8")
    skin_css = (ROOT / "theme" / f"{site['theme']}.css").read_text(encoding="utf-8")
    (out / "style.css").write_text(base_css + "\n" + skin_css, encoding="utf-8")
    shutil.copy(ROOT / "template" / "script.js", out / "script.js")
    assets_out = out / "assets"
    assets_out.mkdir()
    for path in site["gallery"]:
        shutil.copy(ROOT / path, assets_out / Path(path).name)


def main():
    """Validate every config first, then build all sites. Returns exit code."""
    try:
        configs = sorted((ROOT / "sites").glob("*.json"))
        if not configs:
            raise ConfigError("sites/: нет ни одного конфига")
        sites = [load_site(p) for p in configs]  # validate ALL before writing anything
        for site in sites:
            build_site(site)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS — all suites green (34 tests)

- [ ] **Step 5: Verify the no-`$` criterion on a real build**

Run: `python3 generate.py && grep -r '\$' dist/ || echo "CLEAN"`
Expected: `CLEAN`

- [ ] **Step 6: Commit**

```bash
git add generate.py tests/test_build.py
git commit -m "feat: cli build with validate-before-write and e2e tests"
```

---

### Task 6: GitHub Actions deploy to Pages

**Files:**
- Create: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: working `python3 generate.py` (Task 5).
- Produces: live URLs `https://sup4ikx.github.io/landing-pages/auto/` and `https://sup4ikx.github.io/landing-pages/cafe/` — consumed by Task 7.

- [ ] **Step 1: Write `.github/workflows/deploy.yml`**

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python3 generate.py
      - uses: actions/upload-pages-artifact@v3
        with:
          path: dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Local pre-flight**

Run: `python3 -m unittest discover -s tests -v && python3 generate.py`
Expected: all tests PASS, exit 0 — CI must not be the first place a failure appears.

- [ ] **Step 3: Commit, create repo, enable Pages, push**

```bash
cd ~/Work/landing-pages
git add .github/workflows/deploy.yml
git commit -m "ci: deploy dist to github pages via actions"
gh auth status   # expect: Logged in to github.com account Sup4ikX
gh repo create landing-pages --public --source=. --remote=origin
gh api repos/Sup4ikX/landing-pages/pages -X POST -f build_type=workflow
git push -u origin main
```

- [ ] **Step 4: Wait for the workflow and verify live URLs**

```bash
gh run watch "$(gh run list -R Sup4ikX/landing-pages -L1 --json databaseId -q '.[0].databaseId')" --exit-status
curl -s -o /dev/null -w "auto: %{http_code}\n" "https://sup4ikx.github.io/landing-pages/auto/"
curl -s -o /dev/null -w "cafe: %{http_code}\n" "https://sup4ikx.github.io/landing-pages/cafe/"
```
Expected: workflow success; `auto: 200`, `cafe: 200`. If `POST pages` returned an error because Pages was already enabled, continue — the check above is the real acceptance.

Note: the repo is public and the phone number is visible on the site — that is by design (spec).

- [ ] **Step 5: Commit nothing else; report URLs to the user**

No new files — this task's deliverable is the two live links.

---

### Task 7: Browser verification (playwright-cli) + screenshots

**Files:**
- Create: `verify/auto-375.png`, `verify/auto-1280.png`, `verify/cafe-375.png`, `verify/live-cafe-1280.png`

**Interfaces:**
- Consumes: local `dist/` (Task 5), live URLs (Task 6).
- Produces: acceptance evidence for spec criteria 4, 5, 6, 7; screenshots kept in the repo as portfolio material.

- [ ] **Step 1: Local mobile checks — auto site**

```bash
cd ~/Work/landing-pages
mkdir -p verify
playwright-cli open "file://$(pwd)/dist/auto/index.html"
playwright-cli resize 375 667
playwright-cli eval "document.documentElement.scrollWidth <= window.innerWidth"   # expect: true
playwright-cli eval "[...document.images].every(i => i.complete && i.naturalWidth > 0)"  # expect: true
playwright-cli console     # expect: no error entries
playwright-cli screenshot --filename=verify/auto-375.png
```

- [ ] **Step 2: Form click test — auto site**

```bash
playwright-cli run-code "async page => { await page.route('**wa.me/**', r => r.fulfill({status: 200, contentType: 'text/html', body: 'ok'})); await page.fill('#f-name', 'Иван'); await page.fill('#f-phone', '+7 900 111-22-33'); await page.click('#f-submit'); await page.waitForURL(/wa\.me/); return page.url(); }"
```
Expected output URL contains `wa.me/<11 digits from sites/auto.json>` and `text=` with `%D0%98%D0%B2%D0%B0%D0%BD` (URL-encoded «Иван»). Get the digits with:
```bash
python3 -c "import generate; print(generate.digits(generate.load_site('sites/auto.json')['phone']))"
```

- [ ] **Step 3: Desktop checks — auto site**

```bash
playwright-cli resize 1280 800
playwright-cli eval "document.documentElement.scrollWidth <= window.innerWidth"   # expect: true
playwright-cli screenshot --filename=verify/auto-1280.png
```

- [ ] **Step 4: Repeat Steps 1–3 for the cafe site**

```bash
playwright-cli open "file://$(pwd)/dist/cafe/index.html"
playwright-cli resize 375 667
playwright-cli eval "document.documentElement.scrollWidth <= window.innerWidth"
playwright-cli eval "[...document.images].every(i => i.complete && i.naturalWidth > 0)"
playwright-cli console
playwright-cli screenshot --filename=verify/cafe-375.png
playwright-cli run-code "async page => { await page.route('**wa.me/**', r => r.fulfill({status: 200, contentType: 'text/html', body: 'ok'})); await page.fill('#f-name', 'Пётр'); await page.fill('#f-phone', '+7 900 111-22-33'); await page.click('#f-submit'); await page.waitForURL(/wa\.me/); return page.url(); }"
```
Expected: same assertions with «Пётр» encoded.

- [ ] **Step 5: Live URL verification (acceptance 6 and 7)**

```bash
playwright-cli open "https://sup4ikx.github.io/landing-pages/cafe/"
playwright-cli eval "document.title"
```
Expected: `Тёплый хлеб — пекарня-кофейня в Москве` (exactly `seo.title` from `sites/cafe.json`).
```bash
playwright-cli eval "document.documentElement.scrollWidth <= window.innerWidth"   # expect: true
playwright-cli eval "[...document.images].every(i => i.complete && i.naturalWidth > 0)"  # expect: true
playwright-cli console     # expect: no errors
playwright-cli screenshot --filename=verify/live-cafe-1280.png
playwright-cli close
```

- [ ] **Step 6: Full suite re-run + acceptance checklist**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests PASS. Then confirm each spec acceptance criterion:

1. `python3 generate.py` exits 0, both `dist/*/index.html` exist — Step 5 of Task 5 ✓
2. No `$` in `dist/` — `grep -r '\$' dist/` empty ✓
3. Missing `phone` → nonzero exit, stderr names field, no output — `TestNegative` ✓
4. 375px no scroll, images 200, no console errors — Steps 1/4/5 here ✓
5. Form submit → wa.me URL with typed name/phone — Steps 2/4 here ✓
6. Both Pages URLs open — Task 6 Step 4 ✓
7. `<title>` matches config — `test_titles_match_config` + live eval ✓

- [ ] **Step 7: Commit screenshots**

```bash
git add verify
git commit -m "test: browser verification screenshots for both sites"
git push
```

---

## Self-Review (executed at plan write time)

- **Spec coverage:** F1→T1/T2, F2→T3, F3→T4, F4/F5→T3 (templates+script) and T7 (click), F6→T3/T5/T7, F7→T2, F8→T3; N1→Global Constraints + all tasks, N2→T4+T7, N3→T1+T5, N4→T1+T5 (never committed, cleaned each build). Acceptance 1–7 mapped in Task 7 Step 6.
- **Placeholders:** phone is obtained from the user in T2 Step 1 (spec-mandated PII, not a TBD); all other content is literal.
- **Type consistency:** `load_site`, `validate`, `digits`, `context`, `render_block`, `assemble`, `build_site`, `main` names identical across tasks; template slot names (`items`, `submit_base`, `phone_raw`, `map_lat/lon`) match `context()` keys.
- **Review Focus:** all five lines have pinning tests in owning tasks (Task 1, 3, 3, 5, 5).
