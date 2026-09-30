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
