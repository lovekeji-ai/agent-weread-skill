import io
import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


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


class QrLoginCompatTests(unittest.TestCase):
    def test_qr_login_accepts_new_getinfo_shape_with_skey_vid_code(self):
        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload
            def json(self):
                return self._payload

        class FakeSession:
            def __init__(self):
                self.headers = {}
                self.calls = []
            def post(self, url, json=None, timeout=None):
                self.calls.append((url, json, timeout))
                if url == weread_auth.GETUID_URL:
                    return FakeResponse({'uid': 'u-1'})
                if url == weread_auth.GETINFO_URL:
                    return FakeResponse({'skey': 'new-skey', 'vid': 12345, 'code': 'abc'})
                if url == weread_auth.SESSION_INIT_URL:
                    return FakeResponse({'success': 1})
                raise AssertionError(f'unexpected url: {url}')

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'weread.json'
            config_path.write_text(json.dumps({'output_dir': tmpdir}), encoding='utf-8')
            fake_session = FakeSession()

            with patch.object(weread_auth.requests, 'Session', return_value=fake_session), \
                 patch.object(weread_auth, '_render_qr_terminal', return_value=Path(tmpdir) / 'qr.png'), \
                 patch.object(weread_auth.time, 'sleep', return_value=None):
                ok = weread_auth.qr_login(config_path, timeout_seconds=1)

            self.assertTrue(ok)
            saved = json.loads(config_path.read_text(encoding='utf-8'))
            self.assertEqual(saved['vid'], '12345')
            self.assertEqual(saved['skey'], 'new-skey')
            self.assertNotIn('rt', saved)
            session_init_call = fake_session.calls[-1]
            self.assertEqual(session_init_call[0], weread_auth.SESSION_INIT_URL)
            self.assertEqual(session_init_call[1]['skey'], 'new-skey')


if __name__ == "__main__":
    unittest.main()
