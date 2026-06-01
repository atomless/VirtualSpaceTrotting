import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class RuntimeScaffoldContractTests(unittest.TestCase):
    def test_spin_manifest_serves_static_site_and_rust_health_route(self) -> None:
        spin_manifest = (REPO_ROOT / "spin.toml").read_text(encoding="utf-8")

        self.assertIn('route = "/health"', spin_manifest)
        self.assertIn('route = "/..."', spin_manifest)
        self.assertIn('files = [{ source = "dist/site", destination = "/" }]', spin_manifest)
        self.assertIn('source = "dist/wasm/virtual_space_trotting.wasm"', spin_manifest)

    def test_rust_runtime_has_health_response_contract(self) -> None:
        runtime_source = (REPO_ROOT / "src" / "lib.rs").read_text(encoding="utf-8")

        self.assertIn("health_response", runtime_source)
        self.assertIn("VirtualSpaceTrotting OK", runtime_source)

    def test_spin_sdk_matches_local_spin_runtime_generation(self) -> None:
        cargo_toml = (REPO_ROOT / "Cargo.toml").read_text(encoding="utf-8")
        runtime_source = (REPO_ROOT / "src" / "lib.rs").read_text(encoding="utf-8")
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        spin_manifest = (REPO_ROOT / "spin.toml").read_text(encoding="utf-8")

        self.assertIn('crate-type = ["rlib"]', cargo_toml)
        self.assertIn('spin-sdk = "2.2.0"', cargo_toml)
        self.assertIn("cargo rustc --target wasm32-wasip1 --release --lib --crate-type cdylib", makefile)
        self.assertIn("cargo rustc --target wasm32-wasip1 --release --lib --crate-type cdylib", spin_manifest)
        self.assertIn("http_component", runtime_source)
        self.assertNotIn("http_service", runtime_source)


if __name__ == "__main__":
    unittest.main()
