import json
import unittest

from scripts.mpulse_profiles import RegistryError, parse_registry_text, render_browser_config


VALID_PROFILE = {
    "description": "Alma development tenant",
    "script_base_url": "https://collector.example.com/boomerang/",
    "api_key": "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY",
}


def registry_text(*, profiles=None, schema="virtual-space-trotting.mpulse-profiles.v1") -> str:
    return json.dumps({"schema": schema, "profiles": profiles or {"dev-alma": VALID_PROFILE}})


class MPulseProfilesTests(unittest.TestCase):
    def test_parses_valid_registry_and_composes_script_url(self) -> None:
        registry = parse_registry_text(registry_text())

        profile = registry.profile("dev-alma")

        self.assertEqual(profile.name, "dev-alma")
        self.assertEqual(profile.description, "Alma development tenant")
        self.assertEqual(
            profile.script_url,
            "https://collector.example.com/boomerang/ABCDE-FGHIJ-KLMNO-PQRST-UVWXY",
        )

    def test_rejects_unknown_schema_and_empty_profiles(self) -> None:
        with self.assertRaisesRegex(RegistryError, "schema"):
            parse_registry_text(registry_text(schema="unknown"))
        with self.assertRaisesRegex(RegistryError, "at least one profile"):
            parse_registry_text(json.dumps({"schema": "virtual-space-trotting.mpulse-profiles.v1", "profiles": {}}))

    def test_rejects_duplicate_json_keys(self) -> None:
        text = (
            '{"schema":"virtual-space-trotting.mpulse-profiles.v1","profiles":{'
            '"dev-alma":{"description":"one","script_base_url":"https://one.example/boomerang/",'
            '"api_key":"ABCDE-FGHIJ-KLMNO-PQRST-UVWXY"},'
            '"dev-alma":{"description":"two","script_base_url":"https://two.example/boomerang/",'
            '"api_key":"ABCDE-FGHIJ-KLMNO-PQRST-UVWXY"}}}'
        )

        with self.assertRaisesRegex(RegistryError, "duplicate"):
            parse_registry_text(text)

    def test_rejects_invalid_profile_names(self) -> None:
        for name in ("Dev-Alma", "dev_alma", "-dev", "dev-", "", "a" * 65):
            with self.subTest(name=name), self.assertRaisesRegex(RegistryError, "profile name"):
                parse_registry_text(registry_text(profiles={name: VALID_PROFILE}))

    def test_rejects_unsafe_or_incorrect_script_urls(self) -> None:
        urls = (
            "http://collector.example.com/boomerang/",
            "https://user@collector.example.com/boomerang/",
            "https://collector.example.com/boomerang/?mode=test",
            "https://collector.example.com/boomerang/#fragment",
            "https://collector.example.com/not-boomerang/",
            "https:///boomerang/",
        )
        for url in urls:
            profile = {**VALID_PROFILE, "script_base_url": url}
            with self.subTest(url=url), self.assertRaisesRegex(RegistryError, "script_base_url"):
                parse_registry_text(registry_text(profiles={"dev-alma": profile}))

    def test_rejects_malformed_key_unknown_fields_and_long_description(self) -> None:
        cases = (
            ({**VALID_PROFILE, "api_key": "not-a-key"}, "api_key"),
            ({**VALID_PROFILE, "extra": "value"}, "unknown"),
            ({**VALID_PROFILE, "description": "x" * 201}, "description"),
        )
        for profile, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(RegistryError, message):
                parse_registry_text(registry_text(profiles={"dev-alma": profile}))

    def test_rejects_unknown_top_level_fields_and_invalid_json(self) -> None:
        payload = json.loads(registry_text())
        payload["extra"] = True
        with self.assertRaisesRegex(RegistryError, "unknown"):
            parse_registry_text(json.dumps(payload))
        with self.assertRaisesRegex(RegistryError, "valid JSON"):
            parse_registry_text("{")

    def test_renders_deterministic_browser_configuration(self) -> None:
        profile = parse_registry_text(registry_text()).profile("dev-alma")

        script = render_browser_config(profile)

        self.assertEqual(
            script,
            'window.VST_MPULSE_PROFILE = Object.freeze({'
            '"apiKey":"ABCDE-FGHIJ-KLMNO-PQRST-UVWXY",'
            '"name":"dev-alma",'
            '"scriptBaseUrl":"https://collector.example.com/boomerang/"});\n',
        )

    def test_canonical_json_is_stable_and_does_not_include_runtime_state(self) -> None:
        registry = parse_registry_text(registry_text())

        canonical = registry.canonical_json()

        self.assertEqual(canonical.endswith("\n"), True)
        self.assertEqual(json.loads(canonical)["profiles"]["dev-alma"], VALID_PROFILE)
        self.assertNotIn("active", canonical)


if __name__ == "__main__":
    unittest.main()
