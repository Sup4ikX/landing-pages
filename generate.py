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
