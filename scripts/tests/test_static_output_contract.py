import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_LAYOUT = REPO_ROOT / "site" / "src" / "routes" / "+layout.js"
class StaticOutputContractTests(unittest.TestCase):
    def test_sveltekit_uses_directory_style_static_routes(self) -> None:
        config = ROOT_LAYOUT.read_text(encoding="utf-8")

        self.assertIn("trailingSlash = 'always'", config)

    def test_layout_keeps_brand_out_of_page_heading_hierarchy(self) -> None:
        layout = (REPO_ROOT / "site" / "src" / "routes" / "+layout.svelte").read_text(encoding="utf-8")

        self.assertIn('<p class="brand">', layout)
        self.assertNotIn('<h1 class="brand"', layout)

    def test_pagination_routes_exist_for_maps_and_categories(self) -> None:
        self.assertTrue((REPO_ROOT / "site" / "src" / "routes" / "maps" / "page" / "[page]" / "+page.js").exists())
        self.assertTrue(
            (REPO_ROOT / "site" / "src" / "routes" / "maps" / "page" / "[page]" / "+page.svelte").exists()
        )
        self.assertTrue(
            (
                REPO_ROOT
                / "site"
                / "src"
                / "routes"
                / "categories"
                / "[slug]"
                / "page"
                / "[page]"
                / "+page.js"
            ).exists()
        )

    def test_static_output_verifier_covers_paginated_depth(self) -> None:
        verifier = (REPO_ROOT / "scripts" / "verify_static_output.py").read_text(encoding="utf-8")

        self.assertIn('"maps" / "page" / "2" / "index.html"', verifier)
        self.assertIn('"maps" / "page" / "5" / "index.html"', verifier)
        self.assertIn('"categories" / "transport" / "page" / "2" / "index.html"', verifier)

    def test_site_build_installs_dependencies_for_release_bundle_checkout(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("pnpm --dir site install --frozen-lockfile", makefile)


if __name__ == "__main__":
    unittest.main()
