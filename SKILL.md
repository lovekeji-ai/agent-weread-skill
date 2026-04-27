---
name: agent-weread-skill
description: 自动导出微信读书笔记，支持 Markdown/JSON 格式，可同步到 Obsidian
homepage: https://github.com/lovekeji-ai/agent-weread-skill
metadata: {"openclaw":{"emoji":"📚","requires":{"bins":["python3"]},"install":[{"id":"pip","kind":"pip","packages":["requests","beautifulsoup4","qrcode"],"label":"安装 Python 依赖"}]}}
---

# 微信读书笔记导出 Skill

把微信读书里的划线、想法、书评导出成 Markdown / JSON，可选同步到 Obsidian。skey 会自动续期，过期了走扫码兜底。

## 启动流程（每次被触发时按顺序执行）

> Agent 被触发后，**先做登录态检查，再问用户要做什么**。不要一上来就让用户选导出动作。

1. **检查 `config/weread.json` 是否存在**
   - 不存在 / 仍是 template → 复制模板，提示「首次使用，需要扫码登录」，进入第 3 步
2. **检查并续期 skey**：跑 `python scripts/weread_auth.py`
   - exit 0 → 登录态有效（已续期或 30min 内续过），进入第 4 步
   - exit 1 → skey 过期、被拒或 cookie 缺失，进入第 3 步
3. **引导扫码登录**：跑 `python scripts/weread_auth.py --qr`
   - 终端会渲染二维码；提示用户「请用微信扫码并在手机上确认登录」
   - 成功后再回到第 4 步；失败则停下来报错，不要继续往下走
4. **登录态确认后**，再询问用户要执行哪个导出动作（全部 / 最近 N 天 / 指定书 / 统计）

> 用户明确说「重新登录 / 换账号」时，直接跳到第 3 步。

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

第一次跑前 `cp config/weread.json.template config/weread.json` 并填好 `output_dir`，然后跑一次 `python scripts/weread_auth.py --qr` 扫码登录。

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
