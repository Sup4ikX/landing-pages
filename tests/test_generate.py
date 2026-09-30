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


def cfg_reviews(n):
    return [{"author": f"Читатель {i}", "text": "Отзыв", "rating": 5} for i in range(1, n + 1)]


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
        self.check(make_cfg(reviews=cfg_reviews(2)), "reviews", "минимум 3")

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


if __name__ == "__main__":
    unittest.main()
