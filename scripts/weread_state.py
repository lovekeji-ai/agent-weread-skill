"""本地同步状态：记录每本书已同步的 bookmark/review id 和 last sort。

用途：
- sort-skip：notebook 接口返回的 sort 跟本地相同时，跳过 bookmarklist/reviewlist 调用
- digest 增量：判断"自上次同步以来真正新增了哪些 id"
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

STATE_SCHEMA = 1


class State:
    """单文件 JSON 状态。线程不安全，单进程使用。"""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.data: dict = {"schema": STATE_SCHEMA, "books": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict) and isinstance(loaded.get("books"), dict):
                self.data = loaded
                self.data.setdefault("schema", STATE_SCHEMA)
        except Exception as exc:
            print(f"⚠️ 状态文件读取失败，将重新初始化: {exc}")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    # --- per-book ----------------------------------------------------------
    def get_book(self, book_id: str) -> dict:
        return self.data["books"].get(str(book_id), {}) or {}

    def get_sort(self, book_id: str) -> int:
        return int(self.get_book(book_id).get("sort") or 0)

    def get_synced_bookmark_ids(self, book_id: str) -> set[str]:
        return set(self.get_book(book_id).get("synced_bookmark_ids") or [])

    def get_synced_review_ids(self, book_id: str) -> set[str]:
        return set(self.get_book(book_id).get("synced_review_ids") or [])

    def update_book(
        self,
        book_id: str,
        *,
        title: str,
        sort: int,
        bookmark_ids: list[str],
        review_ids: list[str],
    ) -> None:
        self.data["books"][str(book_id)] = {
            "title": title,
            "sort": int(sort or 0),
            "synced_bookmark_ids": sorted(set(bookmark_ids)),
            "synced_review_ids": sorted(set(review_ids)),
            "last_synced_at": int(time.time()),
        }


def default_state_path(output_dir: str | os.PathLike) -> Path:
    return Path(output_dir) / ".state" / "synced.json"
