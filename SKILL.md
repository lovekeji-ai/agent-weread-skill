---
name: weread-export
description: 自动导出微信读书笔记，支持 Markdown/JSON 格式，可同步到 Obsidian
homepage: https://github.com/zhongyi-byte/openclaw-weread-skill
metadata: {"openclaw":{"emoji":"📚","requires":{"bins":["python3"]},"install":[{"id":"pip","kind":"pip","packages":["requests","beautifulsoup4"],"label":"安装 Python 依赖"}]}}
---

# 微信读书笔记导出 Skill

自动导出微信读书中的标注、想法、书评，支持多种格式输出和自动化同步。

## 功能特性

- 📖 **批量导出** - 一键导出所有书籍笔记
- 📝 **多格式支持** - Markdown / JSON / CSV
- 🔄 **自动同步** - 定时同步到 Obsidian
- 📊 **阅读统计** - 生成阅读数据报告
- 🔔 **完成通知** - Telegram 导出完成提醒
- ⏰ **定时任务** - 支持 Cron 定时自动导出

## 安装依赖

```bash
pip install requests beautifulsoup4
```

## 配置说明

### 1. 获取微信读书 Cookie

1. 浏览器登录 https://weread.qq.com
2. 按 F12 打开开发者工具
3. 选择 Application → Cookies
4. 复制以下值：
   - `wr_vid` (用户 ID)
   - `wr_skey` (会话密钥)

### 2. 配置文件

编辑 `config/weread.json`：

```json
{
  "vid": "你的_wr_vid",
  "skey": "你的_wr_skey",
  "output_format": "markdown",
  "output_dir": "/root/workspace/weread-notes",
  "sync_to_obsidian": true,
  "obsidian_dir": "/root/workspace/obsidian-sync/03_项目/微信读书笔记",
  "telegram_notify": true,
  "export_highlights": true,
  "export_thoughts": true,
  "export_reviews": true
}
```

## 使用方法

### 命令行

```bash
# 导出所有笔记
python scripts/weread_export.py --all

# 导出本周新增
python scripts/weread_export.py --this-week

# 导出特定书籍
python scripts/weread_export.py --book "书名"

# 同步到 Obsidian
python scripts/weread_export.py --sync

# 查看阅读统计
python scripts/weread_export.py --stats
```

### OpenClaw 集成

在对话中使用：

```
导出微信读书笔记
→ 执行批量导出并同步

导出本周微信读书笔记
→ 导出最近7天新增的笔记

查看微信读书统计
→ 显示阅读数据报告
```

## 输出格式

### Markdown 格式

```markdown
# 《书名》
**作者**: 作者名  
**阅读时间**: 2026-01-01 ~ 2026-02-01  
**阅读进度**: 100%

---

## 💡 标注

> 这是标注的内容
> 
> 📍 第 12 页 | 💭 想法：我的思考

## 📝 书评

我的书评内容...

## 📊 统计

- 总标注: 42 条
- 总想法: 15 条
- 阅读时长: 5小时 30分钟
```

### JSON 格式

```json
{
  "book_id": "book_123",
  "title": "书名",
  "author": "作者",
  "highlights": [
    {
      "chapter": "第一章",
      "content": "标注内容",
      "page": 12,
      "thought": "我的想法",
      "create_time": "2026-01-15T10:30:00"
    }
  ]
}
```

## 定时任务

### Cron 配置示例

```json
{
  "schedule": {
    "kind": "cron",
    "expr": "0 9 * * 0",
    "tz": "Asia/Shanghai"
  },
  "task": "weread-export --this-week --notify"
}
```

每周日凌晨 9 点自动导出本周笔记并发送通知。

## 文件结构

```
openclaw-weread-skill/
├── SKILL.md              # 本说明文件
├── README.md             # 详细文档
├── scripts/
│   └── weread_export.py  # 主导出脚本
├── config/
│   └── weread.json       # 配置文件模板
├── templates/
│   ├── markdown.template # Markdown 模板
│   └── obsidian.template # Obsidian 专用模板
└── requirements.txt      # Python 依赖
```

## 当前接口兼容说明（2026-04 实测）

微信读书网页接口已经发生变化，旧实现里常见的这两个接口已失效：
- `/web/book/bookShelf` → 会返回 404
- `/web/book/reviewlist` → 会返回 404

当前实测可用的接口组合是：
- 书架：`/web/shelf/sync`
- 有笔记书籍列表：`/api/user/notebook`
- 书籍详情：`/api/book/info`
- 划线：`/web/book/bookmarklist`
- 书评 / 想法：`/web/review/list`

另外，`/api/user/notebook` 返回的书籍结构与旧书架接口不同：
- 书籍主体嵌套在 `book` 字段内
- 导出前需要先把 `book.bookId / title / author ...` 归一化出来

实践建议：
- `--all` 最好优先导出 `notebook` 里的书，而不是整张书架，避免生成大量没有划线/想法的空文件
- 请求头里加上 `Referer: https://weread.qq.com/`、`Origin: https://weread.qq.com`、`Accept: application/json, text/plain, */*` 更稳

## 注意事项

1. **Cookie 有效期**: `wr_skey` 会过期，需要定期更新
2. **导出限制**: 大量笔记导出可能需要较长时间
3. **隐私保护**: 配置文件包含敏感信息，请勿提交到公开仓库
4. **备份建议**: 定期备份导出的笔记文件

## 故障排除

### Cookie 失效

如果导出失败，可能是 Cookie 过期：
1. 重新登录微信读书网页版
2. 获取新的 `wr_skey`
3. 更新配置文件

### 网络问题

如遇网络超时：
```bash
# 增加超时时间
python scripts/weread_export.py --all --timeout 60
```

### 导出不全

部分书籍可能需要先打开阅读页面才能导出笔记。

## 相关链接

- 微信读书: https://weread.qq.com
- 微信读书网页版: https://weread.qq.com/web/reader/

---

**License**: MIT  
**Author**: Zyi  
**Version**: 1.0.0
