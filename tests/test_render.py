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
