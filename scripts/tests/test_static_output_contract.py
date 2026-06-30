import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_LAYOUT = REPO_ROOT / "site" / "src" / "routes" / "+layout.js"
ROOT_LAYOUT_SVELTE = REPO_ROOT / "site" / "src" / "routes" / "+layout.svelte"
APP_TEMPLATE = REPO_ROOT / "site" / "src" / "app.html"
MPULSE_PLACEHOLDER = REPO_ROOT / "site" / "static" / "mpulse-config.js"
SVELTE_CONFIG = REPO_ROOT / "site" / "svelte.config.js"
PNPM_WORKSPACE = REPO_ROOT / "site" / "pnpm-workspace.yaml"
LISTING_PAGE_TEMPLATES = [
    REPO_ROOT / "site" / "src" / "routes" / "maps" / "+page.svelte",
    REPO_ROOT / "site" / "src" / "routes" / "maps" / "page" / "[page]" / "+page.svelte",
    REPO_ROOT / "site" / "src" / "routes" / "categories" / "[slug]" / "+page.svelte",
    REPO_ROOT / "site" / "src" / "routes" / "categories" / "[slug]" / "page" / "[page]" / "+page.svelte",
]


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

    def test_listing_pages_place_pagination_before_location_list(self) -> None:
        for path in LISTING_PAGE_TEMPLATES:
            with self.subTest(path=path.relative_to(REPO_ROOT)):
                template = path.read_text(encoding="utf-8")

                self.assertLess(template.index("<PageNav"), template.index("<LocationList"))

    def test_static_output_verifier_covers_paginated_depth(self) -> None:
        verifier = (REPO_ROOT / "scripts" / "verify_static_output.py").read_text(encoding="utf-8")

        self.assertIn('"maps" / "page" / "2" / "index.html"', verifier)
        self.assertIn('"maps" / "page" / "5" / "index.html"', verifier)
        self.assertIn('"categories" / "transport" / "page" / "2" / "index.html"', verifier)

    def test_site_build_installs_dependencies_for_release_bundle_checkout(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("pnpm --dir site install --frozen-lockfile", makefile)

    def test_release_build_explicitly_approves_esbuild_install_script(self) -> None:
        policy = PNPM_WORKSPACE.read_text(encoding="utf-8")

        self.assertIn("allowBuilds:\n", policy)
        self.assertIn("  esbuild@0.25.12: true\n", policy)
        self.assertNotIn("dangerouslyAllowAllBuilds: true", policy)

    def test_boomerang_snippet_is_in_page_template(self) -> None:
        template = APP_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('<script src="/mpulse-config.js"></script>', template)
        self.assertLess(template.index('/mpulse-config.js'), template.index("window.BOOMR_config"))
        self.assertIn("window.VST_MPULSE_PROFILE", template)
        self.assertIn("profile.scriptBaseUrl + profile.apiKey", template)
        self.assertIn("window.BOOMR_config", template)
        self.assertIn("window.BOOMR.snippetStart", template)
        self.assertIn("window.BOOMR.snippetExecuted = true", template)
        self.assertIn("window.BOOMR.snippetVersion = 14", template)
        self.assertNotIn("%sveltekit.env.BOOMERANG_API_KEY%", template)
        self.assertNotIn("rum-dev-alma-dct-collector.soasta.com", template)
        self.assertIn("script.src = window.BOOMR.url", template)
        self.assertIn('link.rel = "preload"', template)
        self.assertIn("iframeLoader(true)", template)
        self.assertNotIn("https://c.go-mpulse.net/boomerang/", template)

    def test_boomerang_non_page_load_instrumentation_is_bootstrapped(self) -> None:
        template = APP_TEMPLATE.read_text(encoding="utf-8")
        layout = ROOT_LAYOUT_SVELTE.read_text(encoding="utf-8")

        self.assertIn("window.BOOMR_EARLY_STATE", template)
        self.assertIn('"vst:boomerang-first-input"', template)
        self.assertIn('"vst:boomerang-ready"', template)
        self.assertIn("installBoomerangInstrumentation", layout)
        self.assertIn("onMount", layout)

    def test_missing_host_profile_keeps_static_build_inert(self) -> None:
        placeholder = MPULSE_PLACEHOLDER.read_text(encoding="utf-8")
        config = SVELTE_CONFIG.read_text(encoding="utf-8")

        self.assertEqual(placeholder, "window.VST_MPULSE_PROFILE = null;\n")
        self.assertNotIn("publicPrefix", config)
        self.assertNotIn("LINODE_", config)


if __name__ == "__main__":
    unittest.main()
