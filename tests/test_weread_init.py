import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "weread_init.py"
SPEC = importlib.util.spec_from_file_location("weread_init", MODULE_PATH)
weread_init = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(weread_init)


class InitWizardTests(unittest.TestCase):
    def test_run_init_wizard_continues_to_output_dir_after_successful_qr_login(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "weread.json"
            config_path.write_text(
                json.dumps(
                    {
                        "vid": "",
                        "skey": "",
                        "output_dir": "/root/workspace/weread-notes",
                        "sync_to_obsidian": False,
                    }
                ),
                encoding="utf-8",
            )

            target_dir = Path(tmpdir) / "exports"
            with patch.object(weread_init, "qr_login", return_value=True) as qr_login_mock, \
                 patch("builtins.input", return_value=str(target_dir)):
                ok = weread_init.run_init_wizard(config_path)

            self.assertTrue(ok)
            qr_login_mock.assert_called_once_with(config_path)
            saved = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["output_dir"], str(target_dir.resolve()))
            self.assertTrue(target_dir.exists())

    def test_run_init_wizard_uses_default_output_dir_on_empty_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "weread.json"
            config_path.write_text(json.dumps({"vid": "", "skey": ""}), encoding="utf-8")

            with patch.object(weread_init, "qr_login", return_value=True), \
                 patch("builtins.input", return_value=""):
                ok = weread_init.run_init_wizard(config_path)

            self.assertTrue(ok)
            saved = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["output_dir"], str(weread_init.DEFAULT_OUTPUT_DIR.resolve()))

    def test_run_init_wizard_returns_false_when_output_dir_write_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "weread.json"
            config_path.write_text(json.dumps({"vid": "", "skey": ""}), encoding="utf-8")

            with patch.object(weread_init, "qr_login", return_value=True), \
                 patch("builtins.input", return_value=str(Path(tmpdir) / "exports")), \
                 patch.object(weread_init.Path, "mkdir", side_effect=PermissionError("no permission")):
                ok = weread_init.run_init_wizard(config_path)

            self.assertFalse(ok)

    def test_run_init_wizard_returns_false_when_config_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "weread.json"
            config_path.write_text("{bad json", encoding="utf-8")

            with patch.object(weread_init, "qr_login", return_value=True), \
                 patch("builtins.input", return_value=str(Path(tmpdir) / "exports")):
                ok = weread_init.run_init_wizard(config_path)

            self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
