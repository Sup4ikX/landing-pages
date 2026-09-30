"""Static landing page generator: validate configs -> render templates -> build dist/."""
import html as html_mod
import json
import re
import shutil
import sys
from pathlib import Path
from string import Template

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
    if not isinstance(cfg, dict):
        raise ConfigError(f"{path}: конфиг должен быть JSON-объектом")
    for field in ALWAYS_REQUIRED:
        value = cfg.get(field)
        if value is None or (isinstance(value, (str, list, dict)) and not value):
            raise ConfigError(f"{path}: отсутствует поле {field}")
    if not isinstance(cfg["seo"], dict):
        raise ConfigError(f"{path}: отсутствует поле seo")
    if cfg["id"] != Path(path).stem:
        raise ConfigError(f'{path}: id "{cfg["id"]}" не совпадает с именем файла')
    if cfg["theme"] not in THEMES:
        raise ConfigError(f'{path}: тема "{cfg["theme"]}" не поддерживается (ожидаются {", ".join(THEMES)})')
    if not isinstance(cfg["blocks"], list) or not cfg["blocks"]:
        raise ConfigError(f"{path}: поле blocks должно быть непустым списком")
    for block in cfg["blocks"]:
        if not isinstance(block, str) or block not in KNOWN_BLOCKS:
            raise ConfigError(f"{path}: неизвестный блок {block}")
    for field in ("title", "description"):
        if not cfg["seo"].get(field):
            raise ConfigError(f"{path}: отсутствует поле seo.{field}")
    if not all(cfg[f] for f in ("name", "tagline", "address", "hours")):
        raise ConfigError(f"{path}: поля name, tagline, address, hours должны быть непустыми")
    phone = cfg["phone"]
    phone_digits = digits(phone) if isinstance(phone, str) else ""
    if len(phone_digits) != 11 or not phone_digits.startswith("7"):
        raise ConfigError(f"{path}: поле phone должно содержать 11 цифр с кодом страны")
    if not isinstance(cfg["submit"], dict) or cfg["submit"].get("type") not in ("messenger", "bot"):
        raise ConfigError(f"{path}: отсутствует поле submit")
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
            if not isinstance(g, str) or not (root / g).is_file():
                raise ConfigError(f"{path}: файл галереи не найден: {g}")
    if "map" in blocks:
        m = cfg.get("map")
        if not isinstance(m, dict) or "lat" not in m or "lon" not in m:
            raise ConfigError(f"{path}: отсутствует поле map.lat/map.lon")
        for axis in ("lat", "lon"):
            if isinstance(m[axis], bool) or not isinstance(m[axis], (int, float)):
                raise ConfigError(f"{path}: поле map.{axis} должно быть числом")


def load_site(path):
    """Read and validate one site config; root is two levels above sites/."""
    path = Path(path)
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: невалидный JSON — {e}") from e
    validate(cfg, str(path).replace("\\", "/"), path.parent.parent)
    return cfg


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
    blocks = set(site["blocks"])
    contact = "contact" in blocks
    site_map = site.get("map") or {}
    return {
        "name": esc(site["name"]),
        "tagline": esc(site["tagline"]),
        "phone": esc(site["phone"]),
        "phone_raw": phone_digits,
        "address": esc(site["address"]),
        "hours": esc(site["hours"]),
        "map_lat": esc(site_map.get("lat", "")),
        "map_lon": esc(site_map.get("lon", "")),
        "hero_href": "#hero" if "hero" in blocks else "#",
        "cta_href": "#contact" if contact else f"tel:{phone_digits}",
        "cta_label": "Оставить заявку" if contact else "Позвонить",
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
    gallery_paths = site.get("gallery") or []
    if gallery_paths:
        assets_out = out / "assets"
        assets_out.mkdir()
        for path in gallery_paths:
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
