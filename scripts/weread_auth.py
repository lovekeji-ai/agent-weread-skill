"""微信读书鉴权：skey 自动续期 + QR 扫码兜底。

主路径：调用 /web/login/renewal 用现有 cookie 换新的 wr_skey。
兜底：续期失败时，走 /web/login/getuid + /web/login/getinfo 的扫码登录流程，
      QR 在终端渲染，扫码后把新的 vid/skey/rt 写回配置。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

WEREAD_ORIGIN = "https://weread.qq.com"
RENEWAL_URL = f"{WEREAD_ORIGIN}/web/login/renewal"
GETUID_URL = f"{WEREAD_ORIGIN}/web/login/getuid"
GETINFO_URL = f"{WEREAD_ORIGIN}/web/login/getinfo"
SESSION_INIT_URL = f"{WEREAD_ORIGIN}/web/login/session/init"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://weread.qq.com/",
    "Origin": WEREAD_ORIGIN,
    "Content-Type": "application/json",
}


def load_config(config_path: str | os.PathLike) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config_path: str | os.PathLike, data: dict) -> None:
    """原子写回配置，保留人眼可读格式。"""
    path = Path(config_path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _cookies_from_config(config: dict) -> dict:
    cookies = {}
    if config.get("vid"):
        cookies["wr_vid"] = str(config["vid"])
    if config.get("skey"):
        cookies["wr_skey"] = config["skey"]
    if config.get("rt"):
        cookies["wr_rt"] = config["rt"]
    return cookies


def _extract_cookie(set_cookie_headers: list[str], name: str) -> Optional[str]:
    """从 Set-Cookie 列表里提取指定 name 的 value，跳过过期/清空项。"""
    for header in set_cookie_headers:
        head, _, attrs = header.partition(";")
        if "=" not in head:
            continue
        n, _, v = head.partition("=")
        if n.strip() != name or not v.strip():
            continue
        if "Expires=Thu, 01 Jan 1970" in attrs:
            continue
        return v.strip()
    return None


RENEW_THROTTLE_SECONDS = 30 * 60  # 30 分钟内不重复续期


def renew_skey(config_path: str | os.PathLike, force: bool = False) -> bool:
    """用现有 cookie 调用 /web/login/renewal 换新 skey；成功则写回配置。

    若 30 分钟内续过期则直接返回 True（节流）。
    """
    config = load_config(config_path)
    cookies = _cookies_from_config(config)
    if not cookies.get("wr_vid") or not cookies.get("wr_skey"):
        print("⚠️ 配置里没有 vid/skey，无法续期")
        return False

    if not force:
        last = config.get("last_renewed_at") or 0
        if isinstance(last, (int, float)) and time.time() - last < RENEW_THROTTLE_SECONDS:
            return True

    try:
        resp = requests.post(
            RENEWAL_URL,
            headers=DEFAULT_HEADERS,
            cookies=cookies,
            data=json.dumps({"rq": "%2Fweb%2Fbook%2Fread"}, separators=(",", ":")),
            timeout=10,
        )
    except Exception as exc:
        print(f"⚠️ skey 续期请求失败: {exc}")
        return False

    try:
        body = resp.json()
    except ValueError:
        body = {}

    if body.get("errCode") in (-2013, -12013):
        print(f"⚠️ skey 续期被拒（errCode={body.get('errCode')}），需要扫码重新登录")
        return False

    # 优先用 requests 自己解析的 cookie jar，避免手切 Set-Cookie 字符串里日期带逗号的坑
    new_skey = resp.cookies.get("wr_skey")
    new_rt = resp.cookies.get("wr_rt")
    new_vid = resp.cookies.get("wr_vid")

    if not new_skey and hasattr(resp.raw, "headers") and hasattr(resp.raw.headers, "getlist"):
        headers_list = resp.raw.headers.getlist("Set-Cookie")
        new_skey = _extract_cookie(headers_list, "wr_skey")
        new_rt = new_rt or _extract_cookie(headers_list, "wr_rt")
        new_vid = new_vid or _extract_cookie(headers_list, "wr_vid")

    if not new_skey:
        if resp.status_code == 200 and body.get("succ") == 1:
            config["last_renewed_at"] = int(time.time())
            save_config(config_path, config)
            return True
        print(f"⚠️ skey 续期未返回新 skey，status={resp.status_code} body={body}")
        return False

    config["skey"] = new_skey
    if new_rt:
        config["rt"] = new_rt
    if new_vid:
        config["vid"] = new_vid
    config["last_renewed_at"] = int(time.time())
    save_config(config_path, config)
    print(f"✅ skey 已续期: {new_skey[:6]}…")
    return True


def _render_qr_terminal(text: str, output_dir: str | os.PathLike | None = None) -> Path:
    try:
        import qrcode  # type: ignore
    except ImportError:
        print("❌ 缺少 qrcode 包，请先 `pip install qrcode` 后再扫码登录")
        raise

    qr = qrcode.QRCode(border=1)
    qr.add_data(text)
    qr.make(fit=True)

    qr_output_dir = Path(output_dir) if output_dir else Path(__file__).resolve().parent.parent / "output" / "login_qr"
    qr_path = qr_output_dir / f"weread-login-{int(time.time())}.png"

    try:
        qr_output_dir.mkdir(parents=True, exist_ok=True)
        img = qr.make_image()
        img.save(qr_path)
    except Exception as exc:
        print(f"⚠️ 二维码 PNG 保存失败（不影响终端扫码）: {exc}")
    else:
        print(f"  二维码图片已保存到：{qr_path}")
        print(f"  MEDIA:{qr_path}")
        print("  如果你是通过 Agent / Hermes 调用这个 skill，可以把上面的 PNG 路径作为图片发回对话框。")

    print()
    print("  请用微信扫码登录（终端可能需要拉宽窗口）：")
    print()
    qr.print_ascii(invert=True)
    print()
    print(f"  如果终端无法扫码，请把这个 URL 用手机微信打开：\n  {text}\n")
    return qr_path


def qr_login(config_path: str | os.PathLike, timeout_seconds: int = 180) -> bool:
    """扫码登录流程。成功则把 vid/skey/rt 写回配置。"""
    config = load_config(config_path)
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    try:
        uid_resp = session.post(GETUID_URL, json={}, timeout=10).json()
    except Exception as exc:
        print(f"❌ 获取登录 uid 失败: {exc}")
        return False

    uid = uid_resp.get("uid")
    if not uid:
        print(f"❌ /web/login/getuid 未返回 uid: {uid_resp}")
        return False

    confirm_url = f"{WEREAD_ORIGIN}/web/confirm?pf=2&uid={uid}"
    _render_qr_terminal(confirm_url)

    deadline = time.time() + timeout_seconds
    info: dict = {}
    fatal_codes = {-2010, -2012, -2013, -12013}
    while time.time() < deadline:
        try:
            info = session.post(GETINFO_URL, json={"uid": uid}, timeout=10).json()
        except Exception:
            info = {}
        if info.get("vid") and info.get("accessToken"):
            break
        err = info.get("errCode") if isinstance(info, dict) else None
        if err in fatal_codes:
            print(f"\n❌ 扫码登录失败 errCode={err} errMsg={info.get('errMsg', '')}")
            return False
        sys.stdout.write("  …等待扫码确认\r")
        sys.stdout.flush()
        time.sleep(2)
    else:
        print("\n❌ 扫码超时，请重试")
        return False

    print("\n✅ 扫码确认成功，正在保存登录态…")

    vid = str(info["vid"])
    skey = info["accessToken"]
    rt = info.get("refreshToken", "")

    # session/init 是网页端登录后的常规步骤，跑一下让服务端记录会话
    try:
        session.post(
            SESSION_INIT_URL,
            json={"vid": vid, "pf": 0, "skey": skey, "rt": rt},
            timeout=10,
        )
    except Exception as exc:
        print(f"⚠️ session/init 调用失败（不致命）: {exc}")

    config["vid"] = vid
    config["skey"] = skey
    if rt:
        config["rt"] = rt
    config["last_renewed_at"] = int(time.time())
    save_config(config_path, config)
    print(f"✅ 登录态已写回 {config_path}")
    return True


def ensure_auth(config_path: str | os.PathLike, force_qr: bool = False) -> bool:
    """主入口：先续期，失败则扫码兜底。"""
    if not force_qr and renew_skey(config_path):
        return True
    print("➡️ 进入扫码登录兜底流程")
    return qr_login(config_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="微信读书鉴权工具")
    parser.add_argument("--config", "-c", default=str(Path(__file__).resolve().parent.parent / "config" / "weread.json"))
    parser.add_argument("--qr", action="store_true", help="跳过续期，直接扫码登录")
    args = parser.parse_args()

    ok = ensure_auth(args.config, force_qr=args.qr)
    sys.exit(0 if ok else 1)
