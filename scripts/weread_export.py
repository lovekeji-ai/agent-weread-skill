#!/usr/bin/env python3
"""
微信读书笔记导出工具
自动导出标注、想法、书评
"""

import json
import os
import random
import re
import shutil
import ssl
import sys
import time
import argparse
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path


def _bootstrap_preferred_python():
    """在 macOS 系统 Python + LibreSSL 环境下，自动切换到 skill 本地 venv。"""
    current_ssl = getattr(ssl, 'OPENSSL_VERSION', '')
    if 'LibreSSL' not in current_ssl:
        return

    if os.environ.get('WEREAD_EXPORT_VENV_BOOTSTRAPPED') == '1':
        return

    script_path = Path(__file__).resolve()
    preferred_python = script_path.parent.parent / '.venv' / 'bin' / 'python'
    if not preferred_python.exists():
        return

    current_python = Path(sys.executable).resolve()
    if current_python == preferred_python.resolve():
        return

    env = os.environ.copy()
    env['WEREAD_EXPORT_VENV_BOOTSTRAPPED'] = '1'
    os.execve(str(preferred_python), [str(preferred_python), str(script_path), *sys.argv[1:]], env)


_bootstrap_preferred_python()

import requests

from weread_auth import ensure_auth, qr_login
from weread_state import State, default_state_path


DEFAULT_MAX_BOOKS_PER_RUN = 50
PACING_RANGE = (0.3, 0.8)  # 每本书之间的随机延迟（秒），降低风控概率


class AuthExpired(Exception):
    """微信读书 cookie 失效，需要重新鉴权。"""


class WeReadExporter:
    """微信读书导出器"""

    SHELF_SYNC_URL = 'https://weread.qq.com/web/shelf/sync'
    NOTEBOOK_URL = 'https://weread.qq.com/api/user/notebook'
    BOOK_INFO_URL = 'https://weread.qq.com/api/book/info'
    BOOKMARK_LIST_URL = 'https://weread.qq.com/web/book/bookmarklist'
    REVIEW_LIST_URL = 'https://weread.qq.com/web/review/list'

    def __init__(self, config_path=None):
        self.config_path = self._resolve_config_path(config_path)
        self.config = self._load_config(self.config_path)
        self.vid = self.config.get('vid')
        self.skey = self.config.get('skey')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://weread.qq.com/',
            'Origin': 'https://weread.qq.com',
        })

        if not self.vid or not self.skey:
            raise ValueError("Missing vid or skey in config")
    
    @staticmethod
    def _resolve_config_path(config_path):
        if config_path:
            return os.path.abspath(config_path)
        return str(Path(__file__).resolve().parent.parent / 'config' / 'weread.json')

    def _load_config(self, config_path):
        """加载配置"""
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 默认配置
        return {
            'output_format': 'markdown',
            'output_dir': '/root/workspace/weread-notes',
            'sync_to_obsidian': False,
            'export_highlights': True,
            'export_thoughts': True,
            'export_reviews': True
        }
    
    def _api_request(self, url, params=None):
        """发送 API 请求"""
        cookies = {
            'wr_vid': self.vid,
            'wr_skey': self.skey,
        }
        if self.config.get('rt'):
            cookies['wr_rt'] = self.config['rt']

        try:
            response = self.session.get(url, cookies=cookies, params=params, timeout=30)
        except Exception as e:
            print(f"❌ API 请求失败: {e}")
            return None

        if response.status_code in (401, 403):
            raise AuthExpired(f"HTTP {response.status_code} on {url}")

        try:
            data = response.json()
        except ValueError:
            print(f"❌ API 返回非 JSON，status={response.status_code}")
            return None

        err_code = data.get('errCode') if isinstance(data, dict) else None
        if err_code in (-2010, -2012, -2013, -12013):
            raise AuthExpired(f"errCode={err_code} on {url}")

        return data
    
    def _get_shelf_data(self):
        """获取完整书架数据"""
        return self._api_request(self.SHELF_SYNC_URL, params={
            'synckey': 0,
            'teenmode': 0,
            'album': 1,
            'onlyBookid': 0,
        }) or {}

    def get_bookshelf(self):
        """获取书架列表"""
        data = self._get_shelf_data()

        if 'books' in data:
            return data['books']
        return []

    def get_notebook_books(self):
        """获取有笔记/划线的书籍列表"""
        data = self._api_request(self.NOTEBOOK_URL)
        if data and 'books' in data:
            return data['books']
        return []
    
    def get_book_info(self, book_id):
        """获取书籍信息"""
        return self._api_request(self.BOOK_INFO_URL, params={'bookId': book_id})
    
    def get_highlights(self, book_id):
        """获取书籍标注"""
        data = self._api_request(self.BOOKMARK_LIST_URL, params={'bookId': book_id})
        
        if data and 'updated' in data:
            return data['updated']
        return []
    
    def get_reviews(self, book_id):
        """获取书评/想法"""
        data = self._api_request(self.REVIEW_LIST_URL, params={
            'bookId': book_id,
            'listType': 11,
            'syncKey': 0,
            'mine': 1,
        })
        
        if data and 'reviews' in data:
            return [item.get('review', item) for item in data['reviews']]
        return []
    
    def _book_payload(self, book):
        """兼容书架接口和 notebook 接口的书籍结构"""
        if isinstance(book, dict) and isinstance(book.get('book'), dict):
            payload = dict(book['book'])
            payload.setdefault('bookId', book.get('bookId'))
            payload.setdefault('noteCount', book.get('noteCount', 0))
            payload.setdefault('reviewCount', book.get('reviewCount', 0))
            payload.setdefault('sort', book.get('sort'))
            return payload
        return book or {}

    @staticmethod
    def _safe_filename(name, fallback='Untitled'):
        """清理跨平台不安全字符；避免隐藏文件、空名、超长名。"""
        if not name:
            return fallback
        cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '-', name).strip().strip('.')
        cleaned = re.sub(r'\s+', ' ', cleaned)
        if not cleaned:
            return fallback
        return cleaned[:120]

    def _is_within_days(self, item, since_days=None):
        """按 createTime 过滤最近 N 天的数据；无 createTime 时保留。"""
        if not since_days or since_days <= 0:
            return True

        create_time = item.get('createTime', 0) if isinstance(item, dict) else 0
        if not create_time:
            return True

        try:
            item_date = datetime.fromtimestamp(create_time)
        except Exception:
            return True

        cutoff_date = datetime.now() - timedelta(days=since_days)
        return item_date >= cutoff_date

    def _filter_items_by_days(self, items, since_days=None):
        return [item for item in items if self._is_within_days(item, since_days)]

    def _render_book(self, book, highlights, reviews, format):
        if format == 'markdown':
            return self._export_markdown(book, highlights, reviews)
        if format == 'json':
            return self._export_json(book, highlights, reviews)
        raise ValueError(f"Unsupported format: {format}")

    def export_book(self, book, format='markdown'):
        """导出单本书籍：始终写全量内容。

        `since_days` 不再作用于 per-book 文件——文件永远是当前完整内容。
        """
        book = self._book_payload(book)
        book_id = book.get('bookId')
        title = book.get('title', 'Unknown')

        print(f"📖 正在导出: 《{title}》")

        highlights = self.get_highlights(book_id) if self.config.get('export_highlights') else []
        reviews = self.get_reviews(book_id) if self.config.get('export_reviews') else []

        return self._render_book(book, highlights, reviews, format)
    
    def _export_markdown(self, book, highlights, reviews):
        """导出为 Markdown"""
        title = book.get('title', 'Unknown')
        author = book.get('author', 'Unknown')
        cover = book.get('cover', '')
        
        md_content = f"""# 《{title}》

**作者**: {author}  
**导出时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

"""
        
        # 添加标注（按章节分组，章节内按 chapterIdx + range 自然排序）
        if highlights:
            md_content += "## 💡 标注\n\n"

            grouped = OrderedDict()
            for h in highlights:
                chapter = h.get('chapterTitle') or '未知章节'
                grouped.setdefault(chapter, []).append(h)

            def _sort_key(h):
                rng = h.get('range') or ''
                start = 0
                if isinstance(rng, str) and '-' in rng:
                    head, _, _ = rng.partition('-')
                    try:
                        start = int(head)
                    except ValueError:
                        start = 0
                return (h.get('chapterIdx') or 0, start, h.get('createTime') or 0)

            for chapter, items in grouped.items():
                md_content += f"### {chapter}\n\n"
                for h in sorted(items, key=_sort_key):
                    content = (h.get('markText') or '').strip()
                    thought = (h.get('thought') or '').strip()
                    if content:
                        md_content += f"> {content}\n\n"
                    if thought:
                        md_content += f"💭 **想法**: {thought}\n\n"
                md_content += "---\n\n"
        
        # 添加书评
        if reviews:
            md_content += "## 📝 书评\n\n"
            for r in reviews:
                content = r.get('content', '')
                md_content += f"{content}\n\n"
                md_content += "---\n\n"
        
        # 添加统计
        md_content += f"""## 📊 统计

- 总标注: {len(highlights)} 条
- 书评: {len(reviews)} 条
- 书籍 ID: {book.get('bookId')}
"""
        
        return md_content
    
    def _export_json(self, book, highlights, reviews):
        """导出为 JSON"""
        data = {
            'book_id': book.get('bookId'),
            'title': book.get('title'),
            'author': book.get('author'),
            'cover': book.get('cover'),
            'export_time': datetime.now().isoformat(),
            'highlights': highlights,
            'reviews': reviews,
            'stats': {
                'highlights_count': len(highlights),
                'reviews_count': len(reviews)
            }
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def export_all(self, format=None, output_dir=None, since_days=None, max_books=None):
        """导出所有有笔记的书籍。

        语义：
        - per-book 文件永远写全量内容（idempotent）
        - notebook.sort 没变 + 文件已存在 → sort-skip，不调 bookmarklist/reviewlist
        - 实际拉过的书数受 max_books 限制（默认 50），防止首次 N 本书暴拉触发风控
        - since_days 仅用于生成 digest 文件（output/digest/*.md），不影响 per-book 文件
        """
        format = format or self.config.get('output_format', 'markdown')
        output_dir = output_dir or self.config.get('output_dir', '/root/workspace/weread-notes')
        if max_books is None:
            max_books = self.config.get('max_books_per_run', DEFAULT_MAX_BOOKS_PER_RUN)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        state = State(default_state_path(output_dir))

        books = self.get_notebook_books()
        if not books:
            print("❌ 没有找到带笔记的书籍，请检查 Cookie 是否有效")
            return []

        cap_label = max_books if max_books else "∞"
        print(f"📚 notebook 接口返回 {len(books)} 本带笔记的书籍 · 单次拉取上限 {cap_label}")

        exported = []
        failed = []
        skipped = 0
        fetched = 0
        digest_buckets: "OrderedDict[str, tuple]" = OrderedDict()

        for book in books:
            normalized = self._book_payload(book)
            book_id = str(normalized.get('bookId') or '')
            title = normalized.get('title') or 'Unknown'
            current_sort = int(normalized.get('sort') or 0)
            prev_sort = state.get_sort(book_id)
            prev_bookmark_ids = state.get_synced_bookmark_ids(book_id)
            prev_review_ids = state.get_synced_review_ids(book_id)

            safe_title = self._safe_filename(title, fallback='Untitled')
            filename = f"{safe_title}.{format}"
            filepath = os.path.join(output_dir, filename)

            already_baseline = bool(prev_sort or prev_bookmark_ids or prev_review_ids)
            if already_baseline and prev_sort == current_sort and os.path.exists(filepath):
                skipped += 1
                continue

            if max_books and fetched >= max_books:
                remaining = len(books) - skipped - fetched
                print(f"⏸ 已达单次拉取上限 {max_books}；剩余 {remaining} 本下次再跑")
                break

            if fetched > 0:
                time.sleep(random.uniform(*PACING_RANGE))

            try:
                highlights = self.get_highlights(book_id) if self.config.get('export_highlights') else []
                reviews = self.get_reviews(book_id) if self.config.get('export_reviews') else []
            except AuthExpired:
                raise
            except Exception as e:
                print(f"  ❌ 拉取失败 《{title}》: {e}")
                failed.append(title)
                fetched += 1
                continue

            if since_days:
                new_h = [
                    h for h in highlights
                    if h.get('bookmarkId')
                    and h['bookmarkId'] not in prev_bookmark_ids
                    and self._is_within_days(h, since_days)
                ]
                new_r = [
                    r for r in reviews
                    if r.get('reviewId')
                    and r['reviewId'] not in prev_review_ids
                    and self._is_within_days(r, since_days)
                ]
                if new_h or new_r:
                    digest_buckets[book_id] = (normalized, new_h, new_r)

            try:
                content = self._render_book(normalized, highlights, reviews, format)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                exported.append({'title': title, 'filepath': filepath, 'format': format})
                print(f"  ✅ {filename} (划线 {len(highlights)} / 想法书评 {len(reviews)})")
            except Exception as e:
                print(f"  ❌ 写入失败 《{title}》: {e}")
                failed.append(title)
                fetched += 1
                continue

            state.update_book(
                book_id,
                title=title,
                sort=current_sort,
                bookmark_ids=[h.get('bookmarkId') for h in highlights if h.get('bookmarkId')],
                review_ids=[r.get('reviewId') for r in reviews if r.get('reviewId')],
            )
            fetched += 1

        state.save()

        print(f"\n📊 完成: 拉取 {fetched} · sort-skip {skipped} · 失败 {len(failed)}")

        if since_days:
            if digest_buckets:
                digest_path = self._write_digest(digest_buckets, output_dir, since_days)
                print(f"📰 digest 已写入: {digest_path}")
            else:
                print(f"📰 最近 {since_days} 天没有新增笔记")

        if self.config.get('sync_to_obsidian'):
            self._sync_to_obsidian(exported)

        return exported

    def _write_digest(self, buckets, output_dir, since_days):
        """把"自上次同步以来 + 在时间窗口内"的新条目写成一个 digest 文件。"""
        digest_dir = Path(output_dir) / 'digest'
        digest_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime('%Y-%m-%d')
        path = digest_dir / f"digest-last-{since_days}d-{today}.md"

        total_h = sum(len(hs) for _, hs, _ in buckets.values())
        total_r = sum(len(rs) for _, _, rs in buckets.values())

        md = f"# 微信读书最近 {since_days} 天新增 ({today})\n\n"
        md += f"涉及 {len(buckets)} 本书 · {total_h} 条标注 · {total_r} 条想法/书评\n\n---\n\n"

        for book_id, (book, hs, rs) in buckets.items():
            title = book.get('title') or '?'
            author = book.get('author') or ''
            md += f"## 《{title}》"
            if author:
                md += f" — {author}"
            md += "\n\n"

            if hs:
                grouped = OrderedDict()
                for h in hs:
                    chapter = h.get('chapterTitle') or '未知章节'
                    grouped.setdefault(chapter, []).append(h)
                md += "### 💡 新增标注\n\n"
                for chapter, items in grouped.items():
                    md += f"**{chapter}**\n\n"
                    for h in items:
                        text = (h.get('markText') or '').strip()
                        thought = (h.get('thought') or '').strip()
                        if text:
                            md += f"> {text}\n\n"
                        if thought:
                            md += f"💭 {thought}\n\n"

            if rs:
                md += "### 📝 新增想法/书评\n\n"
                for r in rs:
                    content = (r.get('content') or '').strip()
                    if content:
                        md += f"{content}\n\n---\n\n"

            md += "\n"

        with open(path, 'w', encoding='utf-8') as f:
            f.write(md)
        return path
    
    def _sync_to_obsidian(self, exported_files):
        """同步到 Obsidian"""
        obsidian_dir = self.config.get('obsidian_dir')
        if not obsidian_dir:
            return
        
        Path(obsidian_dir).mkdir(parents=True, exist_ok=True)

        print(f"\n🔄 同步到 Obsidian...")
        for item in exported_files:
            src = item['filepath']
            dst = os.path.join(obsidian_dir, os.path.basename(src))
            try:
                shutil.copy2(src, dst)
                print(f"  ✅ 已同步: {os.path.basename(src)}")
            except Exception as e:
                print(f"  ❌ 同步失败: {e}")
    
    def get_stats(self):
        """获取阅读统计"""
        shelf_data = self._get_shelf_data()
        books = shelf_data.get('books', [])
        progress_items = shelf_data.get('bookProgress', [])
        progress_by_book = {
            str(item.get('bookId')): item for item in progress_items if item.get('bookId')
        }
        
        total_books = len(books)
        finished_books = sum(1 for b in books if b.get('finishReading'))
        reading_books = sum(
            1 for b in books
            if not b.get('finishReading') and (progress_by_book.get(str(b.get('bookId')), {}).get('progress') or 0) > 0
        )
        
        # 统计书架同步返回的阅读时长（秒转分钟）
        total_read_time_seconds = sum((item.get('readingTime') or 0) for item in progress_items)
        
        stats = {
            'total_books': total_books,
            'finished': finished_books,
            'reading': reading_books,
            'total_read_time_minutes': total_read_time_seconds // 60,
            'export_time': datetime.now().isoformat()
        }
        
        return stats

def _run_action(args, exporter, days_window, parser):
    if args.stats:
        stats = exporter.get_stats()
        print("📊 阅读统计")
        print(f"  总书籍: {stats['total_books']}")
        print(f"  已读完: {stats['finished']}")
        print(f"  阅读中: {stats['reading']}")
        print(f"  总阅读时长: {stats['total_read_time_minutes']} 分钟")
        return

    if args.book:
        books = exporter.get_notebook_books()
        target = None
        for b in books:
            candidate = exporter._book_payload(b)
            if args.book in candidate.get('title', ''):
                target = candidate
                break

        if not target:
            print(f"❌ 未找到书籍: {args.book}")
            return

        content = exporter.export_book(target, args.format)
        if content is None:
            print(f"⚠️ 《{target['title']}》没有可导出的笔记")
            return

        output_dir = args.output or exporter.config.get('output_dir')
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        filename = f"{exporter._safe_filename(target.get('title'))}.{args.format}"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 已导出: {filepath}")
        if days_window:
            print(f"💡 提示：--book 始终写全量内容；要看最近 {days_window} 天的新增请去掉 --book 跑 --days {days_window}")
        return

    if args.all or args.this_week or args.last_day or args.days:
        exporter.export_all(
            format=args.format,
            output_dir=args.output,
            since_days=days_window,
            max_books=args.max_books,
        )
        return

    parser.print_help()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='微信读书笔记导出工具')
    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument('--all', action='store_true', help='导出所有书籍')
    parser.add_argument('--this-week', action='store_true', help='导出最近7天新增的笔记')
    parser.add_argument('--last-day', action='store_true', help='导出最近1天新增的笔记')
    parser.add_argument('--days', type=int, help='导出最近 N 天新增的笔记')
    parser.add_argument('--book', '-b', help='导出特定书籍')
    parser.add_argument('--format', '-f', default='markdown', choices=['markdown', 'json'], help='输出格式')
    parser.add_argument('--output', '-o', help='输出目录')
    parser.add_argument('--stats', action='store_true', help='显示阅读统计')
    parser.add_argument('--max-books', type=int, default=None,
                        help=f'单次最多拉取的书籍数（不含 sort-skip 跳过的），默认 {DEFAULT_MAX_BOOKS_PER_RUN}；传 0 表示不限')
    parser.add_argument('--login', action='store_true', help='跳过续期，直接扫码登录')
    parser.add_argument('--no-auto-renew', action='store_true', help='跳过自动续期 skey')

    args = parser.parse_args()

    days_window = args.days
    if days_window is None and args.last_day:
        days_window = 1
    if days_window is None and args.this_week:
        days_window = 7

    # --max-books 0 → 不限
    if args.max_books == 0:
        args.max_books = 0  # falsy in export_all → 解释为"无上限"

    config_path = WeReadExporter._resolve_config_path(args.config)

    try:
        if args.login:
            ok = qr_login(config_path)
            if not ok:
                sys.exit(1)
            if not (args.all or args.this_week or args.last_day or args.days or args.book or args.stats):
                return
        elif not args.no_auto_renew:
            ensure_auth(config_path)

        exporter = WeReadExporter(args.config)

        try:
            _run_action(args, exporter, days_window, parser)
        except AuthExpired as exc:
            print(f"⚠️ 检测到鉴权失效（{exc}），尝试扫码重登…")
            if not qr_login(config_path):
                sys.exit(1)
            exporter = WeReadExporter(args.config)
            _run_action(args, exporter, days_window, parser)

    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
