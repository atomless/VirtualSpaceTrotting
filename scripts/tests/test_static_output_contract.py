import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_LAYOUT = REPO_ROOT / "site" / "src" / "routes" / "+layout.js"
class StaticOutputContractTests(unittest.TestCase):
    def test_sveltekit_uses_directory_style_static_routes(self) -> None:
        config = ROOT_LAYOUT.read_text(encoding="utf-8")

        self.assertIn("trailingSlash = 'always'", config)


if __name__ == "__main__":
    unittest.main()
