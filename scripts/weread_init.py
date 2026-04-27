#!/usr/bin/env python3
"""微信读书初始化向导：扫码登录后继续配置输出目录。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from weread_auth import load_config, qr_login, save_config  # noqa: E402


DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "weread"
_TEMPLATE_OUTPUT_DIRS = {
    "/root/workspace/weread-notes",
    str(DEFAULT_OUTPUT_DIR),
}


def _expand_path(value: str) -> str:
    return str(Path(value).expanduser().resolve())


def _suggest_output_dir(config: dict) -> str:
    current = str(config.get("output_dir") or "").strip()
    if not current or current in _TEMPLATE_OUTPUT_DIRS:
        return str(DEFAULT_OUTPUT_DIR)
    return _expand_path(current)


def configure_output_dir(config_path: str | Path, output_dir: str | None = None, input_fn=None, print_fn=None) -> str | None:
    if input_fn is None:
        input_fn = input
    if print_fn is None:
        print_fn = print

    try:
        config = load_config(config_path)
    except Exception as exc:
        print_fn(f"❌ 配置读取失败：{exc}")
        return None
    suggested = _suggest_output_dir(config)

    if output_dir is None:
        prompt = f"笔记导出到哪？直接回车采用默认值 [{suggested}]："
        entered = input_fn(prompt).strip()
        chosen = entered or suggested
    else:
        chosen = output_dir

    resolved = _expand_path(chosen)
    try:
        Path(resolved).mkdir(parents=True, exist_ok=True)
        config["output_dir"] = resolved
        save_config(config_path, config)
    except Exception as exc:
        print_fn(f"❌ 输出目录写入失败：{exc}")
        return None

    print_fn(f"✅ 输出目录已设为：{resolved}")
    return resolved


def run_init_wizard(config_path: str | Path, output_dir: str | None = None, skip_login: bool = False, input_fn=None, print_fn=None) -> bool:
    if input_fn is None:
        input_fn = input
    if print_fn is None:
        print_fn = print

    if skip_login:
        print_fn("➡️ 跳过扫码登录，直接配置导出目录")
    else:
        print_fn("➡️ 开始微信读书初始化：先扫码登录，再配置导出目录")
        if not qr_login(config_path):
            return False
    resolved = configure_output_dir(config_path, output_dir=output_dir, input_fn=input_fn, print_fn=print_fn)
    if not resolved:
        return False
    print_fn("✅ 初始化完成，可以开始导出微信读书笔记了")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="微信读书初始化向导")
    parser.add_argument("--config", "-c", default=str(SCRIPT_DIR.parent / "config" / "weread.json"))
    parser.add_argument("--output-dir", help="直接写入输出目录，跳过交互提问")
    parser.add_argument("--skip-login", action="store_true", help="skey 仍有效时跳过扫码，只走 output_dir 这一步")
    args = parser.parse_args()

    ok = run_init_wizard(args.config, output_dir=args.output_dir, skip_login=args.skip_login)
    raise SystemExit(0 if ok else 1)
