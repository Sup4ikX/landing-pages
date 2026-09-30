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


class TestSubset(unittest.TestCase):
    """Spec allows block subsets: absent optional blocks/keys must not crash."""

    def setUp(self):
        self.tmp = Path(ROOT.parent / f".tmp_subset_{self._testMethodName}")
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.copytree(ROOT, self.tmp,
                        ignore=shutil.ignore_patterns("dist", ".git", "__pycache__",
                                                      "docs", ".playwright-cli", ".tmp*"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write_auto(self, cfg):
        p = self.tmp / "sites" / "auto.json"
        p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

    def test_minimal_config_without_optional_keys(self):
        cfg = json.loads((ROOT / "sites" / "auto.json").read_text(encoding="utf-8"))
        cfg["blocks"] = ["hero", "services"]
        del cfg["map"]
        del cfg["gallery"]
        self.write_auto(cfg)
        (self.tmp / "sites" / "cafe.json").unlink()
        proc = run_cli(cwd=self.tmp)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        html = (self.tmp / "dist" / "auto" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('id="map"', html)
        self.assertNotIn('id="contact"', html)
        self.assertIn('href="tel:79001112233"', html)
        self.assertFalse((self.tmp / "dist" / "auto" / "assets").exists())
        script = (self.tmp / "dist" / "auto" / "script.js").read_text(encoding="utf-8")
        self.assertIn("if (form)", script)


if __name__ == "__main__":
    unittest.main()
