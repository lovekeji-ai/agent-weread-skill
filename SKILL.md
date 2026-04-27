---
name: agent-weread-skill
description: 自动导出微信读书笔记，支持 Markdown/JSON 格式，可同步到 Obsidian
homepage: https://github.com/lovekeji-ai/agent-weread-skill
metadata: {"openclaw":{"emoji":"📚","requires":{"bins":["python3"]},"install":[{"id":"pip","kind":"pip","packages":["requests","beautifulsoup4","qrcode","Pillow"],"label":"安装 Python 依赖"}]}}
---

# 微信读书笔记导出 Skill

把微信读书里的划线、想法、书评导出成 Markdown / JSON，可选同步到 Obsidian。skey 会自动续期，过期了走扫码兜底。

## 启动流程（每次被触发时按顺序执行）

Agent 被触发后**先静默执行 preflight**（不要列菜单、不要先问用户做什么）。根据 preflight 结果走不同分支。

### Preflight（静默，不输出过程）

1. 读 `config/weread.json`（不存在时 `weread_auth.py` 会自动从 template 复制一份，无需手动 cp）：
   - `vid` 或 `skey` 为空 → **未初始化**，走「初始化向导」从 Step 1 开始
   - 否则继续
2. 跑 `python scripts/weread_auth.py`（自动续期）：
   - exit 1 → skey 过期/被拒 → 走「初始化向导」从 Step 1 开始
   - exit 0 → 登录态有效，进入第 3 步
3. 检查 `output_dir` 是否是真实路径：
   - 为空 / 仍是 template 的占位符（`/root/workspace/weread-notes`）→ 走「初始化向导」**只跑 Step 2**：`python scripts/weread_init.py --skip-login`
   - 否则 → 走「已就绪」分支

### 初始化向导（分步执行，每一步等用户确认后再进下一步）

**Step 1 · 登录 + 接续初始化**
- 提示用户：「首次使用需要扫码登录微信读书」
- 跑 `python scripts/weread_init.py`
- 这个向导会先完成扫码登录；扫码成功后不会停住，而是自动进入下一步继续配置 `output_dir`
- 如果调用方已经知道输出目录，也可以直接跑 `python scripts/weread_init.py --output-dir <PATH>` 跳过提问
- 失败则停在这一步报错，不要往下走

**Step 2 · 配置输出目录**
- 如果上一步没传 `--output-dir`，向导会直接继续问用户：「笔记导出到哪？默认 `~/Documents/weread`，回车采用默认，或直接告诉我别的路径」
- 拿到路径后展开 `~`、写入 `config/weread.json` 的 `output_dir`，必要时 `mkdir -p`
- 写完确认一下："输出目录已设为 X"

初始化完成后转「已就绪」分支。

### 已就绪分支

简短一句话报状态（**不要列菜单**），然后告诉用户可以用哪些自然语言指令：

> ✅ 登录态正常，输出目录：`<output_dir>`
>
> 可以这样跟我说：
> - "导出全部微信读书笔记"
> - "导出最近一周笔记" / "导出最近 30 天笔记"
> - "导出《书名》的笔记"
> - "看一下微信读书统计"
> - "重新登录 / 换账号"

用户说「重新登录 / 换账号」→ 直接跑 Step 1。

## 自然语言触发

对 Agent 这样说：

- 导出微信读书笔记
- 导出最近一周微信读书笔记
- 导出最近 30 天微信读书笔记
- 导出《打造第二大脑》的微信读书笔记
- 查看微信读书统计

## 命令行

```bash
python scripts/weread_export.py --all          # 全部带笔记的书
python scripts/weread_export.py --this-week    # 全量同步 + 最近 7 天 digest
python scripts/weread_export.py --days 30      # 全量同步 + 最近 N 天 digest
python scripts/weread_export.py --book "书名"
python scripts/weread_export.py --stats
python scripts/weread_export.py --login        # 强制扫码登录
```

`--max-books N` 控制单次最多拉取的书籍数（默认 50），sort-skip 跳过的不算。

## 增量与状态

skill 在 `output/.state/synced.json` 维护每本书的 `sort` 和已同步的 bookmark/review id 集合：

- **per-book 文件永远写全量内容**：`output/《书名》.md` 是当前最新副本，不会被时间窗口截断
- **sort-skip**：notebook 接口的 `sort` 没变 + 文件已存在 → 直接跳过，不调 bookmarklist/reviewlist
- **digest 增量**：传 `--this-week` / `--days N` 时，额外把"自上次同步以来 + 时间窗内"的新条目写到 `output/digest/digest-last-Nd-YYYY-MM-DD.md`
- **首次跑节流**：单次最多拉 50 本（含 pacing 0.3-0.8s 抖动），首次跑库存大的用户多跑几次即可，每次都不会触发风控级别的 QPS

## 鉴权

第一次推荐直接跑 `python scripts/weread_init.py`。这个初始化向导会先自动完成扫码登录，再继续配置 `output_dir`；如果你已经知道目录，也可以用 `python scripts/weread_init.py --output-dir <PATH>` 一步写好。只想单独重登时，再跑 `python scripts/weread_auth.py --qr`。扫码时会同时输出终端 ASCII 二维码和 PNG 文件路径（含 `MEDIA:` 行），方便 Agent / Hermes 把二维码图片发回对话框。

之后每次导出会自动调微信读书的 `/web/login/renewal` 续期 `wr_skey`（30 分钟内会节流跳过），续期失败时自动转 QR 扫码。

## 微信读书接口（2026-04 实测）

| 用途 | 路径 |
| --- | --- |
| 书架 | `/web/shelf/sync` |
| 有笔记书籍列表 | `/api/user/notebook` |
| 划线 | `/web/book/bookmarklist` |
| 书评 / 想法 | `/web/review/list` |
| skey 续期 | `/web/login/renewal` |
| 扫码登录 | `/web/login/getuid` + `/web/login/getinfo` |

旧的 `/web/book/bookShelf` 和 `/web/book/reviewlist` 已 404。

## 鸣谢

- [blessonism/weread2flomo](https://github.com/blessonism/weread2flomo) — 最近 N 天过滤、`createTime` 筛选思路
- [Dawn11111/weread2notion-pro](https://github.com/Dawn11111/weread2notion-pro) — 新版接口组合、Cookie 处理参考
- [MoonstoneF/WeRead2CraftCollection](https://github.com/MoonstoneF/WeRead2CraftCollection) — `/web/review/list` 参数参考
- [88825/wereadx](https://github.com/88825/wereadx) — `/web/login/renewal` + 扫码登录流程参考
- [openclaw/skills](https://github.com/openclaw/skills) — skill 结构参考
