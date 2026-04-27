# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a WeChat Reading (微信读书) note export skill for Agent/Hermes. Users instruct an Agent to export highlights, thoughts, and book reviews from WeChat Reading to Markdown or JSON, with optional Obsidian vault sync.

## Running the Script

```bash
# Install dependencies
pip install requests beautifulsoup4

# Export all books with notes
python scripts/weread_export.py --all

# Export notes from the past N days
python scripts/weread_export.py --days 7

# Export a specific book
python scripts/weread_export.py --book "书名"

# Show reading statistics
python scripts/weread_export.py --stats
```

There are no build, lint, or test commands — this is a single-file CLI script.

## Configuration

Copy `config/weread.json.template` to `config/weread.json` and fill in `vid` and `skey` from WeChat Reading browser cookies (`wr_vid` and `wr_skey`). The live config file is gitignored.

Key config options: `output_format` (markdown/json), `output_dir`, `sync_to_obsidian`, `obsidian_dir`, and per-export toggles (`export_highlights`, `export_thoughts`, `export_reviews`).

## Architecture

All logic lives in **`scripts/weread_export.py`** — a single-file script with no external framework.

**`WeReadExporter` class** is the core:
- Authenticates via `wr_vid`/`wr_skey` cookies in request headers
- Fetches books with notes from `/api/user/notebook` (preferred; avoids books with no annotations)
- Fetches highlights from `/web/book/bookmarklist` and reviews from `/web/review/list`
- Filters by `createTime` timestamp when a time window (`--days`) is specified
- Exports via `_export_markdown()` or `_export_json()`, writes to `output_dir`
- Optionally syncs output files to an Obsidian vault via `shutil.copy2()`

**API compatibility note**: The old endpoints `/web/book/bookShelf` and `/web/book/reviewlist` are deprecated (return 404). The notebook API (`/api/user/notebook`) returns books under a nested `book` field — this is handled by `_book_payload()`.

## Python Environment

Uses Python 3.14 via Homebrew. A `.venv/` is present locally. The script auto-detects LibreSSL on macOS and re-execs itself under the venv Python to avoid SSL issues — do not remove this bootstrap block.
