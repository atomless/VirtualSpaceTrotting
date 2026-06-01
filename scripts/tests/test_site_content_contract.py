import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCATIONS_PATH = REPO_ROOT / "site" / "src" / "lib" / "data" / "locations.json"
PROVENANCE_PATH = REPO_ROOT / "site" / "static" / "assets" / "locations" / "provenance.json"


class SiteContentContractTests(unittest.TestCase):
    def load_locations(self) -> list[dict[str, object]]:
        return json.loads(LOCATIONS_PATH.read_text(encoding="utf-8"))

    def test_launch_slice_has_structured_fictional_location_corpus(self) -> None:
        locations = self.load_locations()

        self.assertGreaterEqual(len(locations), 12)
        slugs = [str(location["slug"]) for location in locations]
        self.assertEqual(len(slugs), len(set(slugs)))

        for location in locations:
            with self.subTest(slug=location.get("slug")):
                self.assertIs(location.get("fictional"), True)
                self.assertTrue(str(location.get("title", "")).strip())
                self.assertTrue(str(location.get("summary", "")).strip())
                self.assertTrue(str(location.get("category", "")).strip())
                self.assertTrue(str(location.get("region", "")).strip())
                self.assertTrue(str(location.get("dateAdded", "")).startswith("2026-"))
                self.assertTrue(str(location.get("image", "")).startswith("/assets/locations/"))
                self.assertTrue(str(location.get("image", "")).endswith(".png"))
                self.assertNotIn("Google Maps", json.dumps(location))
                self.assertNotIn("Bing Maps", json.dumps(location))

    def test_every_location_image_exists_as_png_with_provenance(self) -> None:
        locations = self.load_locations()
        provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))

        self.assertEqual({entry["slug"] for entry in provenance}, {entry["slug"] for entry in locations})
        for location in locations:
            with self.subTest(slug=location["slug"]):
                image_path = REPO_ROOT / "site" / "static" / str(location["image"]).lstrip("/")
                self.assertTrue(image_path.exists())
                self.assertEqual(image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
                matching = [entry for entry in provenance if entry["slug"] == location["slug"]]
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["status"], "fictional-generated")
                self.assertTrue(matching[0]["method"])


if __name__ == "__main__":
    unittest.main()
