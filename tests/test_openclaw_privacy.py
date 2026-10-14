from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from backend.openclaw_gateway import OpenClawGatewayClient, OpenClawGatewayConfig, OpenClawGatewayError, discover_openclaw_state_dir


class TestOpenClawCredentialIsolation(unittest.TestCase):
    def make_client(self, directory: str) -> OpenClawGatewayClient:
        return OpenClawGatewayClient(OpenClawGatewayConfig(
            state_dir=str(Path(directory) / "state"),
            workspace_dir=str(Path(directory) / "workspace"),
            codex_home=str(Path(directory) / "app-codex"),
            repo_path=str(Path(directory) / "vendor"),
            url="ws://127.0.0.1:18890",
            origin="http://127.0.0.1:18890",
            timeout_ms=5000,
            client_id="test-client",
            client_mode="backend",
        ))

    def test_default_never_probes_or_copies_desktop_login(self) -> None:
        with TemporaryDirectory(prefix="aociety-privacy-test-") as directory:
            client = self.make_client(directory)
            with patch.dict(os.environ, {}, clear=True), patch.object(Path, "home", side_effect=AssertionError("must not inspect global home")), patch("backend.openclaw_gateway.shutil.copy2") as copy:
                isolated = client._prepare_codex_home({})
            self.assertEqual(isolated.name, "isolated-runtime")
            self.assertTrue((isolated / "config.toml").is_file())
            self.assertFalse((isolated / "auth.json").exists())
            copy.assert_not_called()

    def test_inherited_codex_home_and_legacy_account_data_are_not_mutated(self) -> None:
        with TemporaryDirectory(prefix="aociety-privacy-test-") as directory:
            client = self.make_client(directory)
            legacy = Path(client.config.codex_home) / "runtime"
            legacy.mkdir(parents=True)
            sentinel = legacy / "account-sentinel.txt"
            sentinel.write_text("preserve this test fixture", encoding="utf-8")
            inherited = Path(directory) / "global-codex"
            with patch.dict(os.environ, {"CODEX_HOME": str(inherited)}, clear=True):
                isolated = client._prepare_codex_home({})
            self.assertFalse(inherited.exists())
            self.assertEqual(isolated.parent, Path(client.config.codex_home))
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve this test fixture")

    def test_shared_login_is_only_copied_after_explicit_opt_in(self) -> None:
        with TemporaryDirectory(prefix="aociety-privacy-test-") as directory:
            client = self.make_client(directory)
            source = Path(directory) / "authorized-fixture"
            source.mkdir()
            (source / "auth.json").write_text('{"test_fixture":true}', encoding="utf-8")
            (source / "cap_sid").write_text("not-a-real-session", encoding="utf-8")
            with patch.dict(os.environ, {"OPENCLAW_ALLOW_SHARED_CODEX_AUTH": "1", "OPENCLAW_SHARED_CODEX_HOME": str(source)}, clear=True), patch.object(Path, "home", side_effect=AssertionError("only the specified fixture is authorized")):
                shared = client._prepare_codex_home({})
            self.assertEqual(shared.name, "shared-runtime")
            self.assertEqual((shared / "auth.json").read_text(encoding="utf-8"), '{"test_fixture":true}')
            with patch.dict(os.environ, {}, clear=True), patch.object(Path, "home", side_effect=AssertionError("sharing was disabled")):
                isolated = client._prepare_codex_home({})
            self.assertNotEqual(shared, isolated)
            self.assertFalse((isolated / "auth.json").exists())
            self.assertTrue((shared / "auth.json").exists())

    def test_missing_opt_in_login_has_actionable_error(self) -> None:
        with TemporaryDirectory(prefix="aociety-privacy-test-") as directory:
            client = self.make_client(directory)
            with patch.dict(os.environ, {"OPENCLAW_ALLOW_SHARED_CODEX_AUTH": "1", "OPENCLAW_SHARED_CODEX_HOME": str(Path(directory) / "missing-fixture")}, clear=True):
                with self.assertRaisesRegex(OpenClawGatewayError, "explicitly enabled.*OPENCLAW_SHARED_CODEX_HOME"):
                    client._prepare_codex_home({})


class TestOpenClawStateIsolation(unittest.TestCase):
    def create_fixture(self, source: Path) -> None:
        (source / "identity").mkdir(parents=True)
        (source / "openclaw.json").write_text('{"test_fixture":true}', encoding="utf-8")
        (source / "identity" / "device.json").write_text('{"test_device":true}', encoding="utf-8")
        (source / "identity" / "device-auth.json").write_text('{"test_auth":true}', encoding="utf-8")

    def test_default_never_probes_global_account_directories(self) -> None:
        with TemporaryDirectory(prefix="aociety-state-test-") as directory:
            with patch.dict(os.environ, {}, clear=True), patch.object(Path, "home", side_effect=AssertionError("must not inspect global home")), patch("backend.openclaw_gateway.shutil.copy2") as copy:
                with self.assertRaisesRegex(OpenClawGatewayError, "OPENCLAW_STATE_DIR"):
                    discover_openclaw_state_dir(str(Path(directory) / "state"), str(Path(directory) / "workspace"))
            copy.assert_not_called()

    def test_explicit_application_state_works_without_shared_permission(self) -> None:
        with TemporaryDirectory(prefix="aociety-state-test-") as directory:
            source = Path(directory) / "application-state"
            self.create_fixture(source)
            with patch.dict(os.environ, {}, clear=True), patch.object(Path, "home", side_effect=AssertionError("must not inspect global home")):
                selected = discover_openclaw_state_dir(str(source), str(Path(directory) / "workspace"))
            self.assertEqual(selected, source.resolve())

    def test_shared_source_without_opt_in_is_not_read_or_copied(self) -> None:
        with TemporaryDirectory(prefix="aociety-state-test-") as directory:
            source = Path(directory) / "other-app-fixture"
            self.create_fixture(source)
            with patch.dict(os.environ, {"OPENCLAW_SHARED_STATE_DIR": str(source)}, clear=True), patch("backend.openclaw_gateway.shutil.copy2") as copy:
                with self.assertRaises(OpenClawGatewayError):
                    discover_openclaw_state_dir(str(Path(directory) / "state"), str(Path(directory) / "workspace"))
            copy.assert_not_called()

    def test_explicit_opt_in_copies_only_the_selected_fixture(self) -> None:
        with TemporaryDirectory(prefix="aociety-state-test-") as directory:
            source, target = Path(directory) / "authorized-fixture", Path(directory) / "application-state"
            self.create_fixture(source)
            with patch.dict(os.environ, {"OPENCLAW_ALLOW_SHARED_STATE": "1", "OPENCLAW_SHARED_STATE_DIR": str(source)}, clear=True), patch.object(Path, "home", side_effect=AssertionError("only the selected fixture is authorized")):
                selected = discover_openclaw_state_dir(str(target), str(Path(directory) / "workspace"))
            self.assertEqual(selected, target.resolve())
            self.assertEqual((target / "identity" / "device-auth.json").read_text(encoding="utf-8"), '{"test_auth":true}')
            self.assertTrue(source.is_dir())

    def test_sharing_flag_alone_does_not_grant_a_global_search(self) -> None:
        with TemporaryDirectory(prefix="aociety-state-test-") as directory:
            with patch.dict(os.environ, {"OPENCLAW_ALLOW_SHARED_STATE": "1"}, clear=True), patch.object(Path, "home", side_effect=AssertionError("sharing flag alone is not a global search permission")):
                with self.assertRaises(OpenClawGatewayError):
                    discover_openclaw_state_dir(str(Path(directory) / "state"), str(Path(directory) / "workspace"))


if __name__ == "__main__":
    unittest.main()
