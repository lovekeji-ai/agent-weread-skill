# agent-weread-skill

一个让 Agent / Hermes 帮你导出微信读书笔记的 skill。

装好之后，直接对 Agent 说：

- 导出微信读书笔记
- 导出最近一周微信读书笔记
- 导出《打造第二大脑》的微信读书笔记
- 查看微信读书统计

它会把你的划线、想法、书评导出成 Markdown 或 JSON，可选同步到 Obsidian。

## 安装

把这个仓库放进你 Agent 的 skills 目录即可。它会被识别为名为 `agent-weread-skill` 的 skill（见 `SKILL.md`）。

依赖会按 `SKILL.md` 里的声明自动装上：

```bash
pip install requests beautifulsoup4 qrcode Pillow
```

## 一次性配置：初始化向导

第一次用直接运行初始化向导：

```bash
python scripts/weread_init.py
```

它会自动完成两步：
1. 弹出扫码登录（终端 ASCII + PNG 二维码，方便 Agent / Hermes 直接发回对话框）
2. 扫码成功后继续询问并写入 `output_dir`

如果你已经知道输出目录，也可以一次性带上：

```bash
python scripts/weread_init.py --output-dir ~/Documents/weread
```

初始化成功后，`vid / skey / rt` 和 `output_dir` 都会写回 `config/weread.json`。

> 也可以从浏览器直接复制 `wr_vid / wr_skey / wr_rt` 三个 cookie 手填到配置里，但推荐扫码，省得过期了再翻一次 F12。

## skey 会自动续期

每次跑导出之前，skill 会先调一次微信读书的 `/web/login/renewal` 把 `wr_skey` 续期，所以你**不用再定期手动重取 cookie**。续期失败（`wr_rt` 也过期了）时，会自动弹出 QR 让你重扫一次。

如果只想刷新登录态、不导出：

```bash
python scripts/weread_auth.py        # 续期，失败自动转 QR
python scripts/weread_auth.py --qr   # 跳过续期，直接扫码
```

## 使用

正常情况下你不用碰命令行，对 Agent 说一句中文就行。

如果想手动跑：

```bash
python scripts/weread_export.py --all          # 全部有笔记的书
python scripts/weread_export.py --this-week    # 全量同步 + 最近 7 天 digest
python scripts/weread_export.py --days 30      # 全量同步 + 最近 N 天 digest
python scripts/weread_export.py --book "书名"
python scripts/weread_export.py --stats
```

## 增量同步

第一次跑会一本一本拉，**单次最多 50 本**（带 0.3-0.8s 抖动延迟），库存大的用户跑几次就把基线建完了。

之后再跑会用 notebook 接口返回的 `sort` 字段做 sort-skip——没动过的书直接跳过不拉接口，**日常每次只拉本期更新过的几本**，请求数和耗时都很小，也不容易撞风控。

每本书在本地 `output/` 下永远是一份当前完整的 markdown，不会被 `--this-week` 截短。`--this-week` / `--days N` 会额外在 `output/digest/` 里写一份"自上次同步以来 + 在时间窗内"的新增 digest。

状态记录在 `output/.state/synced.json`，删掉就等于"忘掉所有同步历史，下次重新走一次基线"。

## 隐私

`config/weread.json`、`output/`、`.venv/` 都已在 `.gitignore` 里。`wr_vid` 和 `wr_skey` 是你的认证凭证，别提交到公开仓库。

## 鸣谢

接口适配和筛选思路参考了：
[weread2flomo](https://github.com/blessonism/weread2flomo)、
[weread2notion-pro](https://github.com/Dawn11111/weread2notion-pro)、
[WeRead2CraftCollection](https://github.com/MoonstoneF/WeRead2CraftCollection)、
[openclaw/skills](https://github.com/openclaw/skills)。
