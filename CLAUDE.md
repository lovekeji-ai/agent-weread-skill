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

Three modules under `scripts/`:

- **`weread_export.py`** — main CLI; `WeReadExporter` orchestrates fetching, rendering, and writing.
- **`weread_auth.py`** — skey renewal via `/web/login/renewal` (30-min throttle) + QR-scan fallback via `/web/login/getuid` + `/web/login/getinfo`. Called from `main()` before any export, and again on `AuthExpired` raised mid-flight.
- **`weread_state.py`** — single-JSON state at `output/.state/synced.json`. Per-book record: `{title, sort, synced_bookmark_ids, synced_review_ids, last_synced_at}`.

**Sync semantics:**
- per-book file (`output/《title》.md`) **always written with full current content** — idempotent, can't be truncated by time-window flags.
- **sort-skip**: if `notebook.sort == state.sort` AND the per-book file already exists, skip — no `bookmarklist`/`reviewlist` call. Free.
- **per-run cap**: `--max-books N` (default 50) limits how many books actually get fetched in one invocation. sort-skipped books don't count. Combined with 0.3-0.8s jittered sleep between fetches, this keeps QPS well under any plausible WeRead anti-bot threshold even on first-run users with 500+ books — they just need to run the command a few times.
- **digest**: when `--this-week` / `--days N` is set, additionally write `output/digest/digest-last-Nd-YYYY-MM-DD.md` with items that are (a) inside the time window AND (b) not present in `state.synced_bookmark_ids` / `synced_review_ids`. The state set is the authoritative "already-seen" record, equivalent to weread2flomo's `synced_ids` set but scoped per book.

**Auth flow:**
- `_api_request` raises `AuthExpired` on HTTP 401/403 or known auth errCodes (`-2010 / -2012 / -2013 / -12013`).
- Top-level `main()` catches `AuthExpired`, runs `qr_login`, rebuilds the exporter, retries once.
- The per-book except in `export_all` re-raises `AuthExpired` rather than swallowing it, so mid-flight token expiry triggers the retry.

**API compatibility note**: The old endpoints `/web/book/bookShelf` and `/web/book/reviewlist` are deprecated (return 404). The notebook API (`/api/user/notebook`) returns books nested under a `book` field; `_book_payload()` flattens this.

## Python Environment

Uses Python 3.14 via Homebrew. A `.venv/` is present locally. The script auto-detects LibreSSL on macOS and re-execs itself under the venv Python to avoid SSL issues — do not remove this bootstrap block.
