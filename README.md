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

依赖只有两个 Python 包，Agent 第一次调用时会按 `SKILL.md` 里的声明自动装上：

```bash
pip install requests beautifulsoup4
```

## 一次性配置：登录

第一次用先建配置文件：

```bash
cp config/weread.json.template config/weread.json
```

把 `output_dir` 改成你想要的输出目录；要同步到 Obsidian 就把 `sync_to_obsidian` 设为 `true` 并填 `obsidian_dir`。

然后扫码登录一次（终端会渲染 QR，用微信扫一下）：

```bash
python scripts/weread_auth.py --qr
```

之后 `vid / skey / rt` 会自动写回 `config/weread.json`。

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
python scripts/weread_export.py --this-week    # 最近 7 天新增
python scripts/weread_export.py --days 30      # 最近 N 天新增
python scripts/weread_export.py --book "书名"
python scripts/weread_export.py --stats
```

「最近 N 天」按每条笔记的 `createTime` 过滤，没有就是 0，不会编结果。

## 隐私

`config/weread.json`、`output/`、`.venv/` 都已在 `.gitignore` 里。`wr_vid` 和 `wr_skey` 是你的认证凭证，别提交到公开仓库。

## 鸣谢

接口适配和筛选思路参考了：
[weread2flomo](https://github.com/blessonism/weread2flomo)、
[weread2notion-pro](https://github.com/Dawn11111/weread2notion-pro)、
[WeRead2CraftCollection](https://github.com/MoonstoneF/WeRead2CraftCollection)、
[openclaw/skills](https://github.com/openclaw/skills)。
