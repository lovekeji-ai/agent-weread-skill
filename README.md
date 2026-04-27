# agent-weread-skill

一个给 Agent / Hermes 用的微信读书笔记导出 skill。

它的目标不是“提供一堆源码给你研究”，而是让你能直接对 Agent 说：
- 导出微信读书笔记
- 导出最近一周微信读书笔记
- 导出最近 30 天的微信读书笔记
- 查看微信读书统计

然后把你的微信读书划线、想法、书评导出成 Markdown 或 JSON，必要时同步到 Obsidian。

## 这个 skill 适合什么时候用

适合你想做这些事的时候：
- 把微信读书里的划线和想法导出来长期保存
- 定期回收最近一天 / 一周 / 一个月的新笔记
- 同步到 Obsidian，进入你的知识库工作流
- 做阅读复盘、选题回顾、卡片整理

## 当前支持的能力

- 导出全部“有笔记的书”
- 导出最近 1 天新增笔记
- 导出最近 7 天新增笔记
- 导出最近 N 天新增笔记
- 导出指定书籍的笔记
- 输出 Markdown / JSON
- 查看阅读统计
- 可同步到 Obsidian

说明：
- “最近 N 天”是按每条笔记自己的 `createTime` 做过滤
- 不是按书籍更新时间估算
- 这个实现思路参考了 `weread2flomo`

## 你可以直接对 Agent 这样说

自然语言触发示例：
- 导出微信读书笔记
- 导出最近一天微信读书笔记
- 导出本周微信读书笔记
- 导出最近 30 天微信读书笔记
- 导出《打造第二大脑》的微信读书笔记
- 查看微信读书统计

## 第一次使用前要做什么

### 1）安装依赖

```bash
pip install requests beautifulsoup4
```

如果你在 Hermes 本地作为 skill 使用，推荐给这个仓库单独建一个 `.venv`。

### 2）准备微信读书 Cookie

1. 浏览器登录 https://weread.qq.com
2. 打开开发者工具（F12）
3. 找到 Application → Cookies
4. 复制两个值：
   - `wr_vid`
   - `wr_skey`

### 3）创建本地配置文件

基于模板复制：

```bash
cp config/weread.json.template config/weread.json
```

然后填写：
- `vid`
- `skey`
- `output_dir`
- `obsidian_dir`（如果你要同步到 Obsidian）

## 最常用的命令

```bash
# 导出全部有笔记的书
python scripts/weread_export.py --all

# 导出最近 1 天新增
python scripts/weread_export.py --last-day

# 导出最近 7 天新增
python scripts/weread_export.py --this-week

# 导出最近 30 天新增
python scripts/weread_export.py --days 30

# 导出指定书籍
python scripts/weread_export.py --book "书名"

# 查看阅读统计
python scripts/weread_export.py --stats
```

如果配置文件不在默认位置：

```bash
python scripts/weread_export.py --this-week --config config/weread.json
```

## 它会导出什么

这个 skill 会尝试导出：
- 划线 highlights
- 想法 / 书评 reviews

输出格式：
- Markdown
- JSON

默认更适合拿来做知识库沉淀的是 Markdown。

## 它会把内容写到哪里

由 `config/weread.json` 决定：
- `output_dir`：原始导出目录
- `obsidian_dir`：如果开启同步，复制到知识库的目录

## 当前接口兼容说明

微信读书旧接口里，常见的这些路径已经不可靠或会失效：
- `/web/book/bookShelf`
- `/web/book/reviewlist`

当前这个 skill 已按新版实测可用接口适配：
- `/web/shelf/sync`
- `/api/user/notebook`
- `/api/book/info`
- `/web/book/bookmarklist`
- `/web/review/list`

另外：
- `--all` 会优先从“有笔记的书”列表导出
- 不会傻傻扫描整张书架去生成大量空文件

## 隐私与安全

请不要把这些内容提交到公开仓库：
- `config/weread.json`
- `.venv/`
- `output/`

尤其是：
- `wr_vid`
- `wr_skey`

它们都属于你的私密认证信息。

## 常见问题

### 1）为什么导不出来？

最常见原因是：
- Cookie 过期
- `wr_skey` 失效
- `config/weread.json` 没填对

处理方式：
1. 重新登录微信读书网页版
2. 重新获取 `wr_vid` 和 `wr_skey`
3. 更新配置文件

### 2）为什么最近一周没有内容？

因为这个 skill 现在会严格按 `createTime` 过滤。
也就是说：
- 如果最近 7 天确实没新增笔记
- 那它就应该返回 0，而不是给你伪结果

### 3）为什么有些书没有导出？

因为默认是从“有笔记的书”列表出发。
如果一本书没有划线、没有想法、没有书评，它就不会被当成导出目标。

## 仓库结构

```text
agent-weread-skill/
├── SKILL.md
├── README.md
├── requirements.txt
├── scripts/
│   └── weread_export.py
└── config/
    └── weread.json.template
```

## 特别鸣谢

本项目在接口适配、最近 N 天筛选和脚本结构整理时，参考了这些开源项目：

- [blessonism/weread2flomo](https://github.com/blessonism/weread2flomo)
- [Dawn11111/weread2notion-pro](https://github.com/Dawn11111/weread2notion-pro)
- [MoonstoneF/WeRead2CraftCollection](https://github.com/MoonstoneF/WeRead2CraftCollection)
- [openclaw/skills](https://github.com/openclaw/skills)

## 仓库地址

https://github.com/lovekeji-ai/agent-weread-skill
