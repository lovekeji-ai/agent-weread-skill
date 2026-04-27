import io
import importlib.util
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "weread_auth.py"
SPEC = importlib.util.spec_from_file_location("weread_auth", MODULE_PATH)
weread_auth = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(weread_auth)


class RenderQrTerminalTests(unittest.TestCase):
    def test_render_qr_terminal_saves_png_and_prints_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = io.StringIO()
            with redirect_stdout(out):
                png_path = weread_auth._render_qr_terminal(
                    "https://example.com/qr",
                    output_dir=tmpdir,
                )

            output = out.getvalue()
            self.assertTrue(Path(png_path).exists())
            self.assertEqual(Path(png_path).suffix, ".png")
            self.assertIn("请用微信扫码登录", output)
            self.assertIn("二维码图片已保存到", output)
            self.assertIn("MEDIA:", output)
            self.assertIn(str(png_path), output)

    def test_render_qr_terminal_falls_back_to_ascii_when_png_save_unavailable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_output_dir = Path(tmpdir) / "not-a-dir"
            invalid_output_dir.write_text("x", encoding="utf-8")

            out = io.StringIO()
            with redirect_stdout(out):
                png_path = weread_auth._render_qr_terminal(
                    "https://example.com/qr-fallback",
                    output_dir=invalid_output_dir,
                )

            output = out.getvalue()
            self.assertEqual(Path(png_path).parent, invalid_output_dir)
            self.assertIn("PNG 保存失败", output)
            self.assertIn("请用微信扫码登录", output)
            self.assertIn("https://example.com/qr-fallback", output)


if __name__ == "__main__":
    unittest.main()
